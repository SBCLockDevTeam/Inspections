"""Administrator creates, renames, locks and resets a user through the UI."""
import asyncio
import os

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import login
from test_panel_category_browser import category_browser_app, panel_app

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_admin_user_controls_and_login(category_browser_app, panel_app):
    base, inspection, store = category_browser_app
    client, _ = panel_app
    assert client.patch('/api/admin/settings', json={'default_password': 'TemporaryPassword42!', 'force_password_reset_default': False}).status_code == 200
    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 1280, 'height': 900})
            try:
                await login(page, base)
                await page.locator('#avatar-button').click(button='right')
                await page.click('#avatar-menu-option-admin')
                await page.click('#open-admin-add-user')
                await page.fill('#admin-add-user-id', 'Inspector 42')
                assert await page.locator('#admin-add-user-email').get_attribute('required') is not None
                await page.fill('#admin-add-user-email', 'inspector42@example.com')
                await page.click('#confirm-admin-add-user')
                await playwright.expect(page.locator('#admin-add-user-modal')).not_to_be_visible()
                row = page.locator('#admin-users-body tr').filter(has_text='inspector42@example.com')
                await playwright.expect(row).to_be_visible()
                id_input = row.get_by_role('textbox')
                await id_input.fill('Inspector-007')
                await row.get_by_role('button', name='Save ID', exact=True).click()
                await playwright.expect(page.locator('#admin-message')).to_contain_text('User ID saved: Inspector-007')
                lock = row.get_by_role('checkbox', name='Lock account for inspector42@example.com')
                await lock.check()
                await playwright.expect(page.locator('#admin-message')).to_contain_text('locked and signed out')
                failed = client.post('/api/auth/login', json={'username': 'Inspector-007', 'password': 'TemporaryPassword42!'})
                assert failed.status_code == 401
                await lock.uncheck()
                await playwright.expect(page.locator('#admin-message')).to_contain_text('unlocked')
                page.once('dialog', lambda dialog: dialog.dismiss())
                await row.get_by_role('button', name='Reset Password', exact=True).click()
                page.once('dialog', lambda dialog: dialog.accept())
                await row.get_by_role('button', name='Reset Password', exact=True).click()
                await playwright.expect(page.locator('#admin-message')).to_contain_text('Password reset for Inspector-007')
                await page.screenshot(path='/tmp/inspections-admin-users-desktop.png', full_page=True)
                await page.set_viewport_size({'width': 390, 'height': 844})
                assert await page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
                await page.screenshot(path='/tmp/inspections-admin-users-mobile.png', full_page=True)
                tech = await browser.new_page()
                await tech.goto(base)
                await tech.fill('#login-email', 'Inspector-007')
                await tech.fill('#login-password', 'TemporaryPassword42!')
                await tech.locator('#login-form button').click()
                await playwright.expect(tech.locator('#password-reset-form')).to_be_visible()
                await playwright.expect(tech.locator('#reset-current-password')).to_have_count(0)
                await playwright.expect(tech.locator('#active-user-label')).to_contain_text('Inspector-007')
                await tech.fill('#reset-new-password', 'NewPersonalPassword42!')
                await tech.fill('#reset-confirm-password', 'DifferentPassword42!')
                await tech.locator('#password-reset-form button').click()
                await playwright.expect(tech.locator('#login-message')).to_contain_text('must match')
                await tech.fill('#reset-confirm-password', 'NewPersonalPassword42!')
                await tech.locator('#password-reset-form button').click()
                await playwright.expect(tech.locator('#home-screen')).to_be_visible()
            finally:
                await browser.close()
    asyncio.run(check())
