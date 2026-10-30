"""Two independent sessions must converge without losing local drafts."""
import asyncio
import io
import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip('fastapi')
pytest.importorskip('sqlalchemy')
uvicorn = pytest.importorskip('uvicorn')
playwright = pytest.importorskip('playwright.async_api')
pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in browser regression')


def test_shared_changes_reach_other_sessions_without_reloading(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'sync.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store, User, Inspection, PointList, PointListDecision, InspectionTask
    app = create_app()
    inspection_id, list_id, point_id, task_id = (str(uuid4()) for _ in range(4))
    with open_store().begin() as session:
        session.query(User).one().force_password_reset = False
        session.add(Inspection(id=inspection_id, store_number='SYNC', address='Original', city='Norfolk', state='VA', inspector_name='Original inspector', start_date=datetime(2026, 10, 1).date(), completion_date=datetime(2026, 10, 2).date(), created_at=datetime.now(timezone.utc)))
        session.add(PointList(id=list_id, inspection_id=inspection_id, category='Fire', filename='test.xlsx', path='/tmp/test.xlsx', accepted_at=datetime.now(timezone.utc)))
        session.add(PointListDecision(id=point_id, inspection_id=inspection_id, point_list_id=list_id, address=1, text='Smoke', location='Lobby', accepted=True, deleted=False))
        session.add(InspectionTask(id=task_id, text='Notify station', text_key='notify station', position=1, active=True, created_at=datetime.now(timezone.utc)))
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
                contexts = [await browser.new_context() for _ in range(2)]
                a, b = [await context.new_page() for context in contexts]
                errors = []
                for page in (a, b):
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    await page.goto(base)
                    await page.fill('#login-email', 'john.porter@securitybuildingcontrols.com')
                    await page.fill('#login-password', 'TestBootstrapPassword42!')
                    await page.locator('#login-form button').click()
                    await playwright.expect(page.locator('#home-screen')).to_be_visible()
                    await page.select_option('#inspection-picker', inspection_id); await page.click('#open-inspection')
                    await playwright.expect(page.locator('#inspection-screen')).to_be_visible()
                cell_a = a.locator('.device-type-cell'); cell_b = b.locator('.device-type-cell')
                async with a.expect_response(lambda r: '/highlight' in r.url and r.request.method == 'PATCH'):
                    await cell_a.dblclick()
                await playwright.expect(cell_b).to_have_attribute('aria-pressed', 'true', timeout=12000)
                # Missing event evidence turns the shared green marker yellow; a later match clears it.
                from openpyxl import Workbook
                async def upload_history(point):
                    book = Workbook(); book.active.append(['Date', 'Zone', 'State']); book.active.append([datetime(2026,10,1,10), point, 'A'])
                    data = io.BytesIO(); book.save(data)
                    response = await a.request.post(base + f'/api/inspections/{inspection_id}/event-history', multipart={'point_list_id': list_id, 'event_file': {'name': 'history.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'buffer': data.getvalue()}})
                    assert response.ok and (await response.json()).get('status') == 'matched'
                await upload_history(99)
                await playwright.expect(cell_b).to_have_css('background-color', 'rgb(255, 243, 191)', timeout=12000)
                await upload_history(1)
                await playwright.expect(cell_b).to_have_css('background-color', 'rgb(234, 247, 233)', timeout=12000)
                await playwright.expect(b.locator('#accepted-points-body tr td').nth(3)).to_contain_text('(pending)', timeout=12000)
                # A local draft survives, while another field and the marker still update.
                await b.click('#edit-table'); await cell_b.locator('input').fill('Unsaved local device')
                await b.set_viewport_size({'width': 390, 'height': 900})
                region = b.locator('#points-table-scroll')
                assert await region.evaluate('(el) => el.scrollWidth > el.clientWidth')
                await region.evaluate('(el) => { el.scrollLeft = el.scrollWidth; }')
                last_input = b.locator('#accepted-points-body tr td').nth(3).locator('input')
                edge = await region.bounding_box(); last = await last_input.bounding_box()
                assert last['x'] >= edge['x'] and last['x'] + last['width'] <= edge['x'] + edge['width'] + 1
                await last_input.focus(); await last_input.press('End')
                assert await b.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
                await b.set_viewport_size({'width': 1280, 'height': 900})

                await a.request.patch(base + f'/api/inspections/{inspection_id}', data={'address': 'Changed remotely'})
                await playwright.expect(b.locator('#inspection-address')).to_have_value('Changed remotely', timeout=12000)
                await playwright.expect(b.locator('#inspection-inspector')).to_have_value('Original inspector')
                async with a.expect_response(lambda r: '/highlight' in r.url and r.request.method == 'PATCH'):
                    await cell_a.dblclick()
                await playwright.expect(cell_b).to_have_attribute('aria-pressed', 'false', timeout=12000)
                await playwright.expect(cell_b.locator('input')).to_have_value('Unsaved local device')
                await a.request.post(base + f'/api/inspections/{inspection_id}/accepted-points/save', data={'point_list_id': list_id, 'rows': [{'id': point_id, 'address': '1', 'text': 'Smoke', 'location': 'Remote location', 'event_date': ''}]})
                await playwright.expect(b.locator('#accepted-points-body tr td').nth(2).locator('input')).to_have_value('Remote location', timeout=12000)
                await playwright.expect(cell_b.locator('input')).to_have_value('Unsaved local device')
                await a.locator('#inspection-checklist input[data-checklist-choice="Yes"]').check()
                await playwright.expect(b.locator('#inspection-checklist input[data-checklist-choice="Yes"]')).to_be_checked(timeout=12000)
                await b.locator('#inspection-checklist input[data-checklist-choice="Yes"]').uncheck()
                await playwright.expect(a.locator('#inspection-checklist input[data-checklist-choice="Yes"]')).not_to_be_checked(timeout=12000)
                # Store Data only sends the local field; remote address and inspector survive.
                await b.fill('#inspection-city', 'Roanoke'); await b.locator('#inspection-city').dispatch_event('change')
                await playwright.expect(a.locator('#inspection-city')).to_have_value('Roanoke', timeout=12000)
                persisted = await a.request.get(base + f'/api/inspections/{inspection_id}')
                assert (await persisted.json())['inspector_name'] == 'Original inspector'
                # A dropped connection catches up automatically after reconnect.
                await b.route('**/api/**', lambda route: route.abort())
                async with a.expect_response(lambda r: '/highlight' in r.url and r.request.method == 'PATCH'):
                    await cell_a.dblclick()
                await playwright.expect(b.locator('#live-sync-status')).to_contain_text('Retrying', timeout=12000)
                await b.unroute('**/api/**')
                await playwright.expect(cell_b).to_have_attribute('aria-pressed', 'true', timeout=12000)
                # Remote deletion leaves no stale editable inspection on another device.
                await a.request.delete(base + f'/api/inspections/{inspection_id}')
                await playwright.expect(b.locator('#home-screen')).to_be_visible(timeout=12000)
                await playwright.expect(b.locator('#home-message')).to_contain_text('deleted on another device')
                created = await a.request.post(base + '/api/inspections/blank', data={'store_number': 'NEW-SYNC', 'address': 'Test', 'city': 'Norfolk', 'state': 'VA', 'start_date': '2026-10-01', 'completion_date': '2026-10-02'})
                created_id = (await created.json())['id']
                await playwright.expect(b.locator(f'#inspection-picker option[value="{created_id}"]')).to_have_count(1, timeout=12000)
                await b.select_option('#inspection-picker', created_id); await b.click('#open-inspection')
                await playwright.expect(b.locator('#accepted-points-body')).to_contain_text('No accepted points')
                from openpyxl import Workbook
                workbook = Workbook(); workbook.active.append(['Point', 'Description']); workbook.active.append([2, 'New shared point'])
                upload = io.BytesIO(); workbook.save(upload)
                added = await a.request.post(base + f'/api/inspections/{created_id}/point-lists', multipart={'point_list_category': 'Fire', 'point_decisions': json.dumps([{'address': 2, 'text': 'New shared point', 'accepted': True}]), 'points_file': {'name': 'shared.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'buffer': upload.getvalue()}})
                assert added.ok
                await playwright.expect(b.locator('.device-type-cell')).to_have_text('New shared point', timeout=12000)
                async with b.expect_response(lambda r: '/highlight' in r.url and r.request.method == 'PATCH') as response:
                    await b.locator('.device-type-cell').dblclick()
                assert (await response.value).ok
                await b.click('#home-link-from-inspection')
                await b.locator('#avatar-button').click(button='right'); await b.click('#avatar-menu-option-admin')
                await b.click('#admin-tab-panel-types')
                await a.request.post(base + '/api/admin/panel-types', data={'name': 'Shared panel'})
                await playwright.expect(b.locator('#panel-types-body')).to_contain_text('Shared panel', timeout=12000)
                await b.click('#admin-tab-inspection-tasks')
                await a.request.post(base + '/api/admin/inspection-tasks', data={'text': 'Shared new task'})
                await playwright.expect(b.locator('#inspection-tasks-body tr[data-task-id]:not([data-task-id^="builtin:"]) .admin-task-text')).to_have_count(2, timeout=12000)
                assert errors == []
            finally: await browser.close()
    try: asyncio.run(check())
    finally:
        server.should_exit = True; thread.join(timeout=5); sock.close()
