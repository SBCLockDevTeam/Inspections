"""Private tooling is repeatable and never overwrites an existing proof."""
import json
import os
import stat
import sys
from hashlib import sha256

import pytest

pytest.importorskip('pypdf')
pytest.importorskip('reportlab')

from pdf_integration_fixtures import synthetic_form
from alarm_inspection.integrations.pdf_probe import main, run_probe


def test_probe_keeps_private_files_and_does_not_overwrite(tmp_path):
    source = tmp_path / 'source.pdf'
    data = synthetic_form()
    source.write_bytes(data)
    output = tmp_path / 'private-proof'
    report = run_probe(source, output, pages=(1, 2))
    assert report['widget_count'] == 6
    assert report['widgets_per_page'] == {'1': 5, '2': 1}
    assert report == json.loads((output / 'report.json').read_text())
    assert (output / 'original.pdf').read_bytes() == data
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['source_sha256'] == sha256(data).hexdigest()
    assert manifest['output_sha256'] == sha256((output / 'feasibility.pdf').read_bytes()).hexdigest()
    assert len(manifest['target_correspondence']) == 6
    assert {t['source_page'] for t in manifest['target_correspondence']} == {1, 2}
    assert source.read_bytes() == data
    if os.name == 'posix':
        assert stat.S_IMODE(output.stat().st_mode) == 0o700
        assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in output.iterdir())
    previous = (output / 'feasibility.pdf').read_bytes()
    with pytest.raises(FileExistsError):
        run_probe(source, output, pages=(1,))
    assert (output / 'feasibility.pdf').read_bytes() == previous


@pytest.mark.skipif(sys.platform != 'linux', reason='Bounded CLI currently requires Linux')
def test_cli_only_prints_summary_not_original_answers(tmp_path, capsys):
    source = tmp_path / 'source.pdf'
    source.write_bytes(synthetic_form())
    main([str(source), '--pages', '1-2', '--output-dir', str(tmp_path / 'proof')])
    output = capsys.readouterr().out
    assert json.loads(output)['widget_count'] == 6
    assert 'OLD PRESET' not in output and 'duplicate-key-marker' not in output


def test_probe_fails_before_output_on_unknown_target(tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(synthetic_form())
    output = tmp_path / 'proof'
    with pytest.raises(ValueError, match='target'):
        run_probe(source, output, pages=(1,), values={'unknown': 'bad'})
    assert not output.exists()


def test_expected_source_fingerprint_rejects_replacement(tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(synthetic_form())
    output = tmp_path / 'proof'
    with pytest.raises(ValueError, match='fingerprint'):
        run_probe(source, output, pages=(1,), expected_sha256='0' * 64)
    assert not output.exists()
