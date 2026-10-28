"""Private offline feasibility command; deliberately unavailable over HTTP."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from alarm_inspection.integrations.pdf_inventory import inspect_pdf
from alarm_inspection.integrations.pdf_renderer import render_feasibility_pdf


def _write_private(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)


def _pages(value):
    try:
        if '-' in value:
            start, end = map(int, value.split('-'))
            if not 1 <= start <= end <= 50:
                raise ValueError
            return tuple(range(start, end + 1))
        return (int(value),)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use one page or an ascending range such as 1-4.') from exc


def run_probe(source: Path, output_dir: Path, *, pages: tuple[int, ...],
              values: dict[str, object] | None = None, previews=False) -> dict:
    """Write private inventory/diagnostics and a watermarked vector derivative.

    The output directory must not already exist, preventing accidental overwrite.
    Inventory contains original values/defaults and must stay out of Git/logs.
    """
    if previews and not shutil.which('pdftoppm'):
        raise ValueError('Page previews require the local Poppler pdftoppm tool.')
    started = time.perf_counter()
    with source.open('rb') as stream:
        data = stream.read(40 * 1024 * 1024 + 1)
    inventory = inspect_pdf(data, pages=pages)
    inspected = time.perf_counter()
    pdf = render_feasibility_pdf(data, inventory, values or {})
    rendered = time.perf_counter()
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    _write_private(output_dir / 'inventory.json', json.dumps(inventory, indent=2).encode())
    _write_private(output_dir / 'feasibility.pdf', pdf)
    if previews:
        # Render only the sanitized derivative; never open scripts in the source.
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(output_dir / 'feasibility.pdf'),
                        str(output_dir / 'page')], check=True, capture_output=True, timeout=60)
        for path in output_dir.glob('page-*.png'):
            path.chmod(0o600)
    counts = {str(page): sum(t['page'] == page for t in inventory['targets']) for page in pages}
    report = {
        'purpose': 'FEASIBILITY ONLY - NOT AN INSPECTION REPORT',
        'source_sha256': inventory['source_sha256'], 'source_bytes': len(data),
        'source_pages': inventory['source_page_count'], 'selected_pages': list(pages),
        'widgets_per_page': counts, 'widget_count': len(inventory['targets']),
        'parser_warning_count': sum(d['code'] == 'PARSER_WARNING' for d in inventory['diagnostics']),
        'duplicate_name_group_count': sum(d['code'] == 'DUPLICATE_FIELD_NAME' for d in inventory['diagnostics']),
        'has_active_content': inventory['has_active_content'],
        'output_sha256': sha256(pdf).hexdigest(), 'output_bytes': len(pdf),
        'inspection_seconds': round(inspected - started, 3),
        'render_seconds': round(rendered - inspected, 3),
        'total_seconds': round(time.perf_counter() - started, 3),
    }
    try:
        import resource
        # Process-lifetime high-water mark, not a per-document allocation count.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report['process_peak_rss_bytes'] = peak if sys.platform == 'darwin' else peak * 1024
    except ImportError:  # Windows has no stdlib resource module.
        report['process_peak_rss_bytes'] = None
    _write_private(output_dir / 'report.json', json.dumps(report, indent=2).encode())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline private PDF integration feasibility probe.')
    parser.add_argument('source', type=Path)
    parser.add_argument('--pages', required=True, type=_pages)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--values-json', type=Path, help='Optional private target-ID-to-probe-value JSON object.')
    parser.add_argument('--previews', action='store_true', help='Rasterize the sanitized output with local Poppler.')
    args = parser.parse_args(argv)
    try:
        values = json.loads(args.values_json.read_text()) if args.values_json else {}
        if not isinstance(values, dict):
            raise ValueError('Probe values must be a JSON object.')
        report = run_probe(args.source, args.output_dir, pages=args.pages, values=values, previews=args.previews)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        # Do not print supplied values or raw parser errors to the terminal.
        parser.exit(1, f'Probe failed ({type(exc).__name__}); check private inputs and output directory.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
