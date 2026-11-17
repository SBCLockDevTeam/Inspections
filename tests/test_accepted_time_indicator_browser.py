"""Accepted time checks are visible on phones, live, and absent from print."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import browser_app, login
from alarm_inspection.storage import PointList, PointListDecision, PointListEventDate, PointListPendingEventDate

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_saved_time_indicator_mobile_print_and_live_edit(browser_app):
    base, client, store, inspection, draft = browser_app
    panel = str(uuid4())
    ids = [str(uuid4()) for _ in range(3)]
    with store.begin() as session:
        session.add(PointList(id=panel, inspection_id=inspection, category='Fire', filename='synthetic.xlsx',
                              path='synthetic.xlsx', accepted_at=datetime.now(timezone.utc)))
        for address, ident in enumerate(ids, 1):
            session.add(PointListDecision(id=ident, inspection_id=inspection, point_list_id=panel,
                                          address=address, text=f'Smoke {address}', location='Office', accepted=True, deleted=False))
        session.add(PointListEventDate(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
                                      point_address=1, event_timestamp=datetime(2026, 10, 1, 9), source_filename='synthetic.xlsx'))
        session.add(PointListPendingEventDate(inspection_id=inspection, point_list_id=panel,
                                             point_address=2, event_timestamp=datetime(2026, 10, 1, 10), source_filename='synthetic.xlsx'))
    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 390, 'height': 844})
            try:
                await login(page, base)
                await page.select_option('#inspection-picker', inspection)
                await page.click('#open-inspection')
                cells = page.locator('#accepted-points-body .accepted-time-cell')
                await playwright.expect(cells.nth(0)).to_have_text('✓')
                await playwright.expect(cells.nth(0)).to_have_css('color', 'rgb(21, 128, 61)')
                await playwright.expect(cells.nth(1)).to_have_text('')
                await playwright.expect(cells.nth(2)).to_have_text('')
                assert await cells.nth(0).evaluate('(el) => el.cellIndex') == 0
                region = page.locator('#points-table-scroll')
                await region.evaluate('(el) => { el.scrollLeft = el.scrollWidth; }')
                cell_box, region_box = await cells.nth(0).bounding_box(), await region.bounding_box()
                assert abs(cell_box['x'] - region_box['x']) <= 2
                await page.emulate_media(media='print')
                await playwright.expect(cells.nth(0)).to_be_hidden()
                await playwright.expect(page.locator('th.accepted-time-cell')).to_be_hidden()
                await page.emulate_media(media='screen')
                await page.click('#edit-table')
                rows = page.locator('#accepted-points-body tr')
                await rows.nth(2).locator('input').nth(3).fill('2026-10-01 11:00:00')
                await playwright.expect(cells.nth(2)).to_have_text('')
                await rows.nth(2).locator('input').nth(0).fill('Local draft')
                # Another device saves a location and accepted timestamp during edit mode.
                response = client.post(f'/api/inspections/{inspection}/accepted-points/save', json={
                    'point_list_id': panel, 'rows': [{'id': ids[1], 'location': 'Remote location', 'event_date': '2026-10-01 10:00:00'}]})
                assert response.status_code == 200
                await playwright.expect(cells.nth(1)).to_have_text('✓', timeout=12000)
                await playwright.expect(rows.nth(1).locator('input').nth(2)).to_have_value('Remote location')
                await playwright.expect(rows.nth(2).locator('input').nth(0)).to_have_value('Local draft')
                response = client.post(f'/api/inspections/{inspection}/event-dates/clear', json={'point_list_id': panel, 'confirmed': True})
                assert response.status_code == 200
                await playwright.expect(cells.nth(0)).to_have_text('', timeout=12000)
                await playwright.expect(cells.nth(1)).to_have_text('', timeout=12000)
            finally:
                await browser.close()
    asyncio.run(check())
