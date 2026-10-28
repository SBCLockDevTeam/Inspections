"""Small generated PDFs; no customer documents or extracted answers."""
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ByteStringObject, DictionaryObject, FloatObject, NameObject, TextStringObject
from reportlab.pdfgen.canvas import Canvas


def synthetic_form(*, malformed=False, encrypted=False):
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792), invariant=1)
    canvas.drawString(40, 760, 'SYNTHETIC PRINTED LABEL')
    form = canvas.acroForm
    for y in (700, 660):
        form.textfield(name='duplicate', tooltip='duplicate-key-marker', x=100, y=y,
                       width=160, height=18, value='OLD PRESET', fontSize=10)
    form.checkbox(name='result', x=100, y=620, size=14, checked=True)
    form.choice(name='condition', x=100, y=580, width=160, height=18,
                options=['Pass', 'Fail'], value='Pass')
    canvas.linkURL('https://example.invalid/', (300, 600, 400, 620))
    canvas.showPage()
    canvas.drawString(40, 700, 'ROTATED PRINTED LABEL')
    canvas.acroForm.textfield(name='rotated', x=100, y=650, width=160, height=18)
    canvas.showPage()
    canvas.drawString(40, 700, 'EXCLUDED PAGE SECRET')
    canvas.acroForm.textfield(name='excluded', x=100, y=650, width=160, height=18,
                             value='EXCLUDED FIELD SECRET')
    canvas.save()
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(stream.getvalue())))
    writer._root_object[NameObject('/OpenAction')] = DictionaryObject({
        NameObject('/S'): NameObject('/JavaScript'),
        NameObject('/JS'): TextStringObject("app.alert('DO NOT EXECUTE');"),
    })
    writer.pages[1].cropbox.lower_left = (20, 30)
    writer.pages[1].rotate(90)
    signature = DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/FT'): NameObject('/Sig'), NameObject('/T'): TextStringObject('signature'),
        NameObject('/Rect'): ArrayObject([FloatObject(n) for n in (100, 530, 260, 550)]),
    })
    ref = writer._add_object(signature)
    writer.pages[0]['/Annots'].append(ref)
    writer._root_object['/AcroForm']['/Fields'].append(ref)
    if encrypted:
        writer._ID = ArrayObject([ByteStringObject(b'0123456789abcdef')] * 2)
        writer.encrypt('test-only-password')
    output = BytesIO()
    writer.write(output)
    data = output.getvalue()
    if malformed:
        # Preserve byte offsets so only the duplicate dictionary key is malformed.
        original = b'/TU (duplicate\\055key\\055marker)'
        replacement = b'/TU (first) /TU (second)'
        assert original in data
        data = data.replace(original, replacement.ljust(len(original)), 1)
    return data
