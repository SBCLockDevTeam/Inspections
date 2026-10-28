"""Administration choice editing and captured values across independent devices."""
import asyncio
import json
import os
import socket
import threading
import time

import pytest

uvicorn = pytest.importorskip('uvicorn')
playwright = pytest.importorskip('playwright.async_api')
pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in browser regression')


def test_admin_choices_and_typed_checklist_values_sync(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'typed-browser.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store, User, InspectionChecklistDecision
    app = create_app()
    with open_store().begin() as session: session.query(User).one().force_password_reset = False
    sock = socket.socket(); sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True); thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline: time.sleep(0.01)
    assert server.started

    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                base = f'http://127.0.0.1:{sock.getsockname()[1]}'
                pages = [await browser.new_page() for _ in range(3)]
                a, b, c = pages; errors = []
                for page in pages:
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    await page.goto(base); await page.fill('#login-email', 'john.porter@securitybuildingcontrols.com'); await page.fill('#login-password', 'TestBootstrapPassword42!')
                    await page.locator('#login-form button').click()
                    await playwright.expect(page.locator('#home-screen')).to_be_visible()
                response = await a.request.post(base+'/api/inspections/blank', data={'store_number':'TYPED','address':'Test','city':'Norfolk','state':'VA','start_date':'2026-10-01','completion_date':'2026-10-02'})
                inspection_id = (await response.json())['id']
                await a.locator('#avatar-button').click(button='right'); await a.click('#avatar-menu-option-admin'); await a.click('#admin-tab-inspection-tasks')
                for label, kind in [('Restore system','checkbox'),('Panel serial','textbox'),('Condition','dropdown')]:
                    await a.fill('#inspection-task-text',label); await a.select_option('#inspection-task-type',kind)
                    if kind == 'dropdown':
                        choices = a.locator('#inspection-task-options .task-option-input')
                        await choices.nth(0).fill('Ready'); await a.locator('#inspection-task-options .add-task-choice').click(); await choices.nth(1).fill('Remove me')
                        await a.locator('#inspection-task-options .remove-task-choice').nth(1).click()
                        await a.locator('#inspection-task-options .add-task-choice').click(); await choices.nth(1).fill('Needs repair')
                        await playwright.expect(a.locator('#inspection-task-options .move-task-choice-up').first).to_be_disabled()
                        await playwright.expect(a.locator('#inspection-task-options .move-task-choice-down').last).to_be_disabled()
                        await a.locator('#inspection-task-options .move-task-choice-up').last.click()
                        assert await choices.evaluate_all('(inputs)=>inputs.map(el=>el.value)') == ['Needs repair','Ready']
                        await a.locator('#inspection-task-options .move-task-choice-down').first.click()
                    await a.click('#add-inspection-task'); await playwright.expect(a.locator('#inspection-tasks-message')).to_have_text('Task added.')
                tasks = (await (await a.request.get(base+'/api/admin/inspection-tasks')).json())['tasks']
                ids = {task['text']:task['id'] for task in tasks}
                assert next(task for task in tasks if task['text']=='Condition')['options'] == ['Ready','Needs repair']
                for page in (b,c):
                    await page.click('#refresh-inspections'); await page.select_option('#inspection-picker',inspection_id); await page.click('#open-inspection')
                    await playwright.expect(page.locator('#inspection-screen')).to_be_visible()
                text = f'#checklist-task-{ids["Panel serial"]}'; dropdown = f'#checklist-task-{ids["Condition"]}'; checkbox = f'#checklist-task-{ids["Restore system"]}-yes'
                await b.locator(checkbox).check(); await b.fill(text,'SN-0042'); await b.locator(text).press('Tab')
                await b.select_option(dropdown,'Ready'); await b.locator('#inspection-name').click()
                await playwright.expect(c.locator(text)).to_have_value('SN-0042',timeout=12000)
                await playwright.expect(c.locator(dropdown)).to_have_value('Ready',timeout=12000)
                await playwright.expect(c.locator(checkbox)).to_be_checked(timeout=12000)
                choices = f'#checklist-task-{ids["Restore system"]}'
                await playwright.expect(b.locator('.task-checkbox-choices input')).to_have_count(3)
                assert await b.locator('.task-checkbox-choices label').all_text_contents() == ['Yes', 'No', 'NA']
                # Each answer replaces the previous one and synchronizes to other devices.
                await c.locator(choices+'-no').check()
                await playwright.expect(b.locator(choices+'-no')).to_be_checked(timeout=12000)
                await playwright.expect(b.locator(checkbox)).not_to_be_checked()
                await c.locator(choices+'-na').focus(); await c.locator(choices+'-na').press('Space')
                await playwright.expect(b.locator(choices+'-na')).to_be_checked(timeout=12000)
                await playwright.expect(b.locator(choices+'-no')).not_to_be_checked()
                await playwright.expect(b.locator('#checklist-progress')).to_have_text('3 of 3 complete')
                await c.locator(choices+'-na').uncheck()
                await playwright.expect(b.locator('.task-checkbox-choices input:checked')).to_have_count(0,timeout=12000)
                await playwright.expect(b.locator('#checklist-progress')).to_have_text('2 of 3 complete')
                await b.locator(checkbox).check()
                await playwright.expect(c.locator(checkbox)).to_be_checked(timeout=12000)
                # Failed saves restore the last saved selection and keep the boxes usable.
                async def reject_checkbox(route):
                    await route.fulfill(status=422,json={'detail':'Test save failure'})
                await b.route('**/checklist/'+ids['Restore system'],reject_checkbox)
                await b.locator(choices+'-no').check()
                await playwright.expect(b.locator('#checklist-message')).to_have_text('Test save failure')
                await playwright.expect(b.locator(checkbox)).to_be_checked()
                await playwright.expect(b.locator(choices+'-no')).not_to_be_checked()
                await playwright.expect(b.locator(checkbox)).to_be_enabled()
                await b.unroute('**/checklist/'+ids['Restore system'],reject_checkbox)
                await c.fill(text,'Private draft')
                await b.fill(text,'Shared value'); await b.locator(text).press('Tab')
                await asyncio.sleep(3.5)
                await playwright.expect(c.locator(text)).to_have_value('Private draft')
                # Header Save flushes the local text before reopening the inspection.
                await c.click('#save-all-inspection')
                await playwright.expect(b.locator(text)).to_have_value('Private draft',timeout=12000)
                # Returning to administration must not expose stale rows during its request.
                await a.click('#back-home-from-admin')
                await a.locator('#avatar-button').click(button='right'); await a.click('#avatar-menu-option-admin')
                async def delayed_tasks(route):
                    await asyncio.sleep(0.4)
                    await route.continue_()
                await a.route('**/api/admin/inspection-tasks', delayed_tasks)
                await a.click('#admin-tab-inspection-tasks')
                await playwright.expect(a.locator('#inspection-tasks-body')).to_contain_text('Loading inspection tasks...')
                row = a.locator(f'tr[data-task-id="{ids["Condition"]}"]')
                await row.locator('.move-task-choice-up').last.click()
                await asyncio.sleep(3.5)
                assert await row.locator('.task-option-input').evaluate_all('(inputs)=>inputs.map(el=>el.value)') == ['Needs repair','Ready']
                await row.locator('td').last.locator('button').click()
                await playwright.expect(a.locator('#inspection-tasks-message')).to_have_text('Task updated.')
                await playwright.expect(b.locator(dropdown+' option')).to_have_text(['Select...','Needs repair','Ready'],timeout=12000)
                await playwright.expect(c.locator(dropdown)).to_have_value('Ready')
                with open_store()() as session:
                    answer = session.query(InspectionChecklistDecision).filter_by(task_id=ids['Condition']).one()
                    assert answer.value == 'Ready' and json.loads(answer.options_json) == ['Ready','Needs repair']
                # Persisted order survives reopening administration.
                await a.click('#back-home-from-admin')
                await a.locator('#avatar-button').click(button='right'); await a.click('#avatar-menu-option-admin'); await a.click('#admin-tab-inspection-tasks')
                await playwright.expect(row.locator('.task-option-input').first).to_have_value('Needs repair')
                await row.locator('.remove-task-choice').last.click(); await row.locator('.add-task-choice').click(); await row.locator('.task-option-input').last.fill('Not tested')
                await row.locator('td').last.locator('button').click()
                await playwright.expect(a.locator('#inspection-tasks-message')).to_have_text('Task updated.')
                await b.locator('#inspection-name').click()
                await playwright.expect(b.locator(dropdown+' option:checked')).to_have_text('Ready (removed choice)',timeout=12000)
                await b.select_option(dropdown,'Not tested'); await b.locator('#inspection-name').click()
                await playwright.expect(c.locator(dropdown)).to_have_value('Not tested',timeout=12000)
                await c.reload(); await playwright.expect(c.locator('#home-screen')).to_be_visible(); await c.select_option('#inspection-picker',inspection_id); await c.click('#open-inspection')
                await playwright.expect(c.locator(text)).to_have_value('Private draft')
                await playwright.expect(c.locator(dropdown)).to_have_value('Not tested')
                await playwright.expect(c.locator(checkbox)).to_be_checked()
                await c.set_viewport_size({'width':390,'height':1000})
                assert await c.locator('#checklist-section').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
                assert errors == []
            finally: await browser.close()
    try: asyncio.run(check())
    finally: server.should_exit = True; thread.join(timeout=5); sock.close()
