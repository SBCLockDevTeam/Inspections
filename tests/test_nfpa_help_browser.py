"""Phone-sized help authoring, popup return, and multiple NFPA forms."""
import asyncio
import os
import socket
import threading
import time
import pytest
uvicorn = pytest.importorskip('uvicorn')
playwright = pytest.importorskip('playwright.async_api')
pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in browser regression')


def test_mobile_help_and_independent_forms(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "mobile.db"}')
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store, User
    app=create_app()
    with open_store().begin() as session: session.query(User).one().force_password_reset=False
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and time.monotonic()<deadline: time.sleep(.01)
    assert server.started

    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox'],executable_path=os.getenv('INSPECTIONS_TEST_CHROMIUM'))
            try:
                page=await browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                base=f'http://127.0.0.1:{sock.getsockname()[1]}'
                await page.goto(base)
                await page.fill('#login-email','john.porter@securitybuildingcontrols.com');await page.fill('#login-password','TestBootstrapPassword42!');await page.locator('#login-form button').click()
                await playwright.expect(page.locator('#home-screen')).to_be_visible()
                response=await page.request.post(base+'/api/inspections/blank',data={'store_number':'MOBILE','address':'Test','city':'Norfolk','state':'VA','start_date':'2026-10-01','completion_date':'2026-10-02'})
                ident=(await response.json())['id']
                response=await page.request.post(base+'/api/admin/inspection-tasks',data={'text':'Panel model','section':'nfpa72','input_type':'textbox'})
                task=(await response.json())['task']['id'];control=f'#checklist-task-{task}'
                await page.locator('#avatar-button').click();await page.click('#avatar-menu-option-admin');await page.click('#admin-tab-help')
                await playwright.expect(page.locator('#admin-panel-help')).to_contain_text('Panel model')
                row=page.locator('.help-admin-row').filter(has_text='Panel model')
                await row.get_by_role('button',name='Configure help').click()
                dialog=page.locator('dialog.field-help-dialog[open]')
                await dialog.locator('textarea').fill('Read the model from the panel label.');await dialog.locator('input[type=checkbox]').check()
                import base64
                await dialog.locator('input[type=file]').set_input_files({'name':'label.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGvQAAAAASUVORK5CYII=')})
                await playwright.expect(dialog.get_by_role('status')).to_contain_text('Media uploaded')
                video = await page.evaluate("""async () => {
                    const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;
                    const ctx=canvas.getContext('2d');const stream=canvas.captureStream(10);
                    const recorder=new MediaRecorder(stream,{mimeType:'video/webm'});const chunks=[];
                    recorder.ondataavailable=e=>chunks.push(e.data);
                    const stopped=new Promise(resolve=>recorder.onstop=resolve);recorder.start();
                    const timer=setInterval(()=>{ctx.fillStyle='navy';ctx.fillRect(0,0,160,90);ctx.fillStyle='white';ctx.fillText('Help video',20,40);},50);
                    await new Promise(resolve=>setTimeout(resolve,700));recorder.stop();await stopped;clearInterval(timer);stream.getTracks().forEach(t=>t.stop());
                    return Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer()));
                }""")
                await dialog.locator('input[type=file]').set_input_files({'name':'instruction.webm','mimeType':'video/webm','buffer':bytes(video)})
                await playwright.expect(dialog.locator('video')).to_have_count(1)
                await dialog.get_by_role('button',name='Save help',exact=True).click()
                await playwright.expect(dialog).to_have_count(0)
                await page.click('#back-home-from-admin');await page.click('#refresh-inspections');await page.select_option('#inspection-picker',ident);await page.click('#open-inspection')
                await page.fill(control,'Original panel');await page.locator(control).press('Tab')
                await playwright.expect(page.locator('#checklist-message')).to_contain_text('saved')
                await page.get_by_role('button',name='Help: Panel model:',exact=True).click()
                popup=page.locator('dialog.field-help-dialog[open]')
                await playwright.expect(popup).to_contain_text('Read the model')
                await playwright.expect(popup.locator('img')).to_be_visible()
                assert await popup.evaluate('(d)=>{const r=d.getBoundingClientRect();return r.left >= 0 && r.right <= 390;}')
                await popup.locator('video').evaluate('(v)=>v.play()')
                await page.wait_for_function('document.querySelector("dialog[open] video").currentTime > 0')
                await page.screenshot(path=str(tmp_path/'help-popup.png'))
                await popup.get_by_role('button',name='Close',exact=True).click()
                await playwright.expect(page.locator(control)).to_have_value('Original panel')
                await page.click('#add-nfpa-form');await page.fill('#nfpa-form-name','Fuel station');await page.select_option('#nfpa-form-category','Gas Station');await page.locator('#new-nfpa-form button[type=submit]').click()
                await playwright.expect(page.locator('#new-nfpa-form-dialog')).not_to_be_visible()
                await playwright.expect(page.locator(control)).to_have_value('')
                await page.fill(control,'Fuel panel');await page.locator(control).press('Tab');await playwright.expect(page.locator('#checklist-message')).to_contain_text('saved')
                second=await page.locator('#nfpa-form-selector').input_value()
                await page.select_option('#nfpa-form-selector','');await playwright.expect(page.locator(control)).to_have_value('Original panel')
                await page.select_option('#nfpa-form-selector',second);await playwright.expect(page.locator(control)).to_have_value('Fuel panel')
                await page.screenshot(path=str(tmp_path/'mobile.png'),full_page=True)
                assert errors == []
            finally: await browser.close()
    try: asyncio.run(check())
    finally: server.should_exit=True;thread.join(timeout=5);sock.close()
