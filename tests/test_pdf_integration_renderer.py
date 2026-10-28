"""Offline feasibility output cannot be confused with a completed inspection."""
from io import BytesIO
import shutil
import subprocess

import pytest

pypdf = pytest.importorskip('pypdf')
pytest.importorskip('reportlab')

from pdf_integration_fixtures import synthetic_form
from alarm_inspection.integrations.pdf_inventory import inspect_pdf
from alarm_inspection.integrations.pdf_renderer import render_feasibility_pdf


def test_independent_duplicate_values_clean_page_subset_and_source_unchanged():
    source = synthetic_form()
    inventory = inspect_pdf(source, pages=(1, 2))
    targets = [t for t in inventory['targets'] if t['qualified_name'] == 'duplicate']
    output = render_feasibility_pdf(source, inventory, {
        targets[0]['id']: 'FIRST-LOCATION', targets[1]['id']: 'SECOND-LOCATION',
    })
    reader = pypdf.PdfReader(BytesIO(output))
    assert len(reader.pages) == 2
    text = '\n'.join(p.extract_text() for p in reader.pages)
    assert text.count('FIRST-LOCATION') == text.count('SECOND-LOCATION') == 1
    assert 'SYNTHETIC PRINTED LABEL' in text
    assert 'OLD PRESET' not in text and 'EXCLUDED' not in text
    assert 'FEASIBILITY' in text and 'NOT AN INSPECTION REPORT' in text
    assert reader.get_fields() is None
    assert '/AcroForm' not in reader.trailer['/Root']
    assert '/OpenAction' not in reader.trailer['/Root']
    assert all('/Annots' not in p and '/AA' not in p for p in reader.pages)
    assert b'EXCLUDED FIELD SECRET' not in output
    assert b'DO NOT EXECUTE' not in output
    assert list(reader.pages[1].cropbox) == [20, 30, 612, 792]
    assert reader.pages[1].rotation == 90
    assert inspect_pdf(source, pages=(1, 2)) == inventory


def test_unknown_targets_fingerprint_mismatch_and_forged_inventory_fail():
    source = synthetic_form()
    inventory = inspect_pdf(source, pages=(1,))
    with pytest.raises(ValueError, match='target'):
        render_feasibility_pdf(source, inventory, {'unknown': 'VALUE'})
    with pytest.raises(ValueError, match='inventory'):
        render_feasibility_pdf(source + b'\n% changed', inventory, {})
    inventory['targets'][0]['rect'][0] = 0
    with pytest.raises(ValueError, match='inventory'):
        render_feasibility_pdf(source, inventory, {})


def test_signature_invalid_checkbox_unsupported_glyph_and_overflow_fail():
    source = synthetic_form()
    inventory = inspect_pdf(source, pages=(1,))
    signature = next(t for t in inventory['targets'] if t['kind'] == 'signature')
    button = next(t for t in inventory['targets'] if t['kind'] == 'checkbox')
    text = next(t for t in inventory['targets'] if t['kind'] == 'text')
    for target, value, message in (
        (signature, 'Invented signature', 'signature'),
        (button, 'Yes', 'boolean'),
        (text, '\u6f22', 'character'),
        (text, 'x' * 500, 'overflow'),
    ):
        with pytest.raises(ValueError, match=message):
            render_feasibility_pdf(source, inventory, {target['id']: value})


def test_explicit_mirroring_and_independent_changes_are_distinct():
    source = synthetic_form()
    inventory = inspect_pdf(source, pages=(1,))
    a, b = [t for t in inventory['targets'] if t['qualified_name'] == 'duplicate']
    for first, second in [('MIRRORED', 'MIRRORED'), ('INDEPENDENT', 'MIRRORED')]:
        output = render_feasibility_pdf(source, inventory, {a['id']: first, b['id']: second})
        text = pypdf.PdfReader(BytesIO(output)).pages[0].extract_text()
        assert text.count('MIRRORED') == (2 if first == second else 1)
        assert text.count('INDEPENDENT') == (0 if first == second else 1)


@pytest.mark.skipif(not shutil.which('pdftoppm'), reason='Geometry proof requires Poppler')
@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_rotated_crop_preview_matches_actual_mark_pixels(tmp_path, rotation):
    from pypdf.generic import NameObject, NumberObject
    from PIL import Image, ImageChops
    writer = pypdf.PdfWriter()
    writer.clone_document_from_reader(pypdf.PdfReader(BytesIO(synthetic_form())))
    writer.pages[0].cropbox.lower_left = (20, 30)
    writer.pages[0][NameObject('/Rotate')] = NumberObject(rotation)
    stream = BytesIO(); writer.write(stream)
    source = stream.getvalue()
    inventory = inspect_pdf(source, pages=(1,))
    target = next(t for t in inventory['targets'] if t['kind'] == 'checkbox')
    for name, value in [('off', False), ('on', True)]:
        path = tmp_path / f'{name}.pdf'
        path.write_bytes(render_feasibility_pdf(source, inventory, {target['id']: value}))
        subprocess.run(['pdftoppm', '-cropbox', '-r', '72', '-singlefile', '-png', str(path), str(tmp_path / name)],
                       check=True, capture_output=True, timeout=10)
    with Image.open(tmp_path / 'off.png') as a, Image.open(tmp_path / 'on.png') as b:
        bbox = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox()
    assert bbox is not None
    x0, y0, x1, y1 = target['preview_rect']
    assert x0 - 1 <= bbox[0] <= bbox[2] <= x1 + 1
    assert y0 - 1 <= bbox[1] <= bbox[3] <= y1 + 1


@pytest.mark.skipif(not shutil.which('pdftoppm'), reason='Poppler raster comparison requires pdftoppm')
def test_checked_preset_does_not_survive_and_each_location_is_independent(tmp_path):
    from PIL import Image, ImageChops
    source = synthetic_form()
    inventory = inspect_pdf(source, pages=(1,))
    target = next(t for t in inventory['targets'] if t['kind'] == 'checkbox')
    for name, values in [('blank', {}), ('off', {target['id']: False}), ('on', {target['id']: True})]:
        path = tmp_path / f'{name}.pdf'
        path.write_bytes(render_feasibility_pdf(source, inventory, values))
        subprocess.run(['pdftoppm', '-scale-to', '792', '-singlefile', '-png', str(path), str(tmp_path / name)],
                       check=True, capture_output=True, timeout=20)
    blank, off, on = [Image.open(tmp_path / f'{name}.png').convert('RGB') for name in ('blank','off','on')]
    assert ImageChops.difference(blank, off).getbbox() is None
    box = ImageChops.difference(off, on).getbbox()
    assert box is not None
    assert box[0] >= 100 and box[2] <= 114
    assert box[1] >= 792 - 634 and box[3] <= 792 - 620
