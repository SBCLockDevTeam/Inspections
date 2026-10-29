"""Pure PDF readiness over an immutable saved-data snapshot."""
from typing import Literal
from pydantic import Field, JsonValue

from alarm_inspection.domain.pdf_integrations import (
    ArtifactContext, Contract, Digest, IntegrationConfig, ReadinessBlocker, SourceRef,
    canonical_json, payload_hash,
)
from alarm_inspection.domain.pdf_mapping import (
    MappingError, SourceValue, TargetValue, answered, condition_matches, map_answer_group,
    map_target, usable,
)

RULESET_VERSION = 'pdf-p7-1'


class ReadinessIssue(ReadinessBlocker):
    navigation: Literal['store_data','checklist','form_details','points','integrations'] = 'integrations'


def issue(message, code='UNCONFIGURED', *, source=None, target=None, section='', navigation=None):
    destinations = {'inspection':'store_data','checklist':'checklist','manual':'form_details','panel':'points','count':'points'}
    return ReadinessIssue(code=code, message=message, target_id=target, section=section,
        source_id=(source.id or source.field or source.kind) if source else None,
        navigation=navigation or destinations.get(source.kind if source else '', 'integrations'))


class SavedSnapshot(Contract):
    inspection_id: str
    config: IntegrationConfig | None = None
    stored_config_sha256: Digest | None = None
    panel_ids: list[str] = Field(default_factory=list)
    facts: dict[str, JsonValue] = Field(default_factory=dict)
    sources: dict[str, SourceValue] = Field(default_factory=dict)
    manual_values: dict[str, list[SourceValue]] = Field(default_factory=dict)
    catalog_metadata: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    panel_choices: list[dict[str, JsonValue]] = Field(default_factory=list)
    blockers: list[ReadinessIssue] = Field(default_factory=list)

    def resolve(self, ref):
        return self.sources.get(canonical_json(ref), SourceValue(source=ref, type='number' if ref.kind=='count' else 'text', state='unavailable',
            fingerprint=payload_hash({'unknown':ref.model_dump()}), message='No saved compatible source is available.'))

    @property
    def fingerprint(self):
        return payload_hash({'ruleset':RULESET_VERSION, 'inspection_id':self.inspection_id,
            'stored_config':self.stored_config_sha256, 'effective_config':self.config.model_dump(mode='json') if self.config else None,
            'panels':self.panel_ids, 'facts':self.facts})


class ReadinessResult(Contract):
    ready: bool
    source_fingerprint: Digest
    panel_ids: list[str]
    version_id: str | None = None
    blockers: list[ReadinessIssue] = Field(default_factory=list)
    targets: dict[str, TargetValue] = Field(default_factory=dict)

    def artifact_context(self):
        if not self.ready: raise ValueError('Resolve readiness blockers before creating an export snapshot.')
        provenance = {canonical_json(p):p for target in self.targets.values() for p in target.provenance}
        return ArtifactContext(source_fingerprint=self.source_fingerprint, panel_ids=self.panel_ids,
            resolved_values={key:value.model_dump(mode='json') for key,value in self.targets.items()},
            provenance=[provenance[key] for key in sorted(provenance)])


def evaluate_snapshot(snapshot: SavedSnapshot) -> ReadinessResult:
    blockers, outputs = list(snapshot.blockers), {}
    config = snapshot.config
    if config is None:
        return ReadinessResult(ready=False,source_fingerprint=snapshot.fingerprint,panel_ids=snapshot.panel_ids,blockers=blockers)
    if config.default_timezone:
        config=config.model_copy(update={'mappings':[mapping.model_copy(update={'transforms':[
            transform.model_copy(update={'timezone':config.default_timezone}) if transform.kind in {'date','time'} and transform.timezone is None and mapping.source is not None and snapshot.resolve(mapping.source).type=='datetime' else transform
            for transform in mapping.transforms]}) for mapping in config.mappings]})
    resolve = snapshot.resolve

    def error(exc, mapping=None):
        blockers.append(issue(str(exc),exc.code,source=exc.source or (mapping.source if mapping else None),
                              target=mapping.target_id if mapping else None,section=mapping.section if mapping else '',
                              navigation='integrations' if exc.code in {'UNCONFIGURED','AMBIGUOUS_TARGET'} else None))

    for definition in config.manual_inputs:
        try:
            required = definition.required or bool(definition.required_when and condition_matches(definition.required_when,resolve))
            for value in snapshot.manual_values.get(definition.id, []):
                if required or value.state in {'changed','unavailable'}: usable(value)
        except MappingError as exc: error(exc)
    if config.signature_policy != 'later_signing' and any(t.kind == 'signature' for t in config.inventory.targets):
        blockers.append(issue('A supported, explicit signature policy is required; no signature will be fabricated.', 'SIGNATURE_POLICY_UNRESOLVED'))
    if config.integration_key == 'nfpa72' and config.mapping_mode != 'store_checklist':
        try:
            if config.supplemental_policy != 'manual_declaration' or config.supplemental_source is None:
                raise MappingError('Configure an explicit saved supplemental-sheet declaration source.','UNCONFIGURED')
            declaration = usable(resolve(config.supplemental_source))
            if declaration.type not in {'yes_no_na','choice'} or declaration.value not in ('Yes','No'):
                raise MappingError('Supplemental-sheet declaration must be an explicit Yes or No.','MISSING_ANSWER',declaration.source)
        except MappingError as exc: error(exc)
    mappings = {m.target_id:m for m in config.mappings}
    for group in config.answer_groups:
        try: outputs.update(map_answer_group(config,group,resolve))
        except MappingError as exc: error(exc)
    grouped = {ident for group in config.answer_groups for ids in group.members.values() for ident in ids}
    for target in config.inventory.targets:
        if config.normalized:
            target = target.model_copy(update={'rect':config.normalized_targets[target.id].rect})
        mapping = mappings.get(target.id)
        if mapping is None:
            blockers.append(issue('Every target needs an explicit verified disposition.','UNCONFIGURED',target=target.id)); continue
        if target.id in grouped: continue
        try:
            required = mapping.required or bool(mapping.required_when and condition_matches(mapping.required_when,resolve))
            if mapping.disposition in {'blank','excluded','sign_later'}:
                if required: raise MappingError('A required field cannot have a blank disposition.','UNCONFIGURED')
                outputs[target.id] = TargetValue(target_id=target.id, checked=False if target.kind in {'checkbox','radio'} else None,
                                                  pdf_state='/Off' if target.kind in {'checkbox','radio'} else None)
                continue
            if mapping.disposition == 'constant':
                if target.kind in {'checkbox','radio'}:
                    raise MappingError('Static selections cannot manufacture inspection results.','UNCONFIGURED')
                source = SourceValue(source=SourceRef(kind='inspection',field='store_number'), type='text',state='ready',
                                     value=mapping.constant,fingerprint=payload_hash({'constant':mapping.constant}))
            else: source = resolve(mapping.source)
            if config.mapping_mode == 'store_checklist':
                if mapping.source_schema_sha256 and snapshot.catalog_metadata.get(canonical_json(mapping.source),{}).get('schema_sha256') != mapping.source_schema_sha256:
                    raise MappingError('The mapped Check List field changed. Review its mapping in Administration.', 'SOURCE_CHANGED', mapping.source)
                if source.state == 'missing' and mapping.default_value is not None:
                    source = source.model_copy(update={'value':mapping.default_value,'state':'ready'})
                if target.kind in {'checkbox','radio'} and mapping.source:
                    if source.state == 'missing' and not required:
                        source = source.model_copy(update={'value':False,'state':'ready','type':'boolean'})
                    else:
                        usable(source)
                        if source.value not in ('Yes','No','NA') or mapping.check_on is None:
                            raise MappingError('Choose which Check List answer marks this PDF field.', 'UNCONFIGURED', mapping.source)
                        source = source.model_copy(update={'value':source.value == mapping.check_on,'type':'boolean'})
            outputs[target.id] = map_target(target,mapping,source,resolve,required=required)
        except MappingError as exc: error(exc,mapping)
    # Stable order/deduplication; wording changes do not alter the saved-data fingerprint.
    unique = {canonical_json(blocker):blocker for blocker in blockers}
    return ReadinessResult(ready=not unique, source_fingerprint=snapshot.fingerprint,panel_ids=snapshot.panel_ids,
                           version_id=config.version_id,blockers=[unique[key] for key in sorted(unique)],targets=outputs)
