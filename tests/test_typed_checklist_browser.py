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
                await playwright.expect(a.locator('#admin-tab-inspection-tasks')).to_have_text('Data Sections')
                for label, kind in [('Restore system','checkbox'),('Panel serial','textbox'),('Condition','dropdown'),('Store contact','textbox')]:
                    section = 'nfpa72' if label=='Panel serial' else 'store_data' if label=='Store contact' else 'compliance'
                    group = a.locator(f'.admin-data-section[data-section="{section}"]')
                    await group.locator('.add-data-task').click()
                    draft = group.locator('tbody tr').last
                    await draft.locator('.admin-task-text').fill(label); await draft.locator('.admin-task-type').select_option(kind)
                    if kind == 'dropdown':
                        choices = draft.locator('.task-option-input')
                        await choices.nth(0).fill('Ready'); await draft.locator('.add-task-choice').click(); await choices.nth(1).fill('Remove me')
                        await draft.locator('.remove-task-choice').nth(1).click()
                        await draft.locator('.add-task-choice').click(); await choices.nth(1).fill('Needs repair')
                        await playwright.expect(draft.locator('.move-task-choice-up').first).to_be_disabled()
                        await playwright.expect(draft.locator('.move-task-choice-down').last).to_be_disabled()
                        await draft.locator('.move-task-choice-up').last.click()
                        assert await choices.evaluate_all('(inputs)=>inputs.map(el=>el.value)') == ['Needs repair','Ready']
                        await draft.locator('.move-task-choice-down').first.click()
                    await draft.locator('.save-data-task').click(); await playwright.expect(a.locator('#inspection-tasks-message')).to_have_text('Task added.')
                tasks = (await (await a.request.get(base+'/api/admin/inspection-tasks')).json())['tasks']
                ids = {task['text']:task['id'] for task in tasks}
                assert next(task for task in tasks if task['text']=='Condition')['options'] == ['Ready','Needs repair']
                for page in (b,c):
                    await page.click('#refresh-inspections'); await page.select_option('#inspection-picker',inspection_id); await page.click('#open-inspection')
                    await playwright.expect(page.locator('#inspection-screen')).to_be_visible()
                assert await b.locator(f'#export-form-details-section #checklist-task-{ids["Panel serial"]}').count()==1
                assert await b.locator(f'#checklist-section #checklist-task-{ids["Panel serial"]}').count()==0
                store_contact=f'#checklist-task-{ids["Store contact"]}'
                assert await b.locator('#store-data-section '+store_contact).count()==1
                await b.fill(store_contact,'Store contact value');await b.locator(store_contact).press('Tab')
                await playwright.expect(c.locator(store_contact)).to_have_value('Store contact value',timeout=12000)
                assert await b.locator('#inspection-store-number').input_value()=='TYPED'
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
                await playwright.expect(b.locator('#checklist-progress')).to_have_text('2 of 2 complete')
                await c.locator(choices+'-na').uncheck()
                await playwright.expect(b.locator('.task-checkbox-choices input:checked')).to_have_count(0,timeout=12000)
                await playwright.expect(b.locator('#checklist-progress')).to_have_text('1 of 2 complete')
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
                await playwright.expect(a.locator('#inspection-tasks-message')).to_contain_text('Loading inspection tasks...')
                row = a.locator(f'tr[data-task-id="{ids["Condition"]}"]')
                await row.locator('.move-task-choice-up').last.click()
                await asyncio.sleep(3.5)
                assert await row.locator('.task-option-input').evaluate_all('(inputs)=>inputs.map(el=>el.value)') == ['Needs repair','Ready']
                await row.locator('.save-data-task').click()
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
                await row.locator('.save-data-task').click()
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


def test_data_sections_defaults_drag_delete_and_private_edits(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'sections-browser.db'}")
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
                page = await browser.new_page(); errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(base); await page.fill('#login-email', 'john.porter@securitybuildingcontrols.com'); await page.fill('#login-password', 'TestBootstrapPassword42!')
                await page.locator('#login-form button').click(); await playwright.expect(page.locator('#home-screen')).to_be_visible()
                inspection = (await (await page.request.post(base+'/api/inspections/blank', data={'store_number':'DEFAULTS','address':'Test','city':'Norfolk','state':'VA','start_date':'2026-10-01','completion_date':'2026-10-02'})).json())['id']
                await page.locator('#avatar-button').click(button='right'); await page.click('#avatar-menu-option-admin'); await page.click('#admin-tab-inspection-tasks')
                assert await page.locator('.admin-data-section > summary > span').all_text_contents() == ['Store Data','NFPA 72','Compliance']
                assert await page.locator('#inspection-task-section,.admin-task-order').count() == 0
                group = page.locator('.admin-data-section[data-section="nfpa72"]')
                await group.locator('summary').click(); assert not await group.get_attribute('open')
                # Add in a collapsed heading opens the section and appends an editable row.
                await group.locator('.add-data-task').click()
                draft = group.locator('tbody tr').last
                await draft.locator('.admin-task-text').fill('Panel condition')
                await draft.locator('.admin-task-type').select_option('dropdown')
                await draft.locator('.task-option-input').fill('Ready')
                await draft.locator('.add-task-choice').click(); await draft.locator('.task-option-input').last.fill('Repair')
                await draft.locator('.admin-task-default').select_option('Ready')
                await draft.locator('.save-data-task').click(); await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task added.')
                for name, value in [('First check','NA'),('Second check','Yes'),('Third check','No')]:
                    await group.locator('.add-data-task').click(); row = group.locator('tbody tr').last
                    await row.locator('.admin-task-text').fill(name)
                    assert await row.locator('.admin-task-default option').all_text_contents() == ['None','Yes','No','NA']
                    await row.locator('.admin-task-default').select_option(value)
                    await row.locator('.save-data-task').click(); await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task added.')
                tasks = (await (await page.request.get(base+'/api/admin/inspection-tasks')).json())['tasks']; ids = {task['text']: task['id'] for task in tasks}
                first = group.locator(f'tr[data-task-id="{ids["First check"]}"]')
                second = group.locator(f'tr[data-task-id="{ids["Second check"]}"]')
                third = group.locator(f'tr[data-task-id="{ids["Third check"]}"]')
                # Saving one row must preserve private edits in other rows and appended drafts.
                await first.locator('.admin-task-text').fill('Private edited check')
                await group.locator('.add-data-task').click(); draft = group.locator('tbody tr:not([data-task-id])')
                await draft.locator('.admin-task-text').fill('New draft')
                await second.locator('.admin-task-default').select_option('No'); await second.locator('.save-data-task').click()
                await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task updated.')
                await playwright.expect(first.locator('.admin-task-text')).to_have_value('Private edited check')
                await playwright.expect(draft.locator('.admin-task-text')).to_have_value('New draft')
                # Browser drag persists order while retaining both private edits.
                await third.locator('.task-drag-handle').drag_to(first.locator('.task-drag-handle'))
                await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task order saved.')
                ordered = (await (await page.request.get(base+'/api/admin/inspection-tasks')).json())['tasks']
                assert [task['text'] for task in ordered] == ['Panel condition','Third check','First check','Second check']
                await playwright.expect(first.locator('.admin-task-text')).to_have_value('Private edited check')
                await third.locator('.task-drag-handle').focus(); await third.locator('.task-drag-handle').press('Alt+ArrowDown')
                await playwright.expect(group.locator('tbody tr[data-task-id]').nth(2)).to_have_attribute('data-task-id', ids['Third check'])
                # A failed reorder restores the DOM and does not affect private edits.
                async def reject_order(route): await route.fulfill(status=409, json={'detail':'Section order changed on another device.'})
                await page.route('**/inspection-tasks/order', reject_order)
                await third.locator('.task-drag-handle').press('Alt+ArrowUp')
                await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Section order changed on another device.')
                await playwright.expect(group.locator('tbody tr[data-task-id]').nth(2)).to_have_attribute('data-task-id', ids['Third check'])
                await page.unroute('**/inspection-tasks/order', reject_order)
                await draft.locator('.delete-data-task').click()
                await first.locator('.save-data-task').click(); await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task updated.')
                # Delete cancels cleanly, then hides the task but retains its stable definition.
                page.once('dialog', lambda dialog: dialog.dismiss()); await second.locator('.delete-data-task').click(); await playwright.expect(second).to_be_visible()
                page.once('dialog', lambda dialog: dialog.accept()); await second.locator('.delete-data-task').click()
                await playwright.expect(second).to_be_hidden()
                await page.locator('#show-inactive-tasks').check(); await playwright.expect(second).to_be_visible()
                await second.locator('.admin-task-active').check(); await second.locator('.save-data-task').click()
                await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task updated.')
                await page.locator('#show-inactive-tasks').uncheck(); await playwright.expect(second).to_be_visible()
                # A textbox has a free-text default, placed in the correct section.
                store_group = page.locator('.admin-data-section[data-section="store_data"]')
                await store_group.locator('.add-data-task').click(); store_draft = store_group.locator('tbody tr').last
                await store_draft.locator('.admin-task-text').fill('Store contact'); await store_draft.locator('.admin-task-type').select_option('textbox')
                await store_draft.locator('.admin-task-default').fill('Office'); await store_draft.locator('.save-data-task').click()
                await playwright.expect(page.locator('#inspection-tasks-message')).to_have_text('Task added.')
                await page.click('#back-home-from-admin'); await page.click('#refresh-inspections'); await page.select_option('#inspection-picker', inspection); await page.click('#open-inspection')
                await playwright.expect(page.locator(f'#checklist-task-{ids["Panel condition"]}')).to_have_value('Ready')
                await playwright.expect(page.locator(f'#checklist-task-{ids["First check"]}-na')).to_be_checked()
                await playwright.expect(page.locator(f'#checklist-task-{ids["Second check"]}-no')).to_be_checked()
                await playwright.expect(page.locator(f'#checklist-task-{ids["Third check"]}-no')).to_be_checked()
                with open_store()() as session: assert session.query(InspectionChecklistDecision).count() == 0
                # An explicit clear remains cleared on reopening, without changing the default.
                await page.locator(f'#checklist-task-{ids["First check"]}-na').uncheck()
                await playwright.expect(page.locator('#checklist-message')).to_contain_text('saved')
                await page.reload(); await playwright.expect(page.locator('#home-screen')).to_be_visible(); await page.select_option('#inspection-picker', inspection); await page.click('#open-inspection')
                await playwright.expect(page.locator(f'#checklist-task-{ids["First check"]}-na')).not_to_be_checked()
                assert errors == []
            finally: await browser.close()
    try: asyncio.run(check())
    finally: server.should_exit = True; thread.join(timeout=5); sock.close()
