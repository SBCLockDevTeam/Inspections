"""Linux process/resource boundary for offline feasibility work, not web intake."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


class ProbeExecutionError(ValueError):
    """The isolated probe failed; no diagnostic output is published."""


@dataclass(frozen=True)
class ProbeLimits:
    wall_seconds: float = 30
    cpu_seconds: int = 20
    memory_mib: int = 512
    file_mib: int = 64
    total_output_mib: int = 128

    def __post_init__(self):
        if (type(self.wall_seconds) not in (int, float) or not math.isfinite(self.wall_seconds)
                or not 0 < self.wall_seconds <= 60):
            raise ValueError('Wall limit must be positive and at most 60 seconds.')
        for name in ('cpu_seconds', 'memory_mib', 'file_mib', 'total_output_mib'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be a positive integer.')


def apply_limits(limits: ProbeLimits):
    """Called inside a fresh worker before PDF libraries or content are loaded."""
    if sys.platform != 'linux':
        raise ProbeExecutionError('The bounded feasibility worker currently requires Linux.')
    import resource
    for kind, soft, hard in (
        (resource.RLIMIT_AS, limits.memory_mib * 1024**2, limits.memory_mib * 1024**2),
        (resource.RLIMIT_CPU, limits.cpu_seconds, limits.cpu_seconds + 1),
        (resource.RLIMIT_FSIZE, limits.file_mib * 1024**2, limits.file_mib * 1024**2),
        (resource.RLIMIT_CORE, 0, 0),
    ):
        resource.setrlimit(kind, (soft, hard))


def _run_process(command, *, wall_seconds):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        stdout, _ = process.communicate(timeout=wall_seconds)
    except BaseException as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise ProbeExecutionError('Probe wall time limit exceeded.') from exc
        raise
    if process.returncode:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        raise ProbeExecutionError('Probe worker failed or exceeded a resource limit.')
    if len(stdout) > 64 * 1024:
        raise ProbeExecutionError('Probe worker summary exceeded its limit.')
    return stdout


def run_bounded_probe(source: Path, output_dir: Path, *, pages: tuple[int, ...],
                      values=None, previews=False, expected_sha256=None,
                      limits: ProbeLimits | None = None) -> dict:
    """Publish only a successful private worker result; never overwrite output.

    Resource bounds do not sandbox filesystem/network access. There is still no
    HTTP entry point. Source content and request values are not sent to stdout.
    """
    if sys.platform != 'linux':
        raise ProbeExecutionError('The bounded feasibility worker currently requires Linux.')
    limits = limits or ProbeLimits()
    source, output_dir = Path(source).resolve(), Path(output_dir).absolute()
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pdf-probe-', dir=output_dir.parent) as temporary:
        staging = Path(temporary)
        request = {'source': str(source), 'output_dir': str(staging / 'proof'),
                   'pages': list(pages), 'values': values, 'previews': previews,
                   'expected_sha256': expected_sha256, 'limits': asdict(limits)}
        encoded = json.dumps(request).encode()
        if len(encoded) > 2 * 1024**2:
            raise ProbeExecutionError('Probe request exceeds its size limit.')
        request_path = staging / 'request.json'
        fd = os.open(request_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
        raw = _run_process([sys.executable, '-m', 'alarm_inspection.integrations.pdf_probe_worker',
                            str(request_path)], wall_seconds=limits.wall_seconds)
        report = json.loads(raw)
        files = sorted((staging / 'proof').iterdir(), key=lambda path: path.name == 'report.json')
        if (any(not path.is_file() or path.is_symlink() for path in files)
                or sum(path.stat().st_size for path in files) > limits.total_output_mib * 1024**2):
            raise ProbeExecutionError('Probe output exceeds its size limit.')
        output_dir.mkdir(mode=0o700, exist_ok=False)
        published = []
        try:
            # Same-filesystem hard links fail on collisions; unlike rename they
            # cannot silently overwrite an existing file. Publish report last.
            for path in files:
                destination = output_dir / path.name
                os.link(path, destination)
                published.append(destination)
        except BaseException:
            for path in published:
                path.unlink()
            output_dir.rmdir()
            raise
        return report
