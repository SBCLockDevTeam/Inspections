"""Read-only occurrence-level PDF inspection for private integration setup.

This module never executes PDF actions, changes source bytes, or infers business
meaning. Returned values/defaults may contain private data: do not log inventories.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import logging
import math
import threading


class PdfInspectionError(ValueError):
    """The document cannot be inventoried safely with the requested selection."""


@contextmanager
def _parser_messages():
    messages = []
    thread_id = threading.get_ident()

    class Capture(logging.Handler):
        def emit(self, record):
            if record.thread == thread_id and record.levelno >= logging.WARNING:
                message = record.getMessage()
                if message not in messages:
                    messages.append(message)

    handler = Capture()
    logger = logging.getLogger('pypdf')
    logger.addHandler(handler)
    try:
        yield messages
    finally:
        logger.removeHandler(handler)


def _box(value):
    try:
        result = [float(n) for n in value]
        if len(result) != 4 or not all(math.isfinite(n) for n in result):
            raise ValueError
        if result[2] <= result[0] or result[3] <= result[1]:
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError) as exc:
        raise PdfInspectionError('Invalid page or target rectangle.') from exc


def preview_rect(rect, crop_box, rotation):
    """Convert PDF-space geometry to top-left displayed points, before zoom."""
    x0, y0, x1, y1 = rect
    cx0, cy0, cx1, cy1 = crop_box
    if rotation == 0:
        return [x0 - cx0, cy1 - y1, x1 - cx0, cy1 - y0]
    if rotation == 90:
        return [y0 - cy0, x0 - cx0, y1 - cy0, x1 - cx0]
    if rotation == 180:
        return [cx1 - x1, y0 - cy0, cx1 - x0, y1 - cy0]
    if rotation == 270:
        return [cy1 - y1, cx1 - x1, cy1 - y0, cx1 - x0]
    raise PdfInspectionError('Unsupported page rotation.')


def _parents(widget):
    chain, seen = [], set()
    current = widget
    while current is not None:
        if id(current) in seen or len(chain) >= 32:
            raise PdfInspectionError('Cyclic or excessive field parent hierarchy.')
        seen.add(id(current))
        chain.append(current)
        parent = current.get('/Parent')
        current = parent.get_object() if parent is not None else None
    return chain


def _inherited(chain, key, default=None):
    for node in chain:
        if key in node:
            return node[key]
    return default


def _value(value):
    """Expose scalar/choice values, not arbitrary nested signature structures."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {'present': True}
    return str(value)


def inspect_pdf(data: bytes, *, pages: tuple[int, ...], max_bytes=40 * 1024 * 1024,
                max_pages=50, max_targets=5000) -> dict:
    """Inventory explicitly selected, ascending, one-based source pages.

    Limits are initial offline feasibility bounds, not a sandbox for hostile PDFs.
    Parsing/rendering resource isolation must be added before web template intake.
    """
    if not isinstance(data, bytes) or not data or len(data) > max_bytes:
        raise PdfInspectionError('PDF input size is empty or exceeds the limit.')
    if not data.startswith(b'%PDF-'):
        raise PdfInspectionError('Expected PDF content.')
    if (not pages or any(type(p) is not int or p < 1 for p in pages)
            or tuple(sorted(set(pages))) != tuple(pages)):
        raise PdfInspectionError('Selected pages must be distinct ascending positive integers.')
    try:
        from pypdf import PdfReader
        from pypdf.generic import StreamObject
    except ImportError as exc:
        raise RuntimeError("PDF inspection requires the existing 'web' dependencies.") from exc

    with _parser_messages() as messages:
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise PdfInspectionError('Encrypted PDF templates are not supported.')
            count = len(reader.pages)
            if count > max_pages or pages[-1] > count:
                raise PdfInspectionError('Selected pages or source pages exceed the limit.')
            root = reader.trailer['/Root']
            names = root.get('/Names', {})
            names = names.get_object() if hasattr(names, 'get_object') else names
            active = bool('/OpenAction' in root or '/AA' in root
                          or '/JavaScript' in names or '/EmbeddedFiles' in names)
            geometry, targets, diagnostics = [], [], []
            fingerprint = sha256(data).hexdigest()
            for number in pages:
                page = reader.pages[number - 1]
                crop, media = _box(page.cropbox), _box(page.mediabox)
                rotation = int(page.get('/Rotate', 0)) % 360
                if rotation not in (0, 90, 180, 270):
                    raise PdfInspectionError('Unsupported page rotation.')
                unit = float(page.get('/UserUnit', 1))
                if not math.isfinite(unit) or unit != 1:
                    raise PdfInspectionError('Nonstandard page units need a reviewed rendering strategy.')
                width, height = crop[2] - crop[0], crop[3] - crop[1]
                if rotation in (90, 270):
                    width, height = height, width
                geometry.append({'number': number, 'media_box': media, 'crop_box': crop,
                                 'rotation': rotation, 'user_unit': unit,
                                 'display_width': width, 'display_height': height})
                active = active or '/AA' in page
                for occurrence, ref in enumerate(page.get('/Annots', [])):
                    widget = ref.get_object()
                    active = active or '/A' in widget or '/AA' in widget
                    if widget.get('/Subtype') != '/Widget':
                        continue
                    chain = _parents(widget)
                    active = active or any('/AA' in node or '/A' in node for node in chain)
                    path = '.'.join(str(n['/T']) for n in reversed(chain) if '/T' in n)
                    field_type = str(_inherited(chain, '/FT', ''))
                    flags = int(_inherited(chain, '/Ff', 0))
                    kind = {'/Tx': 'text', '/Ch': 'choice', '/Sig': 'signature'}.get(field_type, 'unknown')
                    if field_type == '/Btn':
                        kind = 'pushbutton' if flags & (1 << 16) else 'radio' if flags & (1 << 15) else 'checkbox'
                    rect = _box(widget.get('/Rect', []))
                    appearance = widget.get('/AP', {})
                    normal = appearance.get('/N')
                    normal = normal.get_object() if normal is not None else None
                    states = sorted(str(key) for key in normal) if isinstance(normal, dict) and not isinstance(normal, StreamObject) else []
                    identity = json.dumps([fingerprint, number, occurrence, rect, path],
                                          separators=(',', ':'), ensure_ascii=True)
                    targets.append({
                        'id': sha256(identity.encode()).hexdigest(), 'page': number,
                        'occurrence': occurrence, 'qualified_name': path, 'rect': rect,
                        'preview_rect': preview_rect(rect, crop, rotation),
                        'pdf_type': field_type, 'kind': kind, 'flags': flags,
                        'annotation_flags': int(widget.get('/F', 0)),
                        'tooltip': str(_inherited(chain, '/TU', '')),
                        'value': _value(_inherited(chain, '/V')),
                        'default_value': _value(_inherited(chain, '/DV')),
                        'options': _value(_inherited(chain, '/Opt', [])),
                        'export_states': states, 'appearance_state': str(widget.get('/AS', '')),
                        'same_name_targets': [],
                    })
                    if len(targets) > max_targets:
                        raise PdfInspectionError('PDF target limit exceeded.')
            by_name = {}
            for target in targets:
                by_name.setdefault(target['qualified_name'], []).append(target['id'])
            for target in targets:
                target['same_name_targets'] = [key for key in by_name[target['qualified_name']]
                                               if key != target['id']]
            for name, ids in by_name.items():
                if len(ids) > 1:
                    diagnostics.append({'code': 'DUPLICATE_FIELD_NAME', 'field': name, 'targets': ids})
            diagnostics.extend({'code': 'PARSER_WARNING', 'message': message} for message in messages)
            return {'schema_version': 1, 'source_sha256': fingerprint, 'source_page_count': count,
                    'selected_pages': list(pages), 'pages': geometry, 'targets': targets,
                    'has_active_content': bool(active), 'diagnostics': diagnostics}
        except PdfInspectionError:
            raise
        except Exception as exc:
            # Keep parser internals and source contents out of caller-facing errors.
            raise PdfInspectionError('PDF structure could not be inventoried.') from exc
