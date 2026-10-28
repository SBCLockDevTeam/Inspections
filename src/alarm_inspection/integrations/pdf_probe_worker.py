"""Internal worker: set process limits before reading a source PDF."""
import json
from pathlib import Path
import sys

from alarm_inspection.integrations.pdf_probe_limits import ProbeLimits, apply_limits


def main():
    with Path(sys.argv[1]).open('rb') as stream:
        encoded = stream.read(2 * 1024**2 + 1)
    if len(encoded) > 2 * 1024**2:
        raise ValueError('Probe request exceeds its size limit.')
    request = json.loads(encoded)
    limits = ProbeLimits(**request.pop('limits'))
    apply_limits(limits)
    from alarm_inspection.integrations.pdf_probe import run_probe
    request['source'] = Path(request['source'])
    request['output_dir'] = Path(request['output_dir'])
    request['pages'] = tuple(request['pages'])
    report = run_probe(**request, execution_limits={
        'wall_seconds': limits.wall_seconds, 'cpu_seconds': limits.cpu_seconds,
        'memory_mib': limits.memory_mib, 'file_mib': limits.file_mib,
        'total_output_mib': limits.total_output_mib,
    })
    print(json.dumps(report))


if __name__ == '__main__':
    main()
