# src/tools/upwork_scraper.py
from playwright.sync_api import sync_playwright

def scrape_upwork_job(job_url: str) -> dict:
    """
    Scrapes a public Upwork job posting and returns structured data.
    Synchronous version with basic stealth.
    """
    with sync_playwright() as p:
        # Launch browser with anti-detection args
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        print(f"🔍 Navigating to: {job_url}")
        page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
        
        # Wait for content
        page.wait_for_selector('h1, section[data-test="JobDescription"]', timeout=15000)
        
        job_data = {}
        
        # Title
        try:
            title_elem = page.query_selector('h1[data-test="job-title"], h1.job-title, h1')
            job_data['title'] = title_elem.inner_text().strip() if title_elem else "N/A"
        except:
            job_data['title'] = "N/A"
        
        # Description
        try:
            desc_elem = page.query_selector('div[data-test="job-description"], section[data-test="JobDescription"] div, .job-description')
            job_data['description'] = desc_elem.inner_text().strip() if desc_elem else "N/A"
        except:
            job_data['description'] = "N/A"
        
        # Skills / Tags
        try:
            skill_elems = page.query_selector_all('span[data-test="skill-tag"], a[data-qa="skill"] span, .air3-token span')
            job_data['skills'] = [el.inner_text().strip() for el in skill_elems[:20]]
        except:
            job_data['skills'] = []
        
        # Budget
        try:
            budget_elem = page.query_selector('li[data-test="budget"] strong, [data-qa="job-budget"]')
            job_data['budget'] = budget_elem.inner_text().strip() if budget_elem else "Not specified"
        except:
            job_data['budget'] = "Not specified"
        
        # Posted time
        try:
            time_elem = page.query_selector('span[data-test="posted-on"], [data-qa="job-posted-on"] span')
            job_data['posted_time'] = time_elem.inner_text().strip() if time_elem else "N/A"
        except:
            job_data['posted_time'] = "N/A"
        
        browser.close()
        return job_data

# Test
if __name__ == "__main__":
    test_url = input("Enter a public Upwork job URL: ").strip()
    data = scrape_upwork_job(test_url)
    print("\n📋 Scraped Job Data:")
    for key, value in data.items():
        print(f"{key}: {value}")