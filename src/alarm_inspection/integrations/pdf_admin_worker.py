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
    if request['operation'] == 'words':
        import subprocess
        from xml.etree import ElementTree
        xml=output.with_suffix('.xml')
        subprocess.run(['pdftotext','-f',str(request['pages'][0]),'-l',str(request['pages'][-1]),'-bbox-layout',str(Path(request['source'])),str(xml)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        tree=ElementTree.parse(xml);pages={}
        for number,page in zip(request['pages'],tree.findall('.//{*}page')):
            height=float(page.attrib['height']);words=[]
            for word in page.findall('.//{*}word'):
                x=(float(word.attrib['xMin'])+float(word.attrib['xMax']))/2;y=height-(float(word.attrib['yMin'])+float(word.attrib['yMax']))/2
                if any(t['page']==number and t['rect'][0]<=x<=t['rect'][2] and t['rect'][1]<=y<=t['rect'][3] for t in inventory['targets']):continue
                words.append({'x':x,'y':y,'text':word.text or ''})
            pages[number]=words
        output.write_text(json.dumps(pages));return
    if request['operation'] == 'inventory':
        output.write_text(json.dumps(inventory))
        return
    if request['operation'] in {'export_preview','export_final'}:
        from alarm_inspection.integrations.pdf_renderer import render_completed_pdf
        plan=request['targets']
        output.write_bytes(render_completed_pdf(source,plan['config'],plan['values'],preview=request['operation']=='export_preview'))
        return
    from alarm_inspection.integrations.pdf_renderer import render_diagnostic_pdf
    if request['operation'] == 'render_batch':
        from io import BytesIO
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        scenarios = request.get('targets', [])
        if not isinstance(scenarios,list) or not 1 <= len(scenarios) <= 256: raise ValueError('Diagnostic scenario limit exceeded.')
        for scenario in scenarios:
            rendered = render_diagnostic_pdf(source, inventory, scenario)
            for page in PdfReader(BytesIO(rendered)).pages: writer.add_page(page)
        stream = BytesIO(); writer.write(stream); output.write_bytes(stream.getvalue())
        return
    data = render_diagnostic_pdf(source, inventory, request.get('targets', {}))
    if request['operation'] == 'page':
        import subprocess
        pdf = output.with_suffix('.pdf'); pdf.write_bytes(data)
        subprocess.run(['pdftoppm', '-cropbox', '-f', str(request['page']), '-singlefile', '-scale-to', '1600', '-png',
                        str(pdf), str(output.with_suffix(''))], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    else:
        output.write_bytes(data)


if __name__ == '__main__': main()
