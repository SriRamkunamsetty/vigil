# SPDX-License-Identifier: Apache-2.0
"""Browser tests against a real server. Run with: pytest -m e2e"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

pytestmark = pytest.mark.e2e
playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def base_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = {**os.environ, "PORT": str(port), "VIGIL_A2A_ENABLED": "false", "VIGIL_ENV": "dev"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "vigil.api.main"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if httpx.get(f"{url}/healthz", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield url
    proc.terminate()
    proc.wait(10)


@pytest.fixture
def page(base_url):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        pg = ctx.new_page()
        pg.problems = []  # type: ignore[attr-defined]
        pg.on(
            "console",
            lambda m: pg.problems.append(m.text) if m.type in {"error", "warning"} else None,
        )  # type: ignore[attr-defined]
        pg.on("pageerror", lambda e: pg.problems.append(str(e)))  # type: ignore[attr-defined]
        pg.goto(base_url)
        pg.wait_for_selector(".call-btn")
        yield pg
        assert pg.problems == [], pg.problems  # no console errors, CSP violations or failed scripts
        browser.close()


def play_to_payment(pg):
    pg.click("#play")
    pg.wait_for_selector("#payBar:not([hidden])", timeout=20000)


def test_digital_arrest_ends_in_a_held_payment(page):
    play_to_payment(page)
    page.click("#payBtn")
    assert page.inner_text("#vTier") == "Payment held"
    assert "digital arrest" in page.inner_text("#vLine").lower()
    assert page.locator("#vSteps li").count() >= 4
    assert page.locator("#drivers li").count() >= 3
    assert (
        page.locator("#transcript mark").count() >= 3
    )  # evidence is highlighted in the transcript


def test_genuine_call_stays_quiet(page):
    page.click('.call-btn[data-id="genuine_bank"]')
    page.wait_for_timeout(400)
    page.click("#play")
    page.wait_for_selector("#play:has-text('Play again')", timeout=20000)
    page.click("#payBtn") if page.locator("#payBar:not([hidden])").count() else None
    assert page.inner_text("#vTier") == "Looks fine"


def test_telugu_and_hindi_render_with_real_fonts(page):
    for call, lang_code, rng in (("investment_te", "te", ("ఀ", "౿")), ("kyc_hi", "hi", ("ऀ", "ॿ"))):
        page.click(f'.call-btn[data-id="{call}"]')
        page.wait_for_timeout(500)
        assert page.input_value("#lang") == lang_code
        play_to_payment(page) if call == "investment_te" else page.click("#play")
        if call == "investment_te":
            page.click("#payBtn")
        else:
            page.wait_for_selector("#play:has-text('Play again')", timeout=20000)
        text = page.inner_text("#vLine") + page.inner_text("#vSteps")
        assert any(rng[0] <= ch <= rng[1] for ch in text), call
        fonts = page.evaluate("document.fonts.check('16px \"Noto Sans\"', '" + rng[0] + "')")
        assert fonts is True


def test_trusted_contact_needs_explicit_approval(page):
    play_to_payment(page)
    page.click("#payBtn")
    page.click("text=Alert my trusted contact")
    assert page.locator("dialog[open]").count() == 1
    page.click("#dlgOk")
    page.wait_for_selector("#vActions >> text=nothing was sent")
    assert page.locator("dialog[open]").count() == 0


def test_tabs_keyboard_and_network_effect(page):
    page.focus("#t-guardian")
    page.keyboard.press("ArrowRight")
    assert page.get_attribute("#t-network", "aria-selected") == "true"
    page.wait_for_selector(".node")
    page.click("#effA")
    page.click("#effB")
    page.wait_for_selector("text=Confirmed by 2 banks")
    assert "Slow down" in page.inner_text("#effOut") or "Payment held" in page.inner_text("#effOut")
    page.fill("#analyst", "Asha")
    page.click("#publishBtn")
    page.wait_for_selector("text=scrambled fingerprints with partner banks")


def test_agent_payment_and_eval_tabs(page):
    page.click("#t-payments")
    page.wait_for_selector(".case-btn")
    page.click('.case-btn[data-id="hijack"]')
    page.wait_for_selector(".badge.deny")
    page.click('.case-btn[data-id="legit"]')
    page.wait_for_selector(".badge.approve")
    page.click("#t-eval")
    page.wait_for_selector(".eval-card.limits")
    assert "synthetic" in page.inner_text("#evalDisclaimer").lower()
    assert "Paraphrased scams" in page.inner_text(".eval-card.limits")


def test_security_headers_on_the_page(base_url):
    r = httpx.get(base_url + "/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
