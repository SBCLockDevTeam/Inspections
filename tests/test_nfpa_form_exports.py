"""The selected form controls frozen NFPA PDF answers, names and history."""
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
import pytest
from pypdf import PdfReader, PdfWriter
from test_pdf_integration_admin import admin_api
from test_pdf_integration_storage import database
from test_pdf_integration_simple import save, text_target
from test_pdf_integration_exports import proof
from pdf_storage_fixtures import template_bytes
from alarm_inspection.storage import NfpaForm, InspectionTask, InspectionChecklistDecision
from alarm_inspection.nfpa_forms import selected_form
from alarm_inspection.integrations import pdf_exports as exports


def test_nfpa_forms_have_separate_pdfs_and_readiness(admin_api):
    client,store,files,inspection=admin_api
    writer=PdfWriter()
    for _ in range(4): writer.add_page(PdfReader(BytesIO(template_bytes())).pages[0])
    stream=BytesIO();writer.write(stream)
    response=client.post('/api/admin/integrations/nfpa72/templates',files={'file':('four.pdf',stream.getvalue())})
    assert response.status_code==200,response.text
    draft=response.json();target=text_target(draft)
    second=str(uuid4())
    with store.begin() as session:
        task=session.get(InspectionTask,'task');task.section='nfpa72'
        session.add(NfpaForm(id=second,inspection_id=inspection,name='Fuel station',category='Gas Station',created_by='tech',created_at=datetime.now(timezone.utc)))
    response=save(client,draft,[{'target_id':target['id'],'disposition':'source','source':{'kind':'checklist','id':'task'},'required':True}])
    assert response.status_code==200,response.text
    config=response.json()['config']
    original=exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech')
    token=selected_form.set(second)
    try:
        with pytest.raises(exports.ExportBlocked): exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech')
        with store.begin() as session:
            session.add(InspectionChecklistDecision(id=str(uuid4()),inspection_id=inspection,task_id='task',task_text='Synthetic task',nfpa_form_id=second,value='Yes',completed=True,decided_by='tech',decided_at=datetime.now(timezone.utc)))
        context=exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech')
        assert context.source_fingerprint!=original.source_fingerprint
        preview=exports.preview(store,inspection,'nfpa72',exports.PreviewRequest(expected_version_id=config['version_id'],expected_source_fingerprint=context.source_fingerprint),files=files,actor_id='tech')
        final=exports.confirm(store,inspection,'nfpa72',proof(preview),files=files,actor_id='tech')
        data,_=exports.download(store,inspection,'nfpa72',final['id'],files=files,actor_id='tech')
        assert 'Yes' in PdfReader(BytesIO(data)).pages[0].extract_text()
        assert 'Fuel station-Gas Station' in final['filename']
        assert len(exports.history(store,inspection,'nfpa72',actor_id='tech')['exports'])==1
    finally: selected_form.reset(token)
    assert exports.history(store,inspection,'nfpa72',actor_id='tech')['exports']==[]
    with pytest.raises(ValueError): exports.download(store,inspection,'nfpa72',final['id'],files=files,actor_id='tech')
    assert exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech').source_fingerprint==original.source_fingerprint
