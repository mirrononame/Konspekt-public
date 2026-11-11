"""UI-тести 2.0 (Playwright, ПК 1280×800 і телефон 390×844) на синтетичних даних."""
import re
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("SHOTS", tempfile.mkdtemp(prefix="shots-")))
W = "2026-10-19_1115_so_aaaa"
L = "2026-10-19_0730_so_bbbb"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    sys.path.insert(0, str(ROOT / "tests"))
    import fixture
    data = fixture.make(Path(tempfile.mkdtemp(prefix="konspekt-ui-")))
    port = _free_port()
    env = {**os.environ, "KONSPEKT_DATA": str(data), "KONSPEKT_BETA": "1", "PYTHONUTF8": "1"}
    p = subprocess.Popen([sys.executable, "-m", "app.server", "--port", str(port), "--no-browser"], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/ping", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield url
    p.terminate()


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _page(pw, mobile=False):
    if mobile:
        ctx = pw.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2,
                             user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148")
    else:
        ctx = pw.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    return page, errs


def shot(page, name):
    safe = re.sub(r'[\/:*?"<>|]+', "_", name)  # назва типу картки може містити «/»
    page.screenshot(path=str(SHOTS / f"{safe}.png"), full_page=False)


def test_home_desktop(server, pw):
    page, errs = _page(pw)
    page.goto(server + "/#/")
    expect(page.locator(".beta-badge")).to_be_visible()
    todo = page.locator('#nav a[href="#/"] .count[title="Пунктів до здачі"]')  # 2.7: лічильник «здати» — на «Сьогодні»
    expect(todo).to_have_text("2")  # 2.2: лише пункти з терміном на ±7 днів (третій — без дати)
    expect(page.locator("#nav > a")).to_have_count(4 + 4)  # 2.8: 3 розділи + «Додати» і 4 у «Ще»
    shot(page, "pc_home")
    page.goto(server + "/#/todo")
    expect(page.locator(".todo-gh").first).to_contain_text("Найближчі 7 днів")
    expect(page.locator("text=Sprawozdanie PDF").first).to_be_visible()
    page.locator(".todo-check").first.click()
    page.wait_for_timeout(1500)
    expect(page.locator(".todo-done summary")).to_contain_text("1")
    expect(todo).to_have_text("1")
    shot(page, "pc_todo")
    assert not errs, errs


def _mode(page, m):
    """2.2: рідкісні режими навчання сховані в «Ще режими» — розгорнути, якщо кнопки не видно."""
    b = page.locator(f'[data-mode="{m}"]').first
    if not b.is_visible():
        page.locator(".more-modes > summary").click()
    b = page.locator(f'[data-mode="{m}"]').first
    b.click()


def _tab(page, key):
    """2.7: секції замість вкладок — розгорнути, якщо згорнута."""
    d = page.locator(f'details[data-sec="{key}"]')
    if d.get_attribute("open") is None:
        d.locator("summary").click()


def test_study_today_all_types_desktop(server, pw):
    page, errs = _page(pw)
    page.goto(server + f"/#/study?lecture={W}")
    expect(page.locator(".study-hero")).to_be_visible()
    shot(page, "pc_study")
    _mode(page, "all")
    expect(page.locator(".flash-card")).to_be_visible()
    seen = set()
    for _ in range(40):
        if page.locator(".sum-card").count():
            break
        card = page.locator(".flash-card")
        t = card.locator(".fc-meta .badge").first.inner_text()
        seen.add(t)
        if len(seen) <= 6:
            shot(page, f"pc_card_{len(seen)}_{t}")
        if page.locator(".mcq").count() and not page.locator(".opt.right").count():
            page.keyboard.press("a")
        elif page.locator("#ss-in").count():
            page.fill("#ss-in", "chmd" if "Polecenie" in card.inner_text() else "6")
            page.keyboard.press("Enter")
        elif page.locator("[data-tf]").count() and not page.locator(".opt.right").count():
            page.locator('[data-tf="true"]').click()
        elif page.locator("[data-pick]").count():
            while page.locator("[data-pick]").count():
                page.locator("[data-pick]").first.click()
        elif page.locator("#ss-show").count():
            page.keyboard.press(" ")
        expect(page.locator("[data-rate]").first).to_be_visible()
        if "Polecenie" in card.inner_text():
            expect(page.locator(".your.ok")).to_contain_text("описк")
        if "Który stan" in card.inner_text():
            shot(page, "pc_mcq_answered")
        page.keyboard.press("3")
        page.wait_for_timeout(120)
    expect(page.locator(".sum-card")).to_be_visible()
    shot(page, "pc_summary")
    assert {"Вибір", "Впиши", "Правда / ні", "Порядок", "Код", "Картка"} <= seen, seen
    assert not errs, errs


def test_test_mode_and_blitz(server, pw):
    page, errs = _page(pw)
    page.goto(server + "/#/study?subject=so")
    _mode(page, "test")
    for _ in range(90):  # кожне питання — 2–3 дії; з запасом, щоб тест не залежав від швидкості ПК
        if page.locator(".sum-card").count():
            break
        if page.locator("#ss-next").count():
            page.keyboard.press("Enter")
        elif page.locator("[data-self]").count():
            page.locator('[data-self="1"]').click()
        else:
            page.locator("#ss-show").click()
        page.wait_for_timeout(150)
    expect(page.locator(".sum-big")).to_be_visible()
    expect(page.locator(".mistakes")).to_be_visible()
    shot(page, "pc_test_result")
    page.locator("#sum-back").click()
    _mode(page, "blitz")
    expect(page.locator("#bz-t")).to_be_visible()
    for _ in range(4):
        page.keyboard.press("ArrowRight")
    shot(page, "pc_blitz")
    page.locator("#ss-exit").click()
    expect(page.locator("text=Бліц:")).to_be_visible()
    assert not errs, errs


def test_manage_and_custom(server, pw):
    page, errs = _page(pw)
    page.goto(server + "/#/study?manage=1")
    expect(page.locator(".mg-row").first).to_be_visible()
    page.locator("#mg-add").click()
    page.fill('textarea[name="q"]', "Co to jest PID?")
    page.fill('textarea[name="a"]', "Identyfikator procesu")
    page.locator('[data-a="ok"]').click()
    expect(page.locator("text=Co to jest PID?")).to_be_visible()
    page.locator(".mg-row", has_text="Co to jest PID?").locator("[data-mg]").click()
    page.locator('[data-cm="hide"]').click()
    page.locator('[data-show="hidden"]').click()
    expect(page.locator(".mg-row.is-hidden", has_text="Co to jest PID?")).to_be_visible()
    shot(page, "pc_manage")
    assert not errs, errs


def test_lab_page_tabs(server, pw):
    page, errs = _page(pw)
    page.goto(server + f"/#/lecture/{L}")
    expect(page.locator(".chat-card")).to_be_visible()  # 2.7: «Робота в чаті»
    expect(page.locator("#lec-tabs")).to_have_count(0)
    page.fill("#chat-note", "Zrób instrukcję")
    page.locator('[data-chat="copy"]').click()
    expect(page.locator(".chat-card .section-head")).to_contain_text("запит складено")
    shot(page, "pc_lab_chat")
    expect(page.locator(".todo-card")).to_be_visible()
    page.locator(".todo-card .todo-check").first.click()
    page.wait_for_timeout(500)
    expect(page.locator(".todo-card .todo.done").first).to_be_visible()
    expect(page.locator(".todo-card .small.muted")).to_contain_text("1/3")
    expect(page.locator('details[data-sec="help"]')).to_have_count(0)  # 2.7: «Допоможи» через чергу — лише якщо вже були питання
    _tab(page, "task")
    page.set_input_files("#pf-in-task", files=[{"name": "zad.png", "mimeType": "image/png", "buffer": b"\x89PNG\r\n\x1a\n"}])
    expect(page.locator("text=zad.png")).to_be_visible()
    _tab(page, "code")
    page.set_input_files("#pf-in-code", files=[{"name": "s.sh", "mimeType": "text/plain", "buffer": b"#!/bin/bash\necho hi\n"}])
    expect(page.locator("text=s.sh")).to_be_visible()
    page.locator(".code-peek summary").click()
    expect(page.locator(".code-peek code")).to_contain_text("echo hi")
    shot(page, "pc_lab_code")
    # 2.1: умова → план у черзі
    _tab(page, "plan")
    expect(page.locator("text=Інструкція готується")).to_be_visible()  # у фікстурі ввімкнено auto_plan
    expect(page.locator("[data-open-claude]")).to_be_visible()
    shot(page, "pc_lab_plan_pending")
    assert [e for e in errs if "404" not in e] == [], errs


def test_plan_ready_and_eportal_banner(server, pw):
    import json as _j
    from datetime import datetime as _dt, timedelta as _td
    data = Path(urllib.request.urlopen(server + "/api/state").read() and _j.loads(urllib.request.urlopen(server + "/api/state").read())["data_dir"])
    out = data / "lectures" / L / "output"
    (out / "plan.md").write_text("# Plan Lab 1\n\n**1.** Przygotuj skrypt\n\n```bash\nchmod a+x s.sh\n```\n", encoding="utf-8")
    later = (_dt.now().astimezone() + _td(seconds=5)).isoformat(timespec="seconds")
    (out / "plan.json").write_text(_j.dumps({"completed_at": later, "checklist": [{"text": "Skrypt gotowy przed zajęciami"}]}), encoding="utf-8")
    m = _j.loads((data / "lectures" / W / "meta.json").read_text(encoding="utf-8"))
    m["eportal_new"] = [{"name": "W3_slajdy.pdf", "at": later}]
    (data / "lectures" / W / "meta.json").write_text(_j.dumps(m, ensure_ascii=False), encoding="utf-8")
    page, errs = _page(pw)
    page.goto(server + f"/#/lecture/{L}?tab=plan")
    expect(page.locator(".md h1")).to_have_text("Plan Lab 1")
    expect(page.locator("text=Skrypt gotowy przed zajęciami")).to_be_visible()
    shot(page, "pc_lab_plan_ready")
    page.goto(server + f"/#/lecture/{W}")
    expect(page.locator("text=Нові матеріали з ePortalu")).to_be_visible()
    shot(page, "pc_eportal_new")
    page.locator('[data-act="epnew-up"]').click()
    page.wait_for_timeout(600)
    expect(page.locator("text=Нові матеріали з ePortalu")).to_have_count(0)
    assert [e for e in errs if "404" not in e] == [], errs


def test_subject_tabs_map(server, pw):
    page, errs = _page(pw)
    page.goto(server + "/#/subject/so")
    expect(page.locator("#sj-tabs button")).to_have_count(2)  # 2.7: Заняття, Матеріали (у SO немає проєкту)
    expect(page.locator('#sj-types [data-typ="L"]')).to_be_visible()
    page.locator('#sj-tabs [data-tab="materials"]').click()
    page.locator("details.lsec summary", has_text="Карта курсу").click()
    expect(page.locator(".cm-row")).to_be_visible()
    expect(page.locator(".mem")).to_contain_text("Jak chce prowadzący")
    shot(page, "pc_subject_map")
    page.locator('#sj-tabs [data-tab="lessons"]').click()
    page.locator('#sj-types [data-typ="L"]').click()
    expect(page.locator(".row", has_text="Lab 1")).to_be_visible()
    expect(page.locator(".row", has_text="Procesy")).to_have_count(0)
    assert not errs, errs


def test_source_link_seeks_transcript(server, pw):
    page, errs = _page(pw)
    page.goto(server + f"/#/lecture/{W}?t=754")
    expect(page.locator(".hl-line")).to_contain_text("zdanie 12")
    assert not errs, errs


def test_mobile_study_swipe(server, pw):
    page, errs = _page(pw, mobile=True)
    page.goto(server + "/#/study")
    expect(page.locator(".study-hero")).to_be_visible()
    shot(page, "m_study")
    _mode(page, "all")
    expect(page.locator(".flash-card")).to_be_visible()
    assert not page.locator(".bottom-nav").is_visible()  # повноекранна картка
    # шукаємо flip-картку
    for _ in range(25):
        if page.locator(".flip3d").count():
            break
        page.wait_for_timeout(150)
        if page.locator(".flip3d").count():
            break
        if page.locator("#ss-show").count():
            page.locator("#ss-show").click()
        else:
            shot(page, "m_debug")
            raise AssertionError(page.locator(".study-wrap").inner_text()[:500])
        page.locator("[data-rate='3']").click()
    shot(page, "m_card_front")
    page.locator(".flip3d").tap()
    expect(page.locator(".flip3d.flipped")).to_be_visible()
    page.wait_for_timeout(500)
    shot(page, "m_card_back")
    n0 = page.locator(".ss-top .small").inner_text()
    box = page.locator(".flash-card").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, 8):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + i * 25, "y": y}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(600)
    assert page.locator(".ss-top .small").inner_text() != n0 or page.locator(".sum-card").count()
    assert not errs, errs


def test_mobile_pages(server, pw):
    page, errs = _page(pw, mobile=True)
    for name, url in (("m_home", "/#/"), ("m_todo", "/#/todo"), ("m_lab", f"/#/lecture/{L}"), ("m_subject", "/#/subject/so?tab=map")):
        page.goto(server + url)
        page.wait_for_timeout(700)
        shot(page, name)
        w = page.evaluate("document.documentElement.scrollWidth")
        assert w <= 392, (name, w)
    assert not errs, errs



def test_interface_language_switch(server, pw):
    import json as _j
    import urllib.request as _u
    req = _u.Request(server + "/api/settings", data=_j.dumps({"ui_language": "en"}).encode(), method="PUT", headers={"Content-Type": "application/json"})
    _u.urlopen(req).read()
    try:
        page, errs = _page(pw)
        page.goto(server + "/#/settings")
        expect(page.locator("h1")).to_have_text("Settings")
        expect(page.locator('#nav a[href="#/"]')).to_contain_text("Today")
        expect(page.locator('[data-uilang="ru"] .flag')).to_have_css("background-color", "rgb(156, 163, 175)")
        shot(page, "pc_settings_en")
        assert not errs, errs
    finally:
        req = _u.Request(server + "/api/settings", data=_j.dumps({"ui_language": "uk"}).encode(), method="PUT", headers={"Content-Type": "application/json"})
        _u.urlopen(req).read()
