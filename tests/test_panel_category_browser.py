"""Explicit category changes preserve private table edits and survive reopening."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import login
from test_panel_types import panel_app, inspection_payload
import socket
import threading
import time
import uvicorn
from alarm_inspection.storage import PointList, PointListDecision

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


@pytest.fixture
def category_browser_app(panel_app):
    client, store = panel_app
    inspection = client.post('/api/inspections/blank', json=inspection_payload()).json()['id']
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(client.app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    try:
        yield f'http://127.0.0.1:{sock.getsockname()[1]}', inspection, store
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def test_change_type_cancel_save_and_reopen(category_browser_app):
    base, inspection, store = category_browser_app
    panel = str(uuid4())
    with store.begin() as session:
        session.add(PointList(id=panel, inspection_id=inspection, category='Combo', filename='synthetic.xlsx',
                              path='synthetic.xlsx', accepted_at=datetime.now(timezone.utc)))
        session.add(PointListDecision(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
                                      address=1, text='Smoke', location='Office', accepted=True, deleted=False))
    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            try:
                await login(page, base)
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await page.click('#edit-table')
                await page.locator('#accepted-points-body input').nth(0).fill('Unsaved description')
                await page.click('#change-panel-type')
                await playwright.expect(page.locator('#saved-panel-category')).to_have_value('Combo')
                await page.select_option('#saved-panel-category', 'Fire')
                await page.click('#cancel-panel-type')
                await playwright.expect(page.locator('#inspection-point-list-selector')).to_contain_text('Combo')
                for category in ('Fire', 'Burglar'):
                    await page.click('#change-panel-type')
                    await playwright.expect(page.locator('#save-panel-type')).to_be_enabled()
                    await page.select_option('#saved-panel-category', category)
                    await page.click('#save-panel-type')
                    await playwright.expect(page.locator('#change-panel-type-dialog')).not_to_be_visible()
                    await playwright.expect(page.locator('#inspection-point-list-selector')).to_contain_text(category)
                    await playwright.expect(page.locator('#accepted-points-body input').nth(0)).to_have_value('Unsaved description')
                await page.reload()
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('#inspection-point-list-selector')).to_contain_text('Burglar')
            finally:
                await browser.close()
    asyncio.run(check())
