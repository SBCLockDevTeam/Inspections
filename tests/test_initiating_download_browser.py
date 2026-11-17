"""Download feedback stays visible for validation, network errors and success."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import browser_app, login
from alarm_inspection.storage import PointList, PointListDecision, PointListEventDate

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_initiating_download_feedback_and_retry(browser_app):
    base, client, store, inspection, draft = browser_app
    panel = str(uuid4())
    with store.begin() as session:
        session.add(PointList(id=panel, inspection_id=inspection, category='Fire', filename='synthetic.xlsx',
                              path='synthetic.xlsx', accepted_at=datetime.now(timezone.utc)))
        session.add(PointListDecision(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
                                      address=1, text='Smoke', location='Office', accepted=True, deleted=False))

    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            try:
                # Production uses HTTP, where the native file picker is unavailable.
                await page.add_init_script('window.showSaveFilePicker = undefined')
                await login(page, base)
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await page.click('#inspection-menu-button')
                await page.click('#inspection-menu-option-export-pdf')
                await page.select_option('#download-form-type', 'initiating')
                button = page.locator('#download-selected-pdf')
                message = page.locator('#initiating-download-message')
                await button.click()
                await playwright.expect(message).to_contain_text('accepted test timestamp required')
                await playwright.expect(message).to_be_visible()
                await playwright.expect(button).to_be_enabled()
                async def fail(route):
                    await route.abort('failed')
                await page.route('**/export-pdf', fail)
                await button.click()
                await playwright.expect(message).to_contain_text('PDF download failed')
                await playwright.expect(button).to_be_enabled()
                await page.unroute('**/export-pdf', fail)
                with store.begin() as session:
                    session.add(PointListEventDate(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
                                                  point_address=1, event_timestamp=datetime(2026, 10, 1, 9),
                                                  source_filename='synthetic.xlsx'))
                async with page.expect_download() as download_info:
                    await button.click()
                download = await download_info.value
                assert download.suggested_filename == 'PDFTEST-Norfolk,VA-Initiating Devices-Fire-10-02-26.pdf'
                assert await download.failure() is None
                await playwright.expect(message).to_contain_text('PDF downloaded:')
                await playwright.expect(message).to_be_visible()
            finally:
                await browser.close()
    asyncio.run(check())
