# src/tools/rss_scraper.py
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict
import re

def fetch_upwork_jobs(keyword: str = "automation", limit: int = 5) -> List[Dict]:
    """
    Fetch recent Upwork jobs via public RSS feed.
    No login, no anti-bot issues.
    """
    url = f"https://www.upwork.com/ab/feed/jobs/rss?q={keyword}&sort=recency"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Parse XML
    root = ET.fromstring(response.content)
    jobs = []
    
    for item in root.findall('.//item')[:limit]:
        job = {
            'title': item.findtext('title', ''),
            'link': item.findtext('link', ''),
            'description': item.findtext('description', ''),
            'pub_date': item.findtext('pubDate', ''),
            'guid': item.findtext('guid', '')
        }
        # Clean description (remove CDATA and HTML tags if needed)
        if job['description']:
            job['description'] = re.sub(r'<[^>]+>', '', job['description']).strip()
        jobs.append(job)
    
    return jobs

if __name__ == "__main__":
    keyword = input("Enter keyword (e.g., automation, n8n, ClickUp): ").strip() or "automation"
    jobs = fetch_upwork_jobs(keyword, limit=3)
    for i, job in enumerate(jobs, 1):
        print(f"\n--- Job {i} ---")
        print(f"Title: {job['title']}")
        print(f"Link: {job['link']}")
        print(f"Posted: {job['pub_date']}")
        print(f"Description preview: {job['description'][:300]}...")