from uuid import uuid4
import os
import stat

import pytest

from alarm_inspection.integrations.pdf_files import PrivatePdfFiles


def test_immutable_atomic_private_blobs_and_hash_checked_reads(tmp_path):
    files = PrivatePdfFiles(tmp_path / 'private')
    key = files.template_key('compliance', str(uuid4()), 'original.pdf')
    receipt = files.put(key, b'SYNTHETIC PDF BYTES')
    assert files.read(receipt) == b'SYNTHETIC PDF BYTES'
    with pytest.raises(FileExistsError): files.put(key, b'replacement')
    assert files.read(receipt) == b'SYNTHETIC PDF BYTES'
    if os.name == 'posix': assert stat.S_IMODE((files.root / key).stat().st_mode) == 0o600
    (files.root / key).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash|integrity'): files.read(receipt)


@pytest.mark.parametrize('key', ['../secret', '/etc/passwd', 'x/../../secret', 'uploads/secret.pdf',
                                '_pdf_integrations/compliance/not-an-id/original.pdf'])
def test_arbitrary_paths_are_rejected(tmp_path, key):
    with pytest.raises(ValueError): PrivatePdfFiles(tmp_path).put(key, b'anything')


def test_symlink_parent_cannot_escape_and_size_limits_fail_without_artifact(tmp_path):
    root = tmp_path / 'private'; root.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    (root / '_pdf_integrations').symlink_to(outside, target_is_directory=True)
    files = PrivatePdfFiles(root)
    key = files.template_key('compliance', str(uuid4()), 'original.pdf')
    with pytest.raises(ValueError): files.put(key, b'no escape')
    assert list(outside.iterdir()) == []
    files = PrivatePdfFiles(tmp_path / 'other', max_bytes=2)
    with pytest.raises(ValueError): files.put(key, b'too large')
    assert not list(files.root.rglob('*.pdf'))
