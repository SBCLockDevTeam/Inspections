"""Opt-in regression for out-of-order autosaves under real browser networking."""
import asyncio
import os
import socket
import threading
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
uvicorn = pytest.importorskip("uvicorn")
playwright = pytest.importorskip("playwright.async_api")
pytestmark = pytest.mark.skipif(os.getenv("INSPECTIONS_RUN_BROWSER_TESTS") != "1", reason="Opt-in browser regression")


def test_latest_details_win_when_autosaves_are_delayed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'browser.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store, User

    app = create_app()
    with open_store().begin() as session:
        admin = session.query(User).one()
        admin.force_password_reset = False
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started

    async def check():
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = await browser.new_page()
                base = f"http://127.0.0.1:{port}"
                await page.goto(base)
                await page.fill("#login-email", "john.porter@securitybuildingcontrols.com")
                await page.fill("#login-password", "password")
                await page.locator("#login-form button[type=submit]").click()
                await playwright.expect(page.locator("#home-screen")).to_be_visible()
                response = await page.request.post(base + "/api/inspections/blank", data={
                    "store_number": "0042", "address": "123 Test St", "city": "Norfolk", "state": "VA",
                    "start_date": "2026-09-01", "completion_date": "2026-09-02",
                })
                inspection_id = (await response.json())["id"]
                await page.click("#refresh-inspections")
                await page.locator("#inspection-picker").select_option(inspection_id)
                await page.click("#open-inspection")
                await playwright.expect(page.locator("#inspection-name")).to_have_text("0042-Norfolk-VA-09-2026")

                async def delay_older_save(route):
                    if route.request.method == "PATCH" and route.request.post_data_json.get("city") == "Virginia Beach":
                        await asyncio.sleep(0.4)
                    await route.continue_()

                await page.route("**/api/inspections/" + inspection_id, delay_older_save)
                await page.evaluate("""() => {
                    const originalFetch = window.fetch;
                    window.namingSaves = 0;
                    window.pendingNamingSaves = 0;
                    window.fetch = async (...args) => {
                        const save = args[1]?.method === 'PATCH';
                        if (save) { window.namingSaves++; window.pendingNamingSaves++; }
                        try { return await originalFetch(...args); }
                        finally { if (save) window.pendingNamingSaves--; }
                    };
                    const city = document.querySelector('#inspection-city');
                    city.value = 'Virginia Beach';
                    city.dispatchEvent(new Event('change'));
                }""")
                await page.wait_for_function("window.pendingNamingSaves === 1")
                await page.evaluate("""() => {
                    const date = document.querySelector('#inspection-start-date');
                    date.value = '2026-08-31';
                    date.dispatchEvent(new Event('change'));
                }""")
                await page.wait_for_function("window.namingSaves >= 2 && window.pendingNamingSaves === 0")
                await playwright.expect(page.locator("#inspection-name")).to_have_text("0042-Virginia Beach-VA-08-2026")
                persisted = await page.request.get(base + "/api/inspections/" + inspection_id)
                assert (await persisted.json())["name"] == "0042-Virginia Beach-VA-08-2026"
            finally:
                await browser.close()
    try:
        asyncio.run(check())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
