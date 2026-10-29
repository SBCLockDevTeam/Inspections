"""Enforce resource limits outside the application's API process."""
import sys
from pathlib import Path

import pytest

pytest.importorskip('pypdf')
pytest.importorskip('reportlab')
pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Bounded feasibility worker currently requires Linux')

from pdf_integration_fixtures import synthetic_form
from alarm_inspection.integrations.pdf_probe_limits import (
    ProbeExecutionError, ProbeLimits, run_bounded_probe, _run_process,
)


def test_bounded_worker_produces_private_proof_with_limits(tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(synthetic_form())
    output = tmp_path / 'proof'
    report = run_bounded_probe(source, output, pages=(1, 2))
    assert report['widget_count'] == 6
    assert report['execution_limits']['memory_mib'] == 512
    assert (output / 'manifest.json').exists()


def test_wall_timeout_terminates_worker():
    with pytest.raises(ProbeExecutionError, match='wall time'):
        _run_process([sys.executable, '-c', 'import time; time.sleep(10)'],
                     wall_seconds=.1)


def test_memory_limit_is_enforced_in_child():
    code = (
        'from alarm_inspection.integrations.pdf_probe_limits import ProbeLimits, apply_limits; '
        'apply_limits(ProbeLimits(memory_mib=96)); bytearray(512 * 1024 * 1024)'
    )
    with pytest.raises(ProbeExecutionError, match='failed'):
        _run_process([sys.executable, '-c', code], wall_seconds=5)


def test_cpu_limit_is_enforced_in_child():
    code = (
        'from alarm_inspection.integrations.pdf_probe_limits import ProbeLimits, apply_limits; '
        'apply_limits(ProbeLimits(cpu_seconds=1))\nwhile True: pass'
    )
    with pytest.raises(ProbeExecutionError, match='failed'):
        _run_process([sys.executable, '-c', code], wall_seconds=5)


def test_file_limit_is_enforced_in_child(tmp_path):
    path = tmp_path / 'bounded-file'
    code = (
        'import sys; from alarm_inspection.integrations.pdf_probe_limits import ProbeLimits, apply_limits; '
        'apply_limits(ProbeLimits(file_mib=1)); open(sys.argv[1], "wb").write(b"x" * (2 * 1024**2))'
    )
    with pytest.raises(ProbeExecutionError, match='failed'):
        _run_process([sys.executable, '-c', code, str(path)], wall_seconds=5)
    assert path.stat().st_size <= 1024**2


def test_timeout_also_terminates_descendants(tmp_path):
    pidfile = tmp_path / 'child-pid'
    code = (
        'import pathlib,subprocess,sys,time; '
        'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]); '
        'pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)'
    )
    with pytest.raises(ProbeExecutionError, match='wall time'):
        _run_process([sys.executable, '-c', code, str(pidfile)], wall_seconds=.5)
    proc = Path('/proc') / pidfile.read_text() / 'stat'
    # A killed orphan may remain a zombie until the host's init reaps it.
    try:
        state = proc.read_text().split()[2]
    except FileNotFoundError:
        state = None  # init may reap it between process termination and this read.
    assert state in (None, 'Z')


def test_worker_failure_does_not_publish_output_or_alter_source(tmp_path):
    source = tmp_path / 'source.pdf'
    data = synthetic_form()
    source.write_bytes(data)
    output = tmp_path / 'proof'
    with pytest.raises(ProbeExecutionError):
        run_bounded_probe(source, output, pages=(1,), expected_sha256='0' * 64)
    assert not output.exists()
    assert source.read_bytes() == data


@pytest.mark.parametrize('limits', [dict(wall_seconds=0), dict(memory_mib=0), dict(cpu_seconds=-1)])
def test_invalid_limits_fail_before_launch(limits):
    with pytest.raises(ValueError):
        ProbeLimits(**limits)
