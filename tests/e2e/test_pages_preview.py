"""The public demo must work under a Pages subpath without sending RSVP data."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread

import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.mark.parametrize("attending", [True, False])
def test_pages_demo_never_submits_or_stores_guest_data(tmp_path, attending):
    root = Path(__file__).resolve().parents[2]
    site = tmp_path / "axe-gestao-convites"
    built = subprocess.run(
        [sys.executable, str(root / "scripts/build_pages_preview.py"), "--output", str(site)],
        capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    worker = Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            requests = []
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.goto(f"http://127.0.0.1:{httpd.server_port}/axe-gestao-convites/")
            expect(page.get_by_role("heading", name="Os 2 aninhos da Isadora")).to_be_visible()
            expect(page.locator("#preview-notice")).to_contain_text("nenhuma resposta será enviada")
            page.locator("#contact-name").fill("Pessoa de teste")
            if attending:
                page.locator("#add-companion").click()
                row = page.locator(".person-row").nth(1)
                row.locator(".person-name").fill("Criança de teste")
                row.locator(".person-kind").select_option("CHILD")
                row.locator(".person-age").fill("6")
            else:
                page.locator('input[name="attendance"][value="no"]').check()
            page.locator("#review-btn").click()
            expect(page.locator("#review-data")).to_contain_text("Pessoa de teste")
            page.locator("#back-btn").click()
            expect(page.locator("#contact-name")).to_have_value("Pessoa de teste")
            page.locator("#review-btn").click()
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            expect(page.locator("#success-message")).to_contain_text("não foi enviada")
            assert page.locator("#edit-link").count() == 0
            assert all(method == "GET" and "/api/" not in url for method, url in requests)
            assert page.evaluate("Object.keys(localStorage).length + Object.keys(sessionStorage).length") == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.locator("#preview-reset").click()
            expect(page.locator("#contact-name")).to_have_value("")
            browser.close()
    finally:
        httpd.shutdown()
        worker.join(timeout=5)
        httpd.server_close()
