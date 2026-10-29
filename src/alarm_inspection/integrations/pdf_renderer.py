"""Offline, watermarked rendering proof; not a production export endpoint.

Discard widget annotations instead of painting over their appearances. Copy only
page drawing content/resources and geometry into fresh pages, then draw explicit
occurrence-specific probe values. Originals and legacy fill helpers stay intact.
"""
from __future__ import annotations

from io import BytesIO

from alarm_inspection.integrations.pdf_inventory import inspect_pdf


def render_feasibility_pdf(data: bytes, inventory: dict, values: dict[str, object]) -> bytes:
    """Return a flattened diagnostic derivative, always marked as a test document.

    Unassigned widgets are intentionally blank. This proves annotation isolation;
    it is not an approved mapping/disposition system and cannot produce finals.
    """
    current = inspect_pdf(data, pages=tuple(inventory.get('selected_pages', ())))
    if inventory != current:
        raise ValueError('Source or inventory changed; re-inspect the original.')
    targets = {target['id']: target for target in current['targets']}
    if set(values) - targets.keys():
        raise ValueError('Unknown target in probe values.')
    from pypdf import PdfReader, PdfWriter, PageObject
    from pypdf.generic import DictionaryObject, FloatObject, NameObject, NumberObject, RectangleObject
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen.canvas import Canvas

    reader = PdfReader(BytesIO(data))
    writer = PdfWriter()
    for geometry in current['pages']:
        number = geometry['number']
        source = reader.pages[number - 1]
        media = geometry['media_box']
        # Allowlist page drawing data: do not clone annotations, form trees,
        # actions, attachments, metadata or excluded page structures.
        background = PageObject.create_blank_page(width=media[2] - media[0], height=media[3] - media[1])
        background[NameObject('/MediaBox')] = RectangleObject(media)
        if '/Contents' in source:
            background[NameObject('/Contents')] = source.raw_get('/Contents')
        background[NameObject('/Resources')] = source.get('/Resources', DictionaryObject())
        for key in ('/CropBox', '/TrimBox', '/BleedBox', '/ArtBox'):
            if key in source:
                background[NameObject(key)] = RectangleObject(source[key])

        buffer = BytesIO()
        canvas = Canvas(buffer, pagesize=(media[2], media[3]), invariant=1)
        for target in current['targets']:
            if target['page'] != number or target['id'] not in values:
                continue
            value = values[target['id']]
            if value is None or value == '':
                continue
            kind = target['kind']
            x0, y0, x1, y1 = target['rect']
            width, height = x1 - x0, y1 - y0
            if kind in ('checkbox', 'radio'):
                if type(value) is not bool:
                    raise ValueError('Button probe values must be boolean.')
                if value:
                    inset = min(width, height) * .15
                    canvas.setLineWidth(.7)
                    canvas.line(x0 + inset, y0 + inset, x1 - inset, y1 - inset)
                    canvas.line(x0 + inset, y1 - inset, x1 - inset, y0 + inset)
                continue
            if kind == 'signature':
                raise ValueError('A feasibility probe cannot populate a signature.')
            if kind not in ('text', 'choice'):
                raise ValueError('Unsupported target type for feasibility probe.')
            if not isinstance(value, str):
                raise ValueError('Text probe values must be strings.')
            if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
                raise ValueError('Unsupported character in ASCII feasibility probe.')
            font_size = min(9, height * .65)
            if font_size < 4 or stringWidth(value, 'Helvetica', font_size) > width - 2:
                raise ValueError(f'Text overflow at target {target["id"]}.')
            canvas.setFont('Helvetica', font_size)
            canvas.drawString(x0 + 1, y0 + (height - font_size) / 2 + font_size * .2, value)
        canvas.setFillColorRGB(.65, 0, 0)
        canvas.setFont('Helvetica-Bold', 7)
        cx0, cy0, cx1, cy1 = geometry['crop_box']
        canvas.drawString(cx0 + 12, cy0 + 12, 'PDF INTEGRATION FEASIBILITY - NOT AN INSPECTION REPORT')
        canvas.save()
        overlay = PdfReader(BytesIO(buffer.getvalue())).pages[0]
        background.merge_page(overlay)
        background.pop('/Annots', None)
        background[NameObject('/Rotate')] = NumberObject(geometry['rotation'])
        background[NameObject('/UserUnit')] = FloatObject(1)
        writer.add_page(background)
    writer.add_metadata({'/Title': 'PDF integration feasibility - NOT an inspection report'})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def render_diagnostic_pdf(data, inventory, targets):
    """Isolated per-occurrence mapping proof; always visibly nonfinal."""
    # Reuse the proven page/annotation isolation with blank values, then draw
    # already validated layouts. This entry point cannot remove the watermark.
    base = render_feasibility_pdf(data, inventory, {})
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen.canvas import Canvas
    reader = PdfReader(BytesIO(base)); writer = PdfWriter()
    locations = {t['id']:t for t in inventory['targets']}
    if set(targets) - locations.keys(): raise ValueError('Unknown diagnostic target.')
    for index, page in enumerate(reader.pages):
        geometry = inventory['pages'][index]
        buffer = BytesIO(); canvas = Canvas(buffer, pagesize=geometry['media_box'][2:], invariant=1)
        for ident, result in targets.items():
            target = locations[ident]
            if target['page'] != geometry['number']: continue
            x0,y0,x1,y1 = target['rect']
            if result.get('checked'):
                canvas.setLineWidth(.7); canvas.line(x0+1,y0+1,x1-1,y1-1); canvas.line(x0+1,y1-1,x1-1,y0+1)
            elif result.get('text'):
                size = result['font_size']; canvas.setFont('Helvetica',size)
                for line_index,line in enumerate(result['lines']):
                    canvas.drawString(x0+1,y1-size*(line_index*1.2+1),line)
        canvas.showPage(); canvas.save(); page.merge_page(PdfReader(BytesIO(buffer.getvalue())).pages[0]); page.pop('/Annots',None); writer.add_page(page)
    writer.add_metadata({'/Title':'PDF integration TEST - NOT AN INSPECTION REPORT'})
    output=BytesIO(); writer.write(output); return output.getvalue()
