"""Resource-bounded PDF operations. No PDF actions or scripts are executed."""
import json
from pathlib import Path
import sys

from alarm_inspection.integrations.pdf_probe_limits import ProbeLimits, apply_limits


def main():
    apply_limits(ProbeLimits())
    request = json.loads(Path(sys.argv[1]).read_text())
    source = Path(request['source']).read_bytes()
    from alarm_inspection.integrations.pdf_inventory import inspect_pdf
    inventory = inspect_pdf(source, pages=tuple(request['pages']))
    output = Path(request['output'])
    if request['operation'] == 'inventory':
        output.write_text(json.dumps(inventory))
        return
    from alarm_inspection.integrations.pdf_renderer import render_diagnostic_pdf
    data = render_diagnostic_pdf(source, inventory, request.get('targets', {}))
    if request['operation'] == 'page':
        import subprocess
        pdf = output.with_suffix('.pdf'); pdf.write_bytes(data)
        subprocess.run(['pdftoppm', '-f', str(request['page']), '-singlefile', '-scale-to', '1600', '-png',
                        str(pdf), str(output.with_suffix(''))], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    else:
        output.write_bytes(data)


if __name__ == '__main__': main()
