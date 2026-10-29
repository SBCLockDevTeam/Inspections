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
    from alarm_inspection.api.routers import admin_integrations
    monkeypatch.setattr(admin_integrations,'UPLOAD_ROOT',tmp_path/'private')
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
