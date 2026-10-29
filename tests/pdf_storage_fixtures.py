"""Synthetic P2 configuration and isolated databases; never production data."""
from io import BytesIO
from uuid import uuid4
from hashlib import sha256

from pypdf import PdfReader, PdfWriter
from pdf_integration_fixtures import synthetic_form
from alarm_inspection.integrations.pdf_inventory import inspect_pdf


def template_bytes():
    writer = PdfWriter(); writer.add_page(PdfReader(BytesIO(synthetic_form())).pages[0])
    stream = BytesIO(); writer.write(stream)
    return stream.getvalue()


def config_data():
    data = template_bytes()
    inventory = inspect_pdf(data, pages=(1,))
    ident = str(uuid4())
    return {
        'schema_version': 1, 'integration_key': 'compliance', 'version_id': ident,
        'original': {'key': f'_pdf_integrations/compliance/{ident}/original.pdf',
                     'sha256': sha256(data).hexdigest(), 'size': len(data)},
        'inventory': inventory,
        'applicability': 'no_panel', 'applicability_reason': 'Synthetic persistence test only',
        'signature_policy': 'later_signing', 'supplemental_policy': 'not_applicable',
        'manual_inputs': [{'id': 'remarks', 'label': 'Remarks', 'meaning': 'Inspection remarks', 'type': 'text'}],
        'mappings': [{'target_id': t['id'], 'disposition': 'sign_later' if t['kind'] == 'signature' else 'blank',
                      'reason': 'Synthetic test only: explicitly blank'} for t in inventory['targets']],
    }
