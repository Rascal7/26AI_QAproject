from pathlib import Path
import sys
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
from demo_web.db import ROOT


def main():
    for url in ('http://127.0.0.1:5000/login', 'http://127.0.0.1:8501/_stcore/health'):
        with urlopen(url, timeout=10) as response:
            assert response.status == 200
    out = ROOT / 'artifacts/preview'
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900}, device_scale_factor=1)
        page.goto('http://127.0.0.1:5000/login')
        expect(page.get_by_role('heading', name='QA 데모 로그인')).to_be_visible()
        page.screenshot(path=str(out / 'login-desktop.png'))
        page.set_viewport_size({'width': 375, 'height': 812})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(out / 'login-mobile.png'))
        page.set_viewport_size({'width': 1440, 'height': 1000})
        check_qa_ui(page, out, execute='--execute' in sys.argv)
        browser.close()


def check_qa_ui(page, out, execute=False, url='http://127.0.0.1:8501'):
    page.goto(url)
    expect(page.get_by_role('heading', name='프로젝트', exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_role('button', name='＋ 새 프로젝트', exact=True)).to_be_visible()
    page.screenshot(path=str(out / 'qa-dashboard.png'), full_page=True)
    page.get_by_role('button',name='프로젝트 열기 →',exact=True).first.click()
    for name in ['요구사항','테스트','실행','실행 기록','프로젝트 설정']:
        page.get_by_test_id('stSidebar').get_by_role('button',name=name,exact=True).click()
        expect(page.get_by_role('heading',name=name,exact=True).first).to_be_visible()
        expect(page.get_by_test_id('stException')).to_have_count(0)
        print('UI OK:',name,flush=True)
    if execute:
        page.get_by_test_id('stSidebar').get_by_role('button',name='실행',exact=True).click()
        page.get_by_role('button',name='▶ 테스트 실행',exact=True).click()
        expect(page.get_by_text('실행 완료',exact=True)).to_be_visible(timeout=120000)
        page.get_by_role('button',name='실행 기록 보기 →',exact=True).click()
        expect(page.get_by_test_id('stMetricValue').nth(0)).to_have_text('10')
        expect(page.get_by_test_id('stMetricValue').nth(1)).to_have_text('0')
        expect(page.get_by_test_id('stMetricValue').nth(2)).to_have_text('0')
        print('Baseline UI execution PASS 10 / FAIL 0 / ERROR 0',flush=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(out / 'qa-mobile.png'),full_page=True)


if __name__ == '__main__':
    main()
