"""Review uploaded events without changing existing results until a choice."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from playwright import async_api as playwright
from test_pdf_integrations_browser import browser_app, login
from test_event_device_status import workbook
from alarm_inspection.storage import PointList, PointListDecision, PointListEventDate

pytestmark = pytest.mark.skipif(os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1', reason='Opt-in real browser tests')


def test_upload_review_reject_and_clear(browser_app):
    base,client,store,inspection,draft = browser_app
    panel = str(uuid4())
    with store.begin() as session:
        session.add(PointList(id=panel,inspection_id=inspection,category='Fire',filename='synthetic.xlsx',
            path='synthetic.xlsx',accepted_at=datetime.now(timezone.utc)))
        session.add(PointListDecision(id=str(uuid4()),inspection_id=inspection,point_list_id=panel,
            address=1,text='Smoke',accepted=True,deleted=False))
        session.add(PointListEventDate(id=str(uuid4()),inspection_id=inspection,point_list_id=panel,
            point_address=1,event_timestamp=datetime(2026,10,1,9),source_filename='original.xlsx'))
    async def check():
        async with playwright.async_playwright() as p:
            browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=await browser.new_page()
            async def upload():
                await page.locator('#event-file').set_input_files({'name':'new.xlsx',
                    'mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'buffer':workbook([['Date','Zone','State'],[datetime(2026,10,2,11),1,'A']])})
                await playwright.expect(page.locator('#event-upload-review')).to_be_visible()
            try:
                await login(page,base)
                await page.select_option('#inspection-picker',inspection)
                await page.click('#open-inspection')
                await upload()
                await playwright.expect(page.locator('#event-upload-summary')).to_contain_text('No times have been changed')
                await page.click('#event-upload-reject')
                await playwright.expect(page.locator('#inspection-message')).to_contain_text('Existing times are unchanged')
                with store() as session:assert session.query(PointListEventDate).count()==1
                await upload()
                page.once('dialog',lambda dialog:dialog.dismiss())
                await page.click('#event-upload-clear')
                await playwright.expect(page.locator('#event-upload-review')).to_be_visible()
                with store() as session:assert session.query(PointListEventDate).count()==1
                page.once('dialog',lambda dialog:dialog.accept())
                await page.click('#event-upload-clear')
                await playwright.expect(page.locator('#event-upload-review')).not_to_be_visible()
                await playwright.expect(page.locator('#inspection-message')).to_contain_text('Previous times cleared')
                with store() as session:assert session.query(PointListEventDate).count()==0
                await playwright.expect(page.locator('#accepted-points-body')).to_contain_text('pending')
            finally:
                await browser.close()
    asyncio.run(check())
