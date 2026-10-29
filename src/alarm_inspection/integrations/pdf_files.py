"""Immutable private blobs under the existing application upload volume."""
from hashlib import sha256
import os
from pathlib import Path
import re
import tempfile

from alarm_inspection.domain.pdf_integrations import FileRef, RecordId, valid_blob_key
from pydantic import TypeAdapter


class PrivatePdfFiles:
    def __init__(self, root: Path, *, max_bytes=64 * 1024**2):
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes

    @staticmethod
    def template_key(integration_key, version_id, filename):
        TypeAdapter(RecordId).validate_python(version_id)
        if integration_key not in {'nfpa72', 'compliance'} or filename not in {'original.pdf', 'normalized.pdf'}:
            raise ValueError('Invalid template key.')
        return f'_pdf_integrations/{integration_key}/{version_id}/{filename}'

    @staticmethod
    def artifact_key(inspection_id, artifact_id):
        TypeAdapter(RecordId).validate_python(artifact_id)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', inspection_id): raise ValueError('Invalid inspection ID.')
        return f'{inspection_id}/form_exports/{artifact_id}/document.pdf'

    def _path(self, key, *, create=False):
        if not isinstance(key, str) or not valid_blob_key(key): raise ValueError('Invalid private object key.')
        if create: self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        current = self.root
        for part in key.split('/')[:-1]:
            current = current / part
            if current.is_symlink(): raise ValueError('Symlink in private file path.')
            if create: current.mkdir(mode=0o700, exist_ok=True)
        result = current / key.split('/')[-1]
        if result.is_symlink(): raise ValueError('Symlink in private file path.')
        return result

    def put(self, key, data: bytes) -> FileRef:
        if not isinstance(data, bytes) or len(data) > self.max_bytes: raise ValueError('Private blob size limit exceeded.')
        destination = self._path(key, create=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.pending-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            # Atomic no-replacement publication on the same filesystem.
            os.link(temporary, destination)
            if hasattr(os, 'O_DIRECTORY'):
                descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
            return FileRef(key=key, sha256=sha256(data).hexdigest(), size=len(data))
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)

    def read(self, receipt: FileRef) -> bytes:
        receipt = FileRef.model_validate(receipt.model_dump())
        path = self._path(receipt.key)
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream: data = stream.read(self.max_bytes + 1)
        if len(data) > self.max_bytes or len(data) != receipt.size or sha256(data).hexdigest() != receipt.sha256:
            raise ValueError('Private blob integrity/hash mismatch.')
        return data


    def record_intake(self, original: FileRef, metadata: dict):
        """One private immutable intake diagnostic beside its original upload."""
        from alarm_inspection.domain.pdf_integrations import canonical_json
        if not original.key.endswith('/original.pdf'): raise ValueError('An original template is required.')
        path = self._path(original.key).with_name('intake.json')
        encoded = canonical_json(metadata).encode()
        if len(encoded) > 4 * 1024**2: raise ValueError('Intake diagnostics limit exceeded.')
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
