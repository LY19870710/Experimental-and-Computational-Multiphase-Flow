#!/usr/bin/env python3
"""
ECMF (Experimental and Computational Multiphase Flow) 2026 Article Scraper
Scrapes all 2026 articles from SciOpen and saves structured data to JSON.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
import sys
from pathlib import Path

BASE_URL = "https://www.sciopen.com"
ISSN = "2661-8869"
JOURNAL_ID = "1397828583075348482"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

HEADERS = {"User-Agent": USER_AGENT}

def get_meta(soup, name):
    """Extract single meta tag content."""
    tag = soup.find("meta", attrs={"name": name})
    if not tag:
        tag = soup.find("meta", attrs={"property": name})
    return tag["content"] if tag and tag.get("content") else None

def get_meta_all(soup, name):
    """Extract all meta tag contents with given name."""
    results = []
    for tag in soup.find_all("meta", attrs={"name": name}):
        if tag.get("content"):
            results.append(tag["content"])
    return results

def extract_dates(soup):
    """Extract received/revised/accepted/published dates from page HTML."""
    dates = {}
    page_text = soup.get_text()
    for label in ["Received:", "Revised:", "Accepted:", "Published:"]:
        idx = page_text.find(label)
        if idx >= 0:
            # Get text after label, stop at next label or end of line
            after = page_text[idx + len(label):].strip()
            # Date format: DD Month YYYY
            match = re.match(r'(\d{1,2}\s+\w+\s+\d{4})', after)
            if match:
                dates[label.replace(":", "").lower()] = match.group(1)
    return dates

def extract_stats(soup):
    """Extract views/downloads/citations from page text."""
    stats = {}
    page_text = soup.get_text()
    for label in ["Views:", "Downloads:", "Crossref:", "Web of Science:", "Scopus:", "CSCD:"]:
        idx = page_text.find(label)
        if idx >= 0:
            snippet = page_text[idx:idx+30].replace("\n", " ").strip()
            match = re.match(rf'{label}\s*(\d+)', snippet)
            if match:
                key = label.replace(":", "").replace(" ", "_").lower()
                stats[key] = int(match.group(1))
    return stats

def extract_internal_id(soup):
    """Extract internal article ID from download links."""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "download_ris" in href:
            match = re.search(r"id=(\d+)", href)
            if match:
                return match.group(1)
    return None

def extract_article_type(soup):
    """Extract article type from page text."""
    page_text = soup.get_text()
    types = ["Research Article", "Review", "Editorial", "Letter", "Brief Communication", "Retraction Notice"]
    for t in types:
        if t in page_text:
            return t
    return "Research Article"  # default

def scrape_article(doi):
    """Scrape a single article page and return structured data."""
    url = f"{BASE_URL}/article/{doi}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # JSON-LD
    json_ld = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            json_ld = json.loads(script.string)
        except:
            pass
    
    # Extract dates
    dates = extract_dates(soup)
    
    # Extract stats
    stats = extract_stats(soup)
    
    # Internal ID
    internal_id = extract_internal_id(soup)
    
    # Article type
    article_type = extract_article_type(soup)
    
    # Authors & affiliations
    authors = get_meta_all(soup, "citation_author")
    affiliations = get_meta_all(soup, "citation_author_institution")
    
    # Abstract (from og:description, fallback to citation_abstract)
    abstract = get_meta(soup, "og:description")
    if not abstract:
        abstract = get_meta(soup, "citation_abstract")
    # Clean HTML tags from abstract
    if abstract:
        abstract = re.sub(r'<[^>]+>', '', abstract).strip()
    
    # Citation text
    citation_text = get_meta(soup, "article_references")
    
    article = {
        "doi": get_meta(soup, "citation_doi"),
        "title": get_meta(soup, "citation_title"),
        "authors": authors,
        "affiliations": affiliations,
        "keywords": get_meta_all(soup, "citation_keywords"),
        "abstract": abstract,
        "volume": get_meta(soup, "citation_volume"),
        "issue": get_meta(soup, "citation_issue"),
        "firstpage": get_meta(soup, "citation_firstpage"),
        "lastpage": get_meta(soup, "citation_lastpage"),
        "publication_date": get_meta(soup, "citation_publication_date"),
        "online_date": get_meta(soup, "citation_online_date"),
        "publisher": get_meta(soup, "citation_publisher"),
        "issn": get_meta(soup, "citation_issn"),
        "language": get_meta(soup, "citation_language"),
        "article_type": article_type,
        "received_date": dates.get("received"),
        "revised_date": dates.get("revised"),
        "accepted_date": dates.get("accepted"),
        "published_date": dates.get("published"),
        "views": stats.get("views", 0),
        "downloads": stats.get("downloads", 0),
        "crossref_citations": stats.get("crossref", 0),
        "wos_citations": stats.get("web_of_science", 0),
        "scopus_citations": stats.get("scopus", 0),
        "csdc_citations": stats.get("csdc", 0),
        "pdf_url": get_meta(soup, "citation_pdf_url"),
        "article_url": get_meta(soup, "citation_abstract_html_url"),
        "internal_id": internal_id,
        "ris_url": f"{BASE_URL}/article/download_ris?tag=2&id={internal_id}" if internal_id else None,
        "bibtex_url": f"{BASE_URL}/article/download_ris?tag=3&id={internal_id}" if internal_id else None,
        "citation_text": citation_text,
        "json_ld": json_ld,
    }
    
    return article

def main():
    data_dir = Path(__file__).parent.parent
    
    # Load articles list
    list_file = data_dir / "ecmf_articles_list_2026.json"
    if not list_file.exists():
        print(f"ERROR: {list_file} not found. Run the article list script first.")
        sys.exit(1)
    
    with open(list_file, "r", encoding="utf-8") as f:
        articles_list = json.load(f)
    
    print(f"Found {len(articles_list)} articles to scrape")
    
    results = []
    for i, art in enumerate(articles_list):
        doi = art["doi"]
        print(f"[{i+1}/{len(articles_list)}] {doi}...", end=" ", flush=True)
        try:
            details = scrape_article(doi)
            # Merge with list data (volume, issue from list)
            details["volume"] = art.get("volume", details.get("volume"))
            details["issue"] = art.get("issue", details.get("issue"))
            details["issueIndex"] = art.get("issueIndex")
            results.append(details)
            print(f"OK ({details.get('article_type', 'N/A')})")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(1.5)  # polite delay
    
    # Save results
    output_file = data_dir / "ecmf_articles_2026.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Done! Scraped {len(results)} / {len(articles_list)} articles")
    print(f"Saved to: {output_file}")
    
    # Print summary
    types = {}
    for r in results:
        t = r.get("article_type", "Unknown")
        types[t] = types.get(t, 0) + 1
    print(f"\nArticle types:")
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")
    
    return results

if __name__ == "__main__":
    main()
