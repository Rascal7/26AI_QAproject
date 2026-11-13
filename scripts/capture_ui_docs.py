from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'docs' / 'images'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
    page.goto('http://127.0.0.1:8501', wait_until='domcontentloaded')
    page.get_by_text('검증 가능한 테스트, 설명 가능한 결과', exact=True).wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    for label, filename in [('대시보드', 'dashboard.png'), ('프로젝트', 'requirements.png'), ('테스트 케이스', 'test-cases.png'), ('실행 결과', 'results.png')]:
        page.get_by_text(label, exact=True).first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out / filename))
        print(label, page.locator('body').inner_text()[:2000])
    browser.close()
