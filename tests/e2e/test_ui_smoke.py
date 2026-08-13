"""
Ontologic 프론트엔드 UI 스모크 테스트 (Playwright)

프론트(3000) + 게이트웨이(9000) + 백엔드 서비스들이 떠 있는 상태에서
주요 화면이 렌더링되고 핵심 데이터가 표시되는지 검증한다.

실행:
    cd tests/e2e
    uv run --with pytest --with playwright python -m pytest test_ui_smoke.py -v
    (사전에 playwright 크로미움 설치 필요: playwright install chromium)
"""
import os
import time

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    pytest.skip("playwright 미설치", allow_module_level=True)

BASE = os.getenv("ONTOLOGIC_FRONTEND_URL", "http://127.0.0.1:3000/")


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        pg.goto(BASE, wait_until="domcontentloaded")
        pg.evaluate("localStorage.setItem('appTitle', 'Ontologic')")
        pg.reload(wait_until="domcontentloaded")
        time.sleep(5)
        yield pg
        browser.close()


def open_tab(pg, group, child, wait=6):
    child_btn = pg.locator(f'button.nav-child[title="{child}"]')
    if not child_btn.first.is_visible():
        pg.locator(f'button.nav-group-header[title="{group}"]').first.click()
        time.sleep(0.8)
    child_btn.first.click()
    time.sleep(wait)


def test_app_title_is_ontologic(page):
    assert "Ontologic" in page.title()


def _wait_for(cond, timeout_s=90, interval=3):
    """부하 상황에서 백엔드 응답이 느릴 수 있어 폴링으로 대기"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(interval)
    return False


def test_datasources_tab_shows_manufacturing(page):
    open_tab(page, "피지컬 레이어", "데이터 소스")
    cards = page.locator(".source-card")
    assert _wait_for(lambda: cards.count() >= 3), "데이터소스 카드 3개 이상이어야 함"
    names = " ".join(cards.nth(i).inner_text() for i in range(cards.count()))
    for expected in ("manufacturing", "insurance", "sales"):
        assert expected in names, f"{expected} 데이터소스 카드 없음"


def test_schema_tab_lists_tables(page):
    open_tab(page, "피지컬 레이어", "스키마 관리", wait=9)

    def loaded():
        body = page.locator("body").inner_text()
        return "manufacturing" in body

    if not loaded():
        # 테이블 목록 로드가 타임아웃됐을 수 있음 — 탭 재진입으로 재시도
        open_tab(page, "피지컬 레이어", "자연어 질의", wait=2)
        open_tab(page, "피지컬 레이어", "스키마 관리", wait=10)
    assert _wait_for(loaded), "스키마 트리에 manufacturing 없음"


def test_nl_query_tab_renders(page):
    open_tab(page, "피지컬 레이어", "자연어 질의", wait=5)
    assert page.get_by_placeholder("질문을 입력하세요... (Enter로 전송)").first.is_visible()


def test_ontology_tab_renders(page):
    open_tab(page, "도메인 레이어", "온톨로지 관리", wait=6)
    body = page.locator("body").inner_text()
    for layer in ("KPI", "Measure", "Process", "Driver", "Resource"):
        assert layer in body, f"온톨로지 레이어 패널에 {layer} 없음"


def test_whatif_tab_renders(page):
    open_tab(page, "다이나믹 레이어", "What-If 시뮬레이터", wait=7)
    assert "시나리오" in page.locator("body").inner_text()


def test_watch_agent_tab_renders(page):
    open_tab(page, "다이나믹 레이어", "감시 에이전트", wait=6)
    assert "에이전트" in page.locator("body").inner_text()
