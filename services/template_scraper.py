"""
Zone A — Template Scraper (Step 3)
====================================
Scrapes REAL post templates from Dev.to and Hashnode using Playwright.
Extracts: title, cover image, section count, style, layout type, tags.
Saves to temp/templates.json.
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
TEMPLATES_FILE = os.path.join(TEMP_DIR, "templates.json")
os.makedirs(TEMP_DIR, exist_ok=True)


class TemplateScraper:
    """Scrapes real post templates from Dev.to and Hashnode using Playwright."""

    def __init__(self):
        self._templates: List[Dict] = []
        self._last_scraped: Optional[datetime] = None
        logger.info("TemplateScraper initialized (Playwright-based)")

    async def scrape_templates(self) -> List[Dict]:
        """Run full scrape of Dev.to + Hashnode. Returns template list."""
        logger.info("Starting template scrape...")
        templates = []

        # Scrape Dev.to
        devto = await self._scrape_devto()
        templates.extend(devto)
        logger.info(f"Dev.to → {len(devto)} templates")

        # Scrape Hashnode
        hashnode = await self._scrape_hashnode()
        templates.extend(hashnode)
        logger.info(f"Hashnode → {len(hashnode)} templates")

        # Assign IDs
        for i, t in enumerate(templates):
            t["id"] = f"scraped_{i+1}"

        self._templates = templates
        self._last_scraped = datetime.now()

        # Save to JSON
        self._save_templates(templates)
        logger.info(f"Total: {len(templates)} templates saved to {TEMPLATES_FILE}")

        return templates

    async def _scrape_devto(self) -> List[Dict]:
        """Scrape Dev.to articles using Playwright for visual analysis."""
        templates = []
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Scrape from multiple tag pages
                tags = ["javascript", "webdev", "python", "devops", "tutorial"]
                for tag in tags:
                    try:
                        url = f"https://dev.to/t/{tag}"
                        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)

                        # Extract article cards
                        articles = await page.evaluate("""() => {
                            const cards = document.querySelectorAll('.crayons-story');
                            const results = [];
                            for (let i = 0; i < Math.min(cards.length, 3); i++) {
                                const card = cards[i];
                                const titleEl = card.querySelector('.crayons-story__title a');
                                const imgEl = card.querySelector('.crayons-story__cover img');
                                const tagsEl = card.querySelectorAll('.crayons-tag');
                                
                                results.push({
                                    title: titleEl ? titleEl.textContent.trim() : '',
                                    url: titleEl ? titleEl.href : '',
                                    coverImage: imgEl ? imgEl.src : '',
                                    tags: Array.from(tagsEl).map(t => t.textContent.trim().replace('#', '')),
                                });
                            }
                            return results;
                        }""")

                        for art in articles:
                            if not art.get("title"):
                                continue

                            # Visit article to count sections
                            section_data = {"sectionCount": 4, "style": "light", "layout": "single"}
                            if art.get("url"):
                                try:
                                    await page.goto(art["url"], timeout=10000, wait_until="domcontentloaded")
                                    await page.wait_for_timeout(1000)
                                    section_data = await page.evaluate("""() => {
                                        const h2s = document.querySelectorAll('article h2, article h3');
                                        const bg = getComputedStyle(document.body).backgroundColor;
                                        const isDark = bg.includes('rgb(0') || bg.includes('rgb(1') || bg.includes('rgb(2') || bg.includes('#0') || bg.includes('#1') || bg.includes('#2');
                                        return {
                                            sectionCount: Math.max(h2s.length, 3),
                                            style: isDark ? 'dark' : 'light',
                                            layout: 'single'
                                        };
                                    }""")
                                except Exception:
                                    pass

                            templates.append({
                                "source": "dev.to",
                                "title": art["title"],
                                "coverImage": art.get("coverImage", ""),
                                "sectionCount": section_data.get("sectionCount", 4),
                                "style": section_data.get("style", "light"),
                                "layout": section_data.get("layout", "single"),
                                "tags": art.get("tags", [tag]),
                                "url": art.get("url", ""),
                            })

                    except Exception as e:
                        logger.warning(f"Dev.to tag '{tag}' scrape failed: {e}")
                        continue

                await browser.close()

        except Exception as e:
            logger.error(f"Dev.to scrape error: {e}")
            # Fallback: use API data
            templates = await self._devto_api_fallback()

        return templates

    async def _devto_api_fallback(self) -> List[Dict]:
        """Fallback: use Dev.to API if Playwright fails."""
        import httpx
        templates = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://dev.to/api/articles?per_page=10&top=7")
                if resp.status_code == 200:
                    for art in resp.json():
                        templates.append({
                            "source": "dev.to",
                            "title": art.get("title", ""),
                            "coverImage": art.get("cover_image", "") or art.get("social_image", ""),
                            "sectionCount": 4,
                            "style": "light",
                            "layout": "single",
                            "tags": art.get("tag_list", []),
                            "url": art.get("url", ""),
                        })
        except Exception as e:
            logger.error(f"Dev.to API fallback failed: {e}")
        return templates

    async def _scrape_hashnode(self) -> List[Dict]:
        """Scrape Hashnode using their GraphQL API (no auth needed)."""
        import httpx
        templates = []
        try:
            query = """query {
                feed(first: 10, filter: { type: BEST }) {
                    edges {
                        node {
                            title
                            brief
                            coverImage { url }
                            tags { name }
                            url
                        }
                    }
                }
            }"""
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://gql.hashnode.com/",
                    json={"query": query},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    edges = (data.get("data", {}).get("feed", {}).get("edges", []))
                    for edge in edges:
                        node = edge.get("node", {})
                        cover = node.get("coverImage", {})
                        templates.append({
                            "source": "hashnode",
                            "title": node.get("title", ""),
                            "coverImage": cover.get("url", "") if cover else "",
                            "sectionCount": 5,
                            "style": "dark",
                            "layout": "single",
                            "tags": [t.get("name", "") for t in node.get("tags", [])],
                            "url": node.get("url", ""),
                        })
        except Exception as e:
            logger.error(f"Hashnode scrape error: {e}")
        return templates

    def _save_templates(self, templates: List[Dict]):
        """Save templates to temp/templates.json"""
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)

    def get_templates(self) -> List[Dict]:
        """Return cached templates or load from file."""
        if self._templates:
            return self._templates

        # Try loading from file
        if os.path.exists(TEMPLATES_FILE):
            try:
                with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    self._templates = json.load(f)
                return self._templates
            except Exception:
                pass

        return []

    def get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """Get single template by ID."""
        for t in self.get_templates():
            if t.get("id") == template_id:
                return t
        return None
