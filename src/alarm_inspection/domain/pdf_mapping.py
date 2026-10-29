"""Pure, allowlisted value/target rules; no inspection reads or writes."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, JsonValue
from alarm_inspection.domain.pdf_integrations import (
    Contract, Digest, SourceRef, SourceProvenance, canonical_json, payload_hash,
)


class SourceValue(Contract):
    source: SourceRef
    type: Literal['text', 'number', 'date', 'datetime', 'yes_no_na', 'choice', 'boolean', 'points', 'times']
    state: Literal['ready', 'missing', 'changed', 'unavailable']
    value: JsonValue = None
    fingerprint: Digest
    message: str = ''
    provenance: list[SourceProvenance] = Field(default_factory=list)


class TargetValue(Contract):
    target_id: Digest
    raw_value: JsonValue = None
    text: str = ''
    checked: bool | None = None
    pdf_state: str | None = None
    font_size: float | None = None
    lines: list[str] = Field(default_factory=list)
    provenance: list[SourceProvenance] = Field(default_factory=list)


class MappingError(ValueError):
    def __init__(self, message, code='SOURCE_CHANGED', source=None):
        super().__init__(message)
        self.code, self.source = code, source


def answered(value):
    return value is not None and not (isinstance(value, str) and not value.strip())


def usable(source):
    if source.state in {'changed', 'unavailable'}:
        raise MappingError(source.message or 'Source requires review.', source=source.source)
    if source.state == 'missing' or not answered(source.value):
        raise MappingError('A saved answer is required.', 'MISSING_ANSWER', source.source)
    return source


def condition_matches(condition, resolve):
    source = resolve(condition.source)
    if source.state in {'changed', 'unavailable'}: usable(source)
    if condition.operator == 'answered': return source.state == 'ready' and answered(source.value)
    usable(source)
    equal = (source.value == condition.expected if type(source.value) in (int,float) and type(condition.expected) in (int,float)
             else canonical_json(source.value) == canonical_json(condition.expected))
    return equal if condition.operator == 'equals' else not equal


def _scalar(value):
    if isinstance(value, (dict, list)) or value is None:
        raise MappingError('Collection/missing values require a defined scalar mapping.')
    if type(value) is bool: return 'true' if value else 'false'
    return str(value)


def apply_transforms(source, transforms, resolve):
    source = usable(source)
    if source.type in {'points','times'} and transforms:
        raise MappingError('Device/time collections cannot substitute for explicit individual test results.')
    value, kind, provenance = source.value, source.type, list(source.provenance)
    fingerprints = [source.fingerprint]
    for transform in transforms:
        try:
            if transform.kind == 'lookup':
                key = canonical_json(value)  # Distinguish 0, false and "0".
                if key not in transform.lookup: raise MappingError('No explicit lookup for this answer.')
                value = transform.lookup[key]
                kind = 'boolean' if type(value) is bool else 'number' if type(value) in (int, float) else 'text'
            elif transform.kind == 'number':
                if kind != 'number' or type(value) not in (int, float): raise MappingError('A numeric source is required.')
                places = transform.decimals
                # No declared precision means preserve the saved value, never
                # silently round a measurement to an integer.
                value = str(value) if places is None else format(
                    Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), f'.{places}f')
                kind = 'text'
            elif transform.kind in {'date', 'time'}:
                if kind not in {'date', 'datetime'} or not transform.format:
                    raise MappingError('Date/time formatting requires a typed source and explicit format.')
                if kind == 'date':
                    if transform.kind == 'time' or transform.timezone or any(t in transform.format for t in ('%H','%M','%S','%z')):
                        raise MappingError('Date-only sources cannot supply a time or timezone.')
                    parsed = date.fromisoformat(value)
                else:
                    parsed = datetime.fromisoformat(value)
                    if parsed.utcoffset() is None: raise MappingError('A known timezone offset is required.')
                    if transform.timezone: parsed = parsed.astimezone(ZoneInfo(transform.timezone))
                value, kind = parsed.strftime(transform.format), 'text'
            elif transform.kind == 'concat':
                items = [value]
                for ref in transform.sources:
                    other = usable(resolve(ref)); items.append(other.value)
                    provenance.extend(other.provenance); fingerprints.append(other.fingerprint)
                value, kind = transform.separator.join(_scalar(item) for item in items), 'text'
        except MappingError: raise
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise MappingError('The configured transform cannot represent the saved value.', source=source.source) from exc
    return SourceValue(source=source.source, type=kind, state='ready', value=value, provenance=provenance,
                       fingerprint=payload_hash({'inputs':fingerprints,'transforms':[t.model_dump() for t in transforms]}))


def _button_state(target, checked):
    on = [s for s in target.export_states if s != '/Off']
    if '/Off' not in target.export_states or len(on) != 1:
        raise MappingError('Button on/off states need verified normalization.', 'AMBIGUOUS_TARGET')
    return on[0] if checked else '/Off'


def _fit(text, target, mapping):
    # Initial renderer contract: explicit Helvetica/ASCII; no silent glyph substitution.
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if any(ord(ch) > 126 or (ord(ch) < 32 and ch != '\n') for ch in text):
        raise MappingError('Unsupported character requires an approved font.', 'OVERFLOW')
    width, height = target.rect[2] - target.rect[0] - 2, target.rect[3] - target.rect[1] - 2
    sizes = [mapping.font_size]
    if mapping.overflow == 'shrink':
        sizes += [max(mapping.minimum_font_size, mapping.font_size - n * .5)
                  for n in range(1, int((mapping.font_size - mapping.minimum_font_size) * 2) + 2)]
    for size in sizes:
        lines = []
        for paragraph in text.split('\n'):
            if mapping.overflow != 'wrap': lines.append(paragraph); continue
            current = ''
            for word in re.findall(r'\S+| +', paragraph):
                candidate = current + word
                if current and stringWidth(candidate, 'Helvetica', size) > width:
                    lines.append(current); current = word
                else: current = candidate
            lines.append(current)
        if all(stringWidth(line, 'Helvetica', size) <= width for line in lines) and len(lines) * size * 1.1 <= height:
            return size, lines
    raise MappingError('Text overflow requires correction; no value was truncated.', 'OVERFLOW')


def map_target(target, mapping, source, resolve, *, required=None):
    required = mapping.required if required is None else required
    if source.state in {'changed', 'unavailable'}: usable(source)
    if source.state == 'missing' or not answered(source.value):
        if required or mapping.missing != 'blank': usable(source)
        return TargetValue(target_id=target.id, raw_value=source.value, pdf_state=_button_state(target, False) if target.kind in {'checkbox','radio'} else None)
    raw = source.value
    resolved = apply_transforms(source, mapping.transforms, resolve)
    if target.kind in {'checkbox', 'radio'}:
        if type(resolved.value) is bool: checked = resolved.value
        elif resolved.type in {'yes_no_na','choice'} and resolved.value in ('Yes', 'No'): checked = resolved.value == 'Yes'
        else: raise MappingError('This checkbox needs an explicit Yes/No or Boolean mapping.', 'AMBIGUOUS_TARGET')
        return TargetValue(target_id=target.id, raw_value=raw, checked=checked, pdf_state=_button_state(target, checked), provenance=resolved.provenance)
    if target.kind not in {'text','choice'}: raise MappingError('Unsupported writable target.', 'AMBIGUOUS_TARGET')
    text = _scalar(resolved.value)
    if target.kind == 'choice':
        exports = [item[0] if isinstance(item, list) else item for item in target.options]
        if text not in exports: raise MappingError('Saved value is not an allowed PDF choice.', 'AMBIGUOUS_TARGET')
    font, lines = _fit(text, target, mapping)
    return TargetValue(target_id=target.id, raw_value=raw, text=text, font_size=font, lines=lines, provenance=resolved.provenance)


def map_answer_group(config, group, resolve):
    mappings = {m.target_id:m for m in config.mappings}; targets = {t.id:t for t in config.inventory.targets}
    ids = [ident for members in group.members.values() for ident in members]
    bindings = [mappings.get(ident) for ident in ids]
    if any(m is None or m.source is None or m.disposition not in {'source','computed'} for m in bindings):
        raise MappingError('Every grouped button must use the explicit group source.', 'UNCONFIGURED')
    first = bindings[0]
    if any(canonical_json([m.source.model_dump(), [t.model_dump() for t in m.transforms]]) !=
           canonical_json([first.source.model_dump(), [t.model_dump() for t in first.transforms]]) for m in bindings):
        raise MappingError('Group members have conflicting sources/transforms.', 'AMBIGUOUS_TARGET')
    source = resolve(first.source)
    required = group.required or any(m.required for m in bindings)
    if group.required_when: required = required or condition_matches(group.required_when, resolve)
    for mapping in bindings:
        if mapping.required_when: required = required or condition_matches(mapping.required_when, resolve)
    if source.state in {'changed','unavailable'}: usable(source)
    if source.state == 'missing' or not answered(source.value):
        if required or any(m.missing != 'blank' for m in bindings): usable(source)
        answer = None
    else:
        if source.type not in {'yes_no_na','choice'} and not any(t.kind=='lookup' for t in first.transforms):
            raise MappingError('Grouped buttons require a typed answer or explicit lookup policy.','AMBIGUOUS_TARGET')
        resolved = apply_transforms(source, first.transforms, resolve)
        answer = resolved.value
        if not isinstance(answer, str) or answer not in group.members:
            raise MappingError('No verified group state/policy represents this answer.', 'AMBIGUOUS_TARGET')
    return {ident:TargetValue(target_id=ident, raw_value=source.value, checked=answer == option,
                              pdf_state=_button_state(targets[ident], answer == option),
                              provenance=resolved.provenance if answered(source.value) and source.state=='ready' else source.provenance)
            for option, members in group.members.items() for ident in members}


def count_approved_devices(facts, classification_id, metric):
    """Count only an explicit, complete approved dataset; never infer from events."""
    if metric not in {'installed','tested_good'} or not isinstance(classification_id,str) or not classification_id:
        raise ValueError('An explicit classification and known count metric are required.')
    seen, result = set(), 0
    for fact in facts:
        key = (fact.get('panel_id'), fact.get('point_id'))
        if (any(not isinstance(ident,str) or not ident for ident in key) or key in seen
                or not isinstance(fact.get('classification_id'),str) or not fact['classification_id']
                or fact.get('classification_approved') is not True):
            raise ValueError('Complete, distinct approved device classifications are required.')
        seen.add(key)
        if fact.get('classification_id') != classification_id: continue
        if metric == 'installed': result += 1; continue
        if fact.get('result_approved') is not True or fact.get('test_result') not in {'Pass','Fail','NA','Not tested'}:
            raise ValueError('Explicit approved device results are required.')
        result += fact['test_result'] == 'Pass'
    return result
