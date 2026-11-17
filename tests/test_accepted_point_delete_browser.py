"""Delete controls appear only in edit mode and require a modal confirmation."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import browser_app, login
from alarm_inspection.storage import PointList, PointListDecision

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_delete_cancel_confirm_and_preserve_edits(browser_app):
    base, client, store, inspection, draft = browser_app
    panel = str(uuid4())
    with store.begin() as session:
        session.add(PointList(id=panel, inspection_id=inspection, category='Fire', filename='synthetic.xlsx',
                              path='synthetic.xlsx', accepted_at=datetime.now(timezone.utc)))
        for address in (1, 2):
            session.add(PointListDecision(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
                                          address=address, text=f'Smoke {address}', location='Office', accepted=True, deleted=False))
    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            try:
                await login(page, base)
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('.delete-point-button')).to_have_count(0)
                await page.click('#edit-table')
                await playwright.expect(page.locator('.delete-point-button')).to_have_count(2)
                await page.locator('#accepted-points-body tr').nth(1).locator('input').nth(0).fill('Unsaved description')
                await page.get_by_role('button', name='Delete point 1', exact=True).click()
                await playwright.expect(page.locator('#delete-point-dialog')).to_be_visible()
                await playwright.expect(page.locator('#delete-point-description')).to_contain_text('Point 1: Smoke 1')
                await page.click('#cancel-delete-point')
                await playwright.expect(page.locator('#accepted-points-body tr')).to_have_count(2)
                await page.get_by_role('button', name='Delete point 1', exact=True).click()
                async def fail_delete(route):
                    await route.abort('failed')
                await page.route('**/points/*', fail_delete)
                await page.click('#confirm-delete-point')
                await playwright.expect(page.locator('#delete-point-message')).to_contain_text('Please try again')
                await playwright.expect(page.locator('#accepted-points-body tr')).to_have_count(2)
                await page.unroute('**/points/*', fail_delete)
                await page.click('#confirm-delete-point')
                await playwright.expect(page.locator('#delete-point-dialog')).not_to_be_visible()
                await playwright.expect(page.locator('#accepted-points-body tr')).to_have_count(1)
                await playwright.expect(page.locator('#accepted-points-body input').nth(0)).to_have_value('Unsaved description')
                await page.click('#save-table')
                await playwright.expect(page.locator('.delete-point-button')).to_have_count(0)
                await page.reload()
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('#accepted-points-body tr')).to_have_count(1)
                await playwright.expect(page.locator('#accepted-points-body')).to_contain_text('Unsaved description')
            finally:
                await browser.close()
    asyncio.run(check())
