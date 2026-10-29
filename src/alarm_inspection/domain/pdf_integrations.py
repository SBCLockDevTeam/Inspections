"""Version-one PDF configuration contracts, with no executable expressions."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import math
import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, model_validator

Key = Literal['nfpa72', 'compliance']
Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
RecordId = Annotated[str, Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
LegacyId = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,36}$')]
InputId = Annotated[str, Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')]


def _timestamp(value):
    if isinstance(value, str): return datetime.fromisoformat(value)
    if not isinstance(value, datetime): raise ValueError('An ISO timestamp with offset is required.')
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(_timestamp)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, allow_inf_nan=False,
                              revalidate_instances='always')


class Versioned(Contract):
    schema_version: Literal[1] = 1

    @model_validator(mode='before')
    @classmethod
    def exact_version(cls, data):
        if isinstance(data, dict) and ('schema_version' in data and
                                      (type(data['schema_version']) is not int or data['schema_version'] != 1)):
            raise ValueError('Unsupported schema_version.')
        return data


def valid_blob_key(key: str) -> bool:
    uuid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    return bool(re.fullmatch(r'_pdf_integrations/(nfpa72|compliance)/' + uuid + r'/(original|normalized)\.pdf', key)
                or re.fullmatch(r'[A-Za-z0-9_-]{1,36}/form_exports/' + uuid + r'/document\.pdf', key))


class FileRef(Contract):
    key: str
    sha256: Digest
    size: Annotated[int, Field(ge=0, le=64 * 1024**2)]

    @model_validator(mode='after')
    def safe_key(self):
        if not valid_blob_key(self.key): raise ValueError('Invalid private object key.')
        return self


class PageGeometry(Contract):
    number: Annotated[int, Field(ge=1, le=50)]
    media_box: list[float] = Field(min_length=4, max_length=4)
    crop_box: list[float] = Field(min_length=4, max_length=4)
    rotation: Literal[0, 90, 180, 270]
    user_unit: float
    display_width: Annotated[float, Field(gt=0)]
    display_height: Annotated[float, Field(gt=0)]

    @model_validator(mode='before')
    @classmethod
    def exact_rotation(cls, data):
        if isinstance(data, dict) and type(data.get('rotation')) is not int:
            raise ValueError('Rotation must be an integer.')
        return data


class InventoryTarget(Contract):
    id: Digest
    page: Annotated[int, Field(ge=1, le=50)]
    occurrence: Annotated[int, Field(ge=0)]
    qualified_name: str
    rect: list[float] = Field(min_length=4, max_length=4)
    preview_rect: list[float] = Field(min_length=4, max_length=4)
    pdf_type: str
    kind: Literal['text', 'choice', 'checkbox', 'radio', 'signature', 'pushbutton', 'unknown']
    flags: int
    annotation_flags: int
    tooltip: str
    value: JsonValue
    default_value: JsonValue
    options: list[JsonValue]
    export_states: list[str]
    appearance_state: str
    same_name_targets: list[Digest]


class Inventory(Versioned):
    source_sha256: Digest
    source_page_count: Annotated[int, Field(ge=1, le=50)]
    selected_pages: list[int] = Field(min_length=1, max_length=50)
    pages: list[PageGeometry] = Field(min_length=1, max_length=50)
    targets: list[InventoryTarget] = Field(max_length=5000)
    has_active_content: bool
    diagnostics: list[dict[str, JsonValue]]

    @model_validator(mode='after')
    def consistent(self):
        if self.selected_pages != sorted(set(self.selected_pages)) or any(
                type(p) is not int or not 1 <= p <= self.source_page_count for p in self.selected_pages):
            raise ValueError('Invalid selected pages.')
        if [p.number for p in self.pages] != self.selected_pages:
            raise ValueError('Page geometry does not match selected pages.')
        ids = [t.id for t in self.targets]
        if len(ids) != len(set(ids)) or any(t.page not in self.selected_pages for t in self.targets):
            raise ValueError('Duplicate target identity or excluded target page.')
        for box in [b for p in self.pages for b in (p.media_box, p.crop_box)] + [t.rect for t in self.targets]:
            if box[2] <= box[0] or box[3] <= box[1]: raise ValueError('Invalid rectangle.')
        return self


class SourceRef(Contract):
    kind: Literal['inspection', 'checklist', 'panel', 'manual', 'count']
    field: str | None = None
    id: InputId | LegacyId | None = None

    @model_validator(mode='after')
    def allowlist(self):
        allowed = {'inspection': {'store_number', 'store_type', 'address', 'city', 'state', 'inspector_name',
                                  'start_date', 'completion_date'},
                   'panel': {'id', 'category', 'accepted_points', 'accepted_times'},
                   'count': {'installed', 'tested_good'}}
        if self.kind in allowed and self.field not in allowed[self.kind]:
            raise ValueError('Unknown source field.')
        if self.kind in {'manual', 'checklist', 'count'} and not self.id:
            raise ValueError('A stable source ID is required.')
        if self.kind in {'manual', 'checklist'} and self.field is not None:
            raise ValueError('Task/manual references use IDs, not field names.')
        if self.kind in {'inspection', 'panel'} and self.id is not None:
            raise ValueError('Panel scope is explicit in the snapshot, not a source expression.')
        return self


class Transform(Contract):
    kind: Literal['date', 'time', 'number', 'concat', 'lookup']
    format: str | None = Field(default=None, max_length=80)
    timezone: str | None = None
    decimals: int | None = Field(default=None, ge=0, le=6)
    separator: str = Field(default='', max_length=80)
    lookup: dict[str, JsonValue] = Field(default_factory=dict, max_length=50)

    @model_validator(mode='after')
    def declarative(self):
        if self.timezone:
            try: ZoneInfo(self.timezone)
            except (KeyError, ValueError) as exc: raise ValueError('Unknown timezone.') from exc
        if self.format and re.search(r'%(?![YymdHMSz%])', self.format):
            raise ValueError('Unsupported date/time format directive.')
        if self.kind == 'lookup' and not self.lookup: raise ValueError('Lookup choices are required.')
        if self.kind not in {'date', 'time'} and (self.format is not None or self.timezone is not None):
            raise ValueError('Date/time formatting belongs only to date/time transforms.')
        if self.kind != 'number' and self.decimals is not None: raise ValueError('Only numbers have decimal formatting.')
        if self.kind != 'concat' and self.separator: raise ValueError('Only concatenation has a separator.')
        if self.kind != 'lookup' and self.lookup: raise ValueError('Only lookups have a choice map.')
        return self


class Condition(Contract):
    source: SourceRef
    operator: Literal['answered', 'equals', 'not_equals']
    expected: JsonValue = None


class ManualInput(Contract):
    id: InputId
    label: str = Field(min_length=1, max_length=200)
    meaning: str = Field(min_length=1, max_length=500)
    type: Literal['text', 'number', 'date', 'datetime', 'yes_no_na', 'dropdown']
    scope: Literal['inspection', 'panel'] = 'inspection'
    required: bool = False
    required_when: Condition | None = None
    options: list[str] = Field(default_factory=list, max_length=50)
    unit: str | None = Field(default=None, max_length=40)
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode='after')
    def choices(self):
        if len(self.options) != len(set(self.options)) or any(not v.strip() or len(v) > 120 for v in self.options):
            raise ValueError('Invalid input choices.')
        if (self.type == 'dropdown') != bool(self.options): raise ValueError('Dropdown choices are required only for dropdowns.')
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Invalid numeric bounds.')
        if self.type != 'number' and (self.minimum is not None or self.maximum is not None or self.unit is not None):
            raise ValueError('Only numeric inputs support units/bounds.')
        return self

    def validate_value(self, value):
        if value is None: return  # Explicitly cleared; readiness decides requiredness.
        if self.type == 'number':
            if type(value) not in (int, float) or not math.isfinite(value): raise ValueError('A finite number is required.')
            if self.minimum is not None and value < self.minimum or self.maximum is not None and value > self.maximum:
                raise ValueError('Number is outside configured bounds.')
        elif not isinstance(value, str) or len(value) > 2000:
            raise ValueError('A text answer of at most 2000 characters is required.')
        elif self.type == 'yes_no_na' and value not in ('Yes', 'No', 'NA'):
            raise ValueError('Choose Yes, No or NA.')
        elif self.type == 'dropdown' and value not in self.options:
            raise ValueError('Choose a configured option.')
        elif self.type == 'date':
            if len(value) != 10: raise ValueError('Use an ISO date.')
            date.fromisoformat(value)
        elif self.type == 'datetime':
            if datetime.fromisoformat(value).utcoffset() is None: raise ValueError('A timezone offset is required.')


class TargetMapping(Contract):
    target_id: Digest
    label: str = Field(default='', max_length=200)
    section: str = Field(default='', max_length=200)
    disposition: Literal['source', 'computed', 'constant', 'blank', 'excluded', 'sign_later']
    source: SourceRef | None = None
    constant: JsonValue = None
    transforms: list[Transform] = Field(default_factory=list, max_length=10)
    required: bool = False
    required_when: Condition | None = None
    reason: str = Field(default='', max_length=1000)
    overflow: Literal['block', 'wrap', 'shrink'] = 'block'

    @model_validator(mode='after')
    def disposition_fields(self):
        if (self.disposition in {'source', 'computed'}) != (self.source is not None):
            raise ValueError('Only source/computed dispositions have a source.')
        if self.disposition in {'blank', 'excluded', 'sign_later'} and not self.reason.strip():
            raise ValueError('A deliberate blank/exclusion/signing reason is required.')
        if self.disposition != 'constant' and self.constant is not None:
            raise ValueError('Unexpected constant.')
        if self.disposition == 'constant' and self.constant is None: raise ValueError('A constant value is required.')
        if self.transforms and self.source is None: raise ValueError('Transforms require a source.')
        return self


class AnswerGroup(Contract):
    id: InputId
    members: dict[Literal['Yes', 'No', 'NA'], list[Digest]]
    required: bool = False
    required_when: Condition | None = None

    @model_validator(mode='after')
    def disjoint(self):
        ids = [ident for values in self.members.values() for ident in values]
        if not ids or len(ids) != len(set(ids)) or any(not ids for ids in self.members.values()):
            raise ValueError('Answer group members must be nonempty and disjoint.')
        return self


class NormalizedTarget(Contract):
    page: Annotated[int, Field(ge=1, le=50)]
    rect: list[float] = Field(min_length=4, max_length=4)


class IntegrationConfig(Versioned):
    integration_key: Key
    version_id: RecordId
    original: FileRef
    normalized: FileRef | None = None
    normalized_targets: dict[Digest, NormalizedTarget] = Field(default_factory=dict)
    inventory: Inventory
    mappings: list[TargetMapping] = Field(default_factory=list, max_length=5000)
    manual_inputs: list[ManualInput] = Field(default_factory=list, max_length=1000)
    answer_groups: list[AnswerGroup] = Field(default_factory=list, max_length=1000)
    applicability: Literal['panel', 'inspection', 'no_panel'] | None = None
    applicability_reason: str = Field(default='', max_length=1000)
    categories: list[str] = Field(default_factory=list, max_length=100)
    signature_policy: Literal['unresolved', 'later_signing', 'signed_required'] = 'unresolved'
    supplemental_policy: Literal['unresolved', 'manual_declaration', 'not_applicable'] = 'unresolved'

    @model_validator(mode='after')
    def references(self):
        expected = [1, 2, 3, 4] if self.integration_key == 'nfpa72' else [1]
        if self.inventory.selected_pages != expected: raise ValueError('Initial integration page range is fixed.')
        prefix = f'_pdf_integrations/{self.integration_key}/{self.version_id}/'
        if self.original.key != prefix + 'original.pdf' or self.original.sha256 != self.inventory.source_sha256:
            raise ValueError('Original reference does not match version/inventory.')
        if self.normalized and self.normalized.key != prefix + 'normalized.pdf':
            raise ValueError('Normalized reference belongs to another version.')
        targets = {t.id: t for t in self.inventory.targets}
        if self.normalized is None and self.normalized_targets:
            raise ValueError('Normalized correspondence requires a normalized file.')
        if self.normalized and (set(self.normalized_targets) != set(targets) or any(
                loc.page > len(expected) or loc.rect[2] <= loc.rect[0] or loc.rect[3] <= loc.rect[1]
                for loc in self.normalized_targets.values())):
            raise ValueError('Normalized correspondence must cover every original target.')
        ids = [m.target_id for m in self.mappings]
        inputs = [i.id for i in self.manual_inputs]
        if len(ids) != len(set(ids)) or set(ids) - targets.keys() or len(inputs) != len(set(inputs)):
            raise ValueError('Duplicate or unknown mapping/input ID.')
        for mapping in self.mappings:
            if mapping.source and mapping.source.kind == 'manual' and mapping.source.id not in inputs:
                raise ValueError('Unknown manual source.')
            if targets[mapping.target_id].kind == 'signature' and mapping.disposition not in {'blank', 'excluded', 'sign_later'}:
                raise ValueError('Signature generation is outside initial scope.')
        group_ids = [g.id for g in self.answer_groups]
        members = [ident for g in self.answer_groups for values in g.members.values() for ident in values]
        if len(group_ids) != len(set(group_ids)) or len(members) != len(set(members)) or any(
                ident not in targets or targets[ident].kind not in {'checkbox', 'radio'} for ident in members):
            raise ValueError('Invalid or overlapping answer group.')
        if self.applicability == 'no_panel' and not self.applicability_reason.strip():
            raise ValueError('No-panel applicability requires an explicit reason.')
        conditions = [item.required_when for item in [*self.mappings, *self.manual_inputs, *self.answer_groups]]
        if any(c and c.source.kind == 'manual' and c.source.id not in inputs for c in conditions):
            raise ValueError('Unknown manual condition source.')
        return self


class FormAnswer(Versioned):
    input_id: InputId
    value: JsonValue
    override: bool = False
    reason: str = Field(default='', max_length=1000)
    source_fingerprint: Digest | None = None
    original_value: JsonValue = None

    @model_validator(mode='after')
    def override_evidence(self):
        if self.override and (not self.reason.strip() or self.source_fingerprint is None):
            raise ValueError('Overrides require a reason and original source fingerprint.')
        return self


class SourceProvenance(Contract):
    source: SourceRef
    target_id: Digest | None = None
    decision_id: LegacyId | None = None
    decided_by: LegacyId | None = None
    decided_at: Timestamp | None = None
    evidence_ids: list[LegacyId] = Field(default_factory=list, max_length=1000)


class FieldVerification(Contract):
    target_id: Digest
    verified_by: LegacyId
    verified_at: Timestamp
    test_artifact_id: RecordId


class VerificationEvidence(Versioned):
    payload_sha256: Digest
    test_artifact_id: RecordId
    fields: list[FieldVerification] = Field(min_length=1, max_length=5000)


class ArtifactContext(Versioned):
    source_fingerprint: Digest
    panel_ids: list[LegacyId] = Field(default_factory=list, max_length=1000)
    resolved_values: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: list[SourceProvenance] = Field(default_factory=list, max_length=5000)

    @model_validator(mode='after')
    def unique_scope(self):
        if self.panel_ids != sorted(set(self.panel_ids)): raise ValueError('Panel scope must be sorted and unique.')
        return self


class ReadinessBlocker(Contract):
    code: Literal['MISSING_ANSWER', 'UNACCEPTED_EVENT', 'SOURCE_CHANGED', 'AMBIGUOUS_TARGET', 'OVERFLOW',
                  'SIGNATURE_POLICY_UNRESOLVED', 'INVALID_SCOPE', 'UNCONFIGURED', 'DISABLED']
    message: str = Field(min_length=1, max_length=1000)
    target_id: Digest | None = None
    source_id: str | None = Field(default=None, max_length=100)
    section: str = Field(default='', max_length=200)


def canonical_json(value) -> str:
    if isinstance(value, BaseModel): value = value.model_dump(mode='json')
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def payload_hash(value) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()
