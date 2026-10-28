"""Inventory must identify occurrences, not guess business meaning from names."""
from hashlib import sha256
from io import BytesIO

import pytest

pytest.importorskip('pypdf')
pytest.importorskip('reportlab')

from pdf_integration_fixtures import synthetic_form
from alarm_inspection.integrations.pdf_inventory import inspect_pdf, PdfInspectionError


def test_stable_occurrence_ids_duplicates_types_and_presets():
    data = synthetic_form()
    inventory = inspect_pdf(data, pages=(1, 2))
    assert inventory == inspect_pdf(data, pages=(1, 2))
    assert inventory['source_sha256'] == sha256(data).hexdigest()
    assert inventory['source_page_count'] == 3
    assert inventory['selected_pages'] == [1, 2]
    assert len(inventory['targets']) == 6
    duplicates = [t for t in inventory['targets'] if t['qualified_name'] == 'duplicate']
    assert len(duplicates) == 2
    assert duplicates[0]['id'] != duplicates[1]['id']
    assert all(len(t['same_name_targets']) == 1 for t in duplicates)
    assert all(t['value'] == 'OLD PRESET' for t in duplicates)
    button = next(t for t in inventory['targets'] if t['qualified_name'] == 'result')
    assert button['kind'] == 'checkbox'
    assert button['export_states'] == ['/Off', '/Yes']
    choice = next(t for t in inventory['targets'] if t['kind'] == 'choice')
    assert choice['options'] == ['Pass', 'Fail']
    assert any(t['kind'] == 'signature' for t in inventory['targets'])
    assert inventory['has_active_content'] is True
    assert any(d['code'] == 'DUPLICATE_FIELD_NAME' for d in inventory['diagnostics'])
    assert not any(t['qualified_name'] == 'excluded' for t in inventory['targets'])


def test_page_geometry_and_preview_rect_are_explicit():
    inventory = inspect_pdf(synthetic_form(), pages=(1, 2))
    geometry = inventory['pages'][1]
    assert geometry['rotation'] == 90
    assert geometry['crop_box'] == [20.0, 30.0, 612.0, 792.0]
    assert geometry['display_width'] == 762
    assert geometry['display_height'] == 592
    target = next(t for t in inventory['targets'] if t['qualified_name'] == 'rotated')
    # Rotated crop coordinates, top-left origin, PDF points (independent of zoom).
    assert target['preview_rect'] == [620, 80, 638, 240]


def test_malformed_keys_are_captured_without_changing_source():
    data = synthetic_form(malformed=True)
    inventory = inspect_pdf(data, pages=(1,))
    assert inventory['source_sha256'] == sha256(data).hexdigest()
    assert any(d['code'] == 'PARSER_WARNING' and '/TU' in d['message']
               for d in inventory['diagnostics'])


@pytest.mark.parametrize('pages', [(), (0,), (4,), (1, 1), (2, 1), (True,), (1.0,)])
def test_invalid_page_selection_is_rejected(pages):
    with pytest.raises(PdfInspectionError, match='pages'):
        inspect_pdf(synthetic_form(), pages=pages)


def test_wrong_encrypted_and_oversized_input_is_rejected():
    for data in (b'not a PDF', synthetic_form(encrypted=True)):
        with pytest.raises(PdfInspectionError):
            inspect_pdf(data, pages=(1,))
    with pytest.raises(PdfInspectionError, match='size'):
        inspect_pdf(synthetic_form(), pages=(1,), max_bytes=100)


def test_id_is_bound_to_source_and_not_selection():
    data = synthetic_form()
    first = inspect_pdf(data, pages=(1,))
    both = inspect_pdf(data, pages=(1, 2))
    assert first['targets'][0]['id'] == both['targets'][0]['id']
    changed = inspect_pdf(data + b'\n% source revision', pages=(1,))
    assert first['targets'][0]['id'] != changed['targets'][0]['id']


def test_inherited_identity_values_and_button_subtypes():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(synthetic_form())))
    widget = writer.pages[0]['/Annots'][0].get_object()
    parent = DictionaryObject({NameObject('/T'): TextStringObject('parent'),
                               NameObject('/FT'): NameObject('/Tx'),
                               NameObject('/V'): TextStringObject('Inherited value')})
    parent[NameObject('/Kids')] = ArrayObject([writer.pages[0]['/Annots'][0]])
    widget[NameObject('/Parent')] = writer._add_object(parent)
    widget.pop('/FT')
    widget.pop('/V')
    button = writer.pages[0]['/Annots'][2].get_object()
    for flags, expected in [(1 << 15, 'radio'), (1 << 16, 'pushbutton')]:
        button[NameObject('/Ff')] = NumberObject(flags)
        stream = BytesIO()
        writer.write(stream)
        inventory = inspect_pdf(stream.getvalue(), pages=(1,))
        assert inventory['targets'][0]['qualified_name'] == 'parent.duplicate'
        assert inventory['targets'][0]['value'] == 'Inherited value'
        assert inventory['targets'][2]['kind'] == expected


def test_cyclic_parent_and_nonstandard_units_are_rejected():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import FloatObject, NameObject
    for problem in ('cycle', 'units'):
        writer = PdfWriter()
        writer.clone_document_from_reader(PdfReader(BytesIO(synthetic_form())))
        if problem == 'cycle':
            ref = writer.pages[0]['/Annots'][0]
            ref.get_object()[NameObject('/Parent')] = ref
        else:
            writer.pages[0][NameObject('/UserUnit')] = FloatObject(2)
        stream = BytesIO()
        writer.write(stream)
        with pytest.raises(PdfInspectionError):
            inspect_pdf(stream.getvalue(), pages=(1,))


def test_indirect_annotation_array_and_appearance_dictionary():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(synthetic_form())))
    page = writer.pages[0]
    button = page['/Annots'][2].get_object()
    button[NameObject('/AP')] = writer._add_object(button['/AP'])
    page[NameObject('/Annots')] = writer._add_object(page['/Annots'])
    stream = BytesIO()
    writer.write(stream)
    inventory = inspect_pdf(stream.getvalue(), pages=(1,))
    assert inventory['targets'][2]['export_states'] == ['/Off', '/Yes']


def test_fractional_rotation_is_not_silently_truncated():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import FloatObject, NameObject
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(synthetic_form())))
    writer.pages[0][NameObject('/Rotate')] = FloatObject(90.5)
    stream = BytesIO(); writer.write(stream)
    with pytest.raises(PdfInspectionError, match='rotation'):
        inspect_pdf(stream.getvalue(), pages=(1,))
