"""Admin rename Save/Cancel and shared saved titles in a real browser."""
import asyncio
import os
import pytest
from playwright import async_api as playwright
from test_panel_category_browser import category_browser_app, panel_app
from test_pdf_integrations_browser import login
from alarm_inspection.storage import User

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_rename_cancel_save_reload_and_admin_visibility(category_browser_app):
    base, inspection, store = category_browser_app
    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            try:
                await login(page, base)
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('#inspection-name')).to_have_text('0042-Norfolk-VA-10-2026')
                original = await page.locator('#inspection-name').inner_text()
                await page.click('#rename-inspection')
                await page.fill('#inspection-custom-name', 'Cancelled name')
                await page.click('#cancel-inspection-name')
                await playwright.expect(page.locator('#inspection-name')).to_have_text(original)
                await page.click('#rename-inspection')
                await page.fill('#inspection-custom-name', 'Annual Fire Inspection')
                await page.click('#save-inspection-name')
                await playwright.expect(page.locator('#rename-inspection-dialog')).not_to_be_visible()
                await playwright.expect(page.locator('#inspection-name')).to_have_text('Annual Fire Inspection')
                await page.reload()
                await playwright.expect(page.locator('#inspection-picker')).to_contain_text('Annual Fire Inspection')
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('#inspection-name')).to_have_text('Annual Fire Inspection')
                with store.begin() as session:
                    session.query(User).one().is_admin = False
                await page.reload()
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                await playwright.expect(page.locator('#rename-inspection')).not_to_be_visible()
                await playwright.expect(page.locator('#inspection-name')).to_have_text('Annual Fire Inspection')
            finally:
                await browser.close()
    asyncio.run(check())
