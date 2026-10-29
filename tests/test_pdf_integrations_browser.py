"""Additive admin and technician journeys in real Chromium, using synthetic PDFs."""
import asyncio
import os
import socket
import threading
import time
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
import uvicorn
from playwright import async_api as playwright
from pdf_storage_fixtures import template_bytes

pytestmark=pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS')!='1',reason='Opt-in real browser tests')


@pytest.fixture
def browser_app(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "browser.db"}')
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED','true')
    from alarm_inspection.api.routers import admin_integrations,inspection_form_integrations
    monkeypatch.setattr(admin_integrations,'UPLOAD_ROOT',tmp_path/'private')
    monkeypatch.setattr(inspection_form_integrations,'UPLOAD_ROOT',tmp_path/'private')
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store,User,Inspection
    app=create_app();store=open_store();ident=str(uuid4())
    with store.begin() as session:
        session.query(User).one().force_password_reset=False
        session.add(Inspection(id=ident,store_number='PDFTEST',city='Norfolk',state='VA',address='Test',start_date=date(2026,10,1),completion_date=date(2026,10,2),created_at=datetime.now(timezone.utc)))
    client=TestClient(app)
    assert client.post('/api/auth/login',json={'email':'john.porter@securitybuildingcontrols.com','password':'TestBootstrapPassword42!'}).status_code==200
    draft=client.post('/api/admin/integrations/compliance/templates',files={'file':('synthetic.pdf',template_bytes())}).json()
    config=draft['config'];config.update(applicability='no_panel',applicability_reason='Reviewed synthetic scope',signature_policy='later_signing',supplemental_policy='not_applicable')
    config['manual_inputs']=[dict(id='remarks',label='Remarks',meaning='Inspection defects',type='text',required=True)]
    config['mappings']=[dict(target_id=t['id'],disposition='sign_later' if t['kind']=='signature' else 'blank',reason='Reviewed blank') for t in config['inventory']['targets']]
    response=client.put('/api/admin/integrations/versions/'+draft['id'],json={'config':config,'expected_revision':1})
    assert response.status_code==200,response.text
    draft=response.json()
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and time.monotonic()<deadline:time.sleep(.01)
    assert server.started
    try:yield f'http://127.0.0.1:{sock.getsockname()[1]}',client,store,ident,draft
    finally:server.should_exit=True;thread.join(timeout=10);sock.close()


async def login(page,base):
    await page.goto(base)
    await page.fill('#login-email','john.porter@securitybuildingcontrols.com')
    await page.fill('#login-password','TestBootstrapPassword42!')
    await page.locator('#login-form button').click()
    await playwright.expect(page.locator('#home-screen')).to_be_visible()


def test_admin_exact_targets_conflicts_and_publication(browser_app):
    base,client,store,inspection,draft=browser_app
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                await page.add_init_script("Object.defineProperty(window.crypto,'randomUUID',{value:undefined})")
                await login(page,base)
                await page.locator('#avatar-button').click(button='right');await page.click('#avatar-menu-option-admin')
                for tab in ('panel-types','inspection-tasks','users','integrations'):
                    await page.click('#admin-tab-'+tab)
                    await playwright.expect(page.locator('#admin-panel-'+tab)).to_be_visible()
                await playwright.expect(page.locator('#integration-cards section')).to_have_count(2)
                await page.select_option('select[aria-label="Compliance inspection versions"]',draft['id'])
                await page.locator('#integration-cards section').filter(has=page.get_by_role('heading',name='Compliance inspection',exact=True)).get_by_role('button',name='Open version',exact=True).click()
                await playwright.expect(page.locator('#integration-editor h4')).to_be_visible()
                targets=draft['config']['inventory']['targets']
                duplicates=[t for t in targets if t['same_name_targets']]
                assert len(duplicates)>=2
                for zoom in ('0.5','1','2'):
                    await page.select_option('#integration-zoom',zoom)
                    target=duplicates[1]
                    rect=page.locator(f'#integration-sheet button[aria-label^="Page 1 occurrence {target["occurrence"]} "]')
                    await rect.click()
                    assert await page.locator('#integration-editor h4').inner_text()==f'Selected p1 occurrence {target["occurrence"]}'
                    box=await rect.bounding_box();sheet=await page.locator('#integration-sheet').bounding_box()
                    geometry=draft['config']['inventory']['pages'][0]
                    assert abs((box['x']-sheet['x'])-target['preview_rect'][0]*float(zoom))<2
                await page.locator('#integration-targets button').first.focus();await page.keyboard.press('Enter')
                await page.fill('#integration-label','Private unsaved label')
                # A concurrent save must not replace this browser's local edit.
                changed=client.get('/api/admin/integrations').json()['integrations'][0]['versions'][0]
                changed['config']['applicability_reason']='Concurrent administrative review'
                assert client.put('/api/admin/integrations/versions/'+draft['id'],json={'config':changed['config'],'expected_revision':2}).status_code==200
                await page.wait_for_timeout(3300)
                assert await page.input_value('#integration-label')=='Private unsaved label'
                await page.click('#integration-save')
                await playwright.expect(page.locator('#integration-message')).to_contain_text('Conflict')
                assert await page.input_value('#integration-label')=='Private unsaved label'
                page.once('dialog',lambda d:d.accept());await page.click('#integration-reload')
                await page.select_option('#integration-sample',inspection);await page.click('#integration-load-catalog')
                await page.locator(f'#integration-targets button[data-target="{duplicates[0]["id"]}"]').click()
                await page.select_option('#integration-disposition','source')
                source=await page.locator('#integration-source option').evaluate_all("options => options.find(o => o.value && JSON.parse(o.value).field === 'store_number').value")
                await page.select_option('#integration-source',source)
                await page.click('#integration-save')
                await playwright.expect(page.locator('#integration-message')).to_contain_text('Draft saved')
                await page.click('#integration-test')
                await playwright.expect(page.locator('#integration-message')).to_contain_text('Test complete',timeout=30000)
                for target in targets:
                    await page.locator(f'#integration-targets button[data-target="{target["id"]}"]').click()
                    await page.get_by_role('button',name='Verify selected target in current test',exact=True).click()
                await page.fill('#integration-summary','Reviewed all synthetic locations and states')
                page.once('dialog',lambda d:d.accept());await page.click('#integration-publish')
                await playwright.expect(page.locator('#integration-message')).to_contain_text('published and activated',timeout=10000)
                assert client.get('/api/admin/integrations').json()['integrations'][0]['versions'][0]['status']=='published'
                await page.set_viewport_size({'width':390,'height':844})
                assert await page.locator('#integration-editor').is_visible()
                assert not errors
            finally:await browser.close()
    asyncio.run(check())


def publish_browser_form(client,inspection,draft,manual_inputs=None):
    path='/api/admin/integrations/versions/'+draft['id']
    if manual_inputs:
        config=draft['config'];config['manual_inputs']=manual_inputs
        response=client.put(path,json={'config':config,'expected_revision':draft['revision']})
        assert response.status_code==200,response.text
        draft=response.json()
    test=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':draft['revision']})
    assert test.status_code==200,test.text
    test=test.json()
    response=client.post(path+'/publish',json={'inspection_id':inspection,'expected_revision':draft['revision'],'integration_revision':1,
        'test_artifact_id':test['test_artifact_id'],'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Synthetic browser fixture review'})
    assert response.status_code==200,response.text
    assert client.post('/api/admin/integrations/compliance/state',json={'expected_revision':2,'enabled':True}).status_code==200
    return response.json()


def test_technician_two_devices_private_edits_failure_recovery_and_readiness(browser_app):
    base,client,store,inspection,draft=browser_app
    publish_browser_form(client,inspection,draft,[dict(id='remarks',label='Remarks',meaning='Defects',type='text',required=True),
        dict(id='quantity',label='Quantity',meaning='Measured quantity',type='number',minimum=0,unit='devices',required=True),
        dict(id='outcome',label='Outcome',meaning='Actual outcome',type='yes_no_na',required=True)])
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);contexts=[await browser.new_context() for _ in range(2)]
            a,b=[await context.new_page() for context in contexts];errors=[]
            try:
                for page in (a,b):
                    page.on('pageerror',lambda e:errors.append(str(e)));await login(page,base)
                    await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                    await page.locator('#export-form-details-section summary').click()
                    await playwright.expect(page.locator('[data-form="compliance"] [data-answer]')).to_have_count(3)
                selector='#form-detail-compliance-remarks-inspection'
                await a.fill(selector,'Private device A draft')
                await b.fill(selector,'Saved on B');await b.locator('[data-form="compliance"] h3').click()
                await playwright.expect(b.locator('#form-details-message')).to_contain_text('saved')
                await a.wait_for_timeout(3300)
                assert await a.input_value(selector)=='Private device A draft'
                await a.locator('[data-form="compliance"] h3').click()
                await playwright.expect(a.locator('#form-details-message')).to_contain_text('Conflict')
                assert await a.input_value(selector)=='Private device A draft'
                a.once('dialog',lambda d:d.accept())
                await a.get_by_role('button',name='Review current saved answers and definitions',exact=True).last.click()
                await playwright.expect(a.locator(selector)).to_have_value('Saved on B')
                # A failed save retains the text; retry succeeds after recovery.
                await a.route('**/form-integrations/compliance/answers',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Synthetic save failure"}'))
                await a.fill(selector,'Retained during failure');await a.locator('[data-form="compliance"] h3').click()
                await playwright.expect(a.locator('#form-details-message')).to_contain_text('Synthetic save failure')
                await a.wait_for_timeout(3300)
                assert await a.input_value(selector)=='Retained during failure'
                await a.unroute('**/form-integrations/compliance/answers')
                await a.get_by_role('button',name='Save / confirm Remarks',exact=True).click()
                await playwright.expect(a.locator('#form-details-message')).to_contain_text('saved')
                await b.locator('[data-form="compliance"] h3').click()
                await playwright.expect(b.locator(selector)).to_have_value('Retained during failure',timeout=12000)
                await a.fill('#form-detail-compliance-quantity-inspection','0')
                await a.locator('[data-form="compliance"] h3').click()
                await a.select_option('#form-detail-compliance-outcome-inspection','No')
                await playwright.expect(a.locator('[data-form="compliance"] .pdf-form-summary')).to_contain_text('Saved data ready',timeout=12000)
                assert await a.locator('[data-form="compliance"] .pdf-export-action').is_disabled()
                assert await a.locator('#save-all-inspection').is_enabled()
                # A saved source change makes overrides stale and remains visible.
                view=(await a.request.get(base+f'/api/inspections/{inspection}/form-integrations/compliance')).json()
                view=await view
                original=next(e for e in view['catalog']['entries'] if e['source']['field']=='store_number')
                await a.get_by_text('Override a saved source (requires a reason)',exact=True).first.click()
                source=a.get_by_label('Original source for Remarks')
                value=await source.locator('option').evaluate_all("options => options.find(o => o.value && JSON.parse(o.value).source.field === 'store_number').value")
                await source.select_option(value);await a.get_by_label('Override reason for Remarks').fill('Reviewed on site')
                await a.get_by_role('button',name='Save override for Remarks',exact=True).click()
                await playwright.expect(a.locator('[data-input-key="remarks:"] .pdf-field-status')).to_contain_text('Override')
                response=await a.request.patch(base+f'/api/inspections/{inspection}',data={'store_number':'SOURCE-CHANGED'})
                assert response.status==200
                await playwright.expect(a.locator('[data-form="compliance"] .pdf-readiness-blockers')).to_contain_text('Override',timeout=12000)
                await a.set_viewport_size({'width':390,'height':844})
                assert await a.locator(selector).is_visible()
                assert not errors
            finally:await browser.close()
    asyncio.run(check())


def test_technician_explicit_scope_navigation_and_definition_changes(browser_app):
    from alarm_inspection.storage import PointList
    from alarm_inspection.integrations.pdf_models import InspectionFormDecision
    base,client,store,inspection,draft=browser_app
    with store.begin() as session:
        session.add(PointList(id='explicit-panel',inspection_id=inspection,category='Fire',filename='synthetic.xlsx',path='synthetic',accepted_at=datetime.now(timezone.utc)))
    config=draft['config'];config.update(applicability='panel',categories=['Fire'])
    config['manual_inputs'][0]['scope']='panel'
    draft=client.put('/api/admin/integrations/versions/'+draft['id'],json={'config':config,'expected_revision':2}).json()
    publish_browser_form(client,inspection,draft)
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);page=await browser.new_page()
            try:
                await login(page,base);await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                await page.locator('#export-form-details-section summary').click()
                card=page.locator('[data-form="compliance"]')
                await playwright.expect(card.locator('[data-answer]')).to_have_count(0)
                await card.locator('[data-scope-panel="explicit-panel"]').check()
                await card.get_by_role('button',name='Save explicit panel scope',exact=True).click()
                await playwright.expect(card.locator('[data-answer]')).to_have_count(1)
                control=card.locator('[data-answer]');await control.fill('Saved panel answer');await control.press('Enter')
                await playwright.expect(page.locator('#form-details-message')).to_contain_text('saved')
                # An unrelated tab/navigation retains a private unsaved override draft.
                await card.locator('summary').click()
                await card.get_by_label('Override reason for Remarks').fill('Private reason, not submitted')
                await page.click('#home-link-from-inspection')
                await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                await playwright.expect(card.get_by_label('Override reason for Remarks')).to_have_value('Private reason, not submitted')
                # Publish a different question under the same stable ID; earlier decisions survive.
                copied=client.post('/api/admin/integrations/versions/'+draft['id']+'/copy').json()
                new=copied['config'];new['manual_inputs'][0]['meaning']='Changed question requiring explicit review'
                updated=client.put('/api/admin/integrations/versions/'+copied['id'],json={'config':new,'expected_revision':1}).json()
                test=client.post('/api/admin/integrations/versions/'+copied['id']+'/test',json={'inspection_id':inspection,'expected_revision':2,'panel_ids':['explicit-panel']}).json()
                result=client.post('/api/admin/integrations/versions/'+copied['id']+'/publish',json={'inspection_id':inspection,'panel_ids':['explicit-panel'],'expected_revision':2,'integration_revision':3,
                    'test_artifact_id':test['test_artifact_id'],'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Reviewed changed question'})
                assert result.status_code==200,result.text
                await playwright.expect(card.locator('.pdf-form-summary')).to_contain_text('definitions or panel scope changed',timeout=12000)
                page.once('dialog',lambda d:d.accept())
                await card.get_by_role('button',name='Review current saved answers and definitions',exact=True).click()
                await playwright.expect(card.locator('.pdf-field-status')).to_contain_text('definition changed',timeout=12000)
                await playwright.expect(card.locator('[data-answer]')).to_have_value('Saved panel answer')
                with store() as session:assert session.query(InspectionFormDecision).count()==1
            finally:await browser.close()
    asyncio.run(check())


def test_slow_integration_refresh_does_not_delay_existing_entry_sync(browser_app):
    base,client,store,inspection,draft=browser_app
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);page=await browser.new_page()
            started=asyncio.Event();release=asyncio.Event();finished=asyncio.Event()
            async def delayed(route):
                started.set()
                try:
                    await release.wait()
                    await route.fulfill(status=503,content_type='application/json',body='{"error":"Integration temporarily unavailable"}')
                finally:finished.set()
            try:
                await login(page,base);await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                await playwright.expect(page.locator('[data-form="compliance"]')).to_have_count(1)
                await page.route('**/form-integrations',delayed)
                await asyncio.wait_for(started.wait(),timeout=8)
                assert client.patch(f'/api/inspections/{inspection}',json={'address':'Saved while integration is slow'}).status_code==200
                await playwright.expect(page.locator('#inspection-address')).to_have_value('Saved while integration is slow',timeout=5000)
                assert await page.locator('#save-all-inspection').is_enabled()
            finally:
                release.set()
                if started.is_set():await asyncio.wait_for(finished.wait(),timeout=3)
                await browser.close()
    asyncio.run(check())


def test_technician_preview_stale_confirmation_final_download_and_history(browser_app,tmp_path):
    from io import BytesIO
    from pypdf import PdfReader
    base,client,store,inspection,draft=browser_app
    config=draft['config'];config['filename_policy']='completion_date_panel_id'
    text_target=next(t for t in config['inventory']['targets'] if t['kind']=='text')
    config['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'remarks'},required=True) if m['target_id']==text_target['id'] else m for m in config['mappings']]
    draft=client.put('/api/admin/integrations/versions/'+draft['id'],json={'config':config,'expected_revision':2}).json()
    publish_browser_form(client,inspection,draft)
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                await page.add_init_script("Object.defineProperty(window.crypto,'randomUUID',{value:undefined})")
                await login(page,base);await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                await page.locator('#export-form-details-section summary').click()
                await page.fill('#form-detail-compliance-remarks-inspection','Saved negative result: No')
                await page.locator('[data-form="compliance"] h3').click()
                export=page.get_by_role('button',name='Export Compliance Form',exact=True)
                await playwright.expect(export).to_be_enabled(timeout=12000)
                await export.click();await playwright.expect(page.locator('.pdf-export-dialog')).to_be_visible(timeout=12000)
                iframe=page.locator('.pdf-export-dialog iframe')
                response=await page.request.get(base+await iframe.get_attribute('src'))
                assert 'DRAFT PREVIEW' in PdfReader(BytesIO(await response.body())).pages[0].extract_text()
                assert client.patch(f'/api/inspections/{inspection}',json={'address':'Changed after preview'}).status_code==200
                await page.get_by_role('button',name='Confirm and download completed PDF',exact=True).click()
                await playwright.expect(page.locator('.pdf-export-dialog [role="status"]')).to_contain_text('changed',timeout=12000)
                await page.get_by_role('button',name='Close preview',exact=True).click()
                await page.wait_for_timeout(3300)
                await export.click();await playwright.expect(page.locator('.pdf-export-dialog')).to_be_visible(timeout=12000)
                async with page.expect_download(timeout=15000) as event:
                    await page.get_by_role('button',name='Confirm and download completed PDF',exact=True).click()
                download=await event.value;path=tmp_path/'completed.pdf';await download.save_as(path)
                final=PdfReader(path);text=final.pages[0].extract_text()
                assert 'Saved negative result: No' in text and 'DRAFT PREVIEW' not in text and 'OLD PRESET' not in text
                await playwright.expect(page.locator('[data-form="compliance"] .pdf-export-history')).to_contain_text('ready')
                assert download.suggested_filename=='PDFTEST-Norfolk,VA-Compliance Inspection-10-02-26.pdf'
                assert not errors
            finally:await browser.close()
    asyncio.run(check())


def test_missing_integration_asset_does_not_break_existing_inspection_entry(browser_app):
    base,client,store,inspection,draft=browser_app
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                await page.route('**/integrations.js',lambda route:route.abort())
                await login(page,base);await page.select_option('#inspection-picker',inspection);await page.click('#open-inspection')
                await playwright.expect(page.locator('#inspection-screen')).to_be_visible()
                await page.fill('#inspection-address','Saved without the optional PDF asset');await page.locator('#inspection-name').click()
                await playwright.expect(page.locator('#inspection-message')).to_contain_text('saved',timeout=12000)
                assert client.get(f'/api/inspections/{inspection}').json()['address']=='Saved without the optional PDF asset'
                assert not errors
            finally:await browser.close()
    asyncio.run(check())
