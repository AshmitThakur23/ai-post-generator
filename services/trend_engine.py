"""Trend Engine Service - MULTI-SOURCE Intelligence Layer
Fetches REAL trending topics from 5 FREE APIs (no keys needed!)
✅ Google Trends (pytrends)
✅ Reddit JSON API (no auth trick)
✅ Dev.to API
✅ Hashnode GraphQL
✅ HackerNews API

= Investor-level multi-source redundancy
"""

import asyncio
import logging
from typing import List, Optional, Set
from datetime import datetime
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class TrendTopic:
    """Represents a trending topic"""

    title: str
    description: str
    category: str
    source: str
    score: float
    url: Optional[str] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "source": self.source,
            "score": self.score,
            "url": self.url,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class TrendEngine:
    """Multi-source trend intelligence from 5 FREE APIs"""

    CATEGORIES = {
        "AI": ["ai", "machine learning", "gpt", "llm", "neural", "langchain", "chatgpt"],
        "Backend": ["backend", "api", "server", "python", "nodejs", "rust", "golang"],
        "DevOps": ["devops", "kubernetes", "docker", "deployment", "aws"],
        "System Design": ["system design", "architecture", "scalability", "distributed"],
        "Database": ["database", "sql", "nosql", "postgres", "mongodb", "redis"],
    }

    def __init__(self):
        self.logger = logger
        self.client = httpx.AsyncClient(timeout=15.0)
        self.cache = []
        self.last_fetch = None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def get_trending_topics(self, limit: int = 10) -> List[TrendTopic]:
        """
        Fetch trending topics from ALL 5 FREE sources
        
        Args:
            limit: Number of topics to return
        
        Returns:
            List of trending topics (deduplicated, sorted by score)
        """
        self.logger.info("=" * 70)
        self.logger.info("🔄 MULTI-SOURCE FETCH: 5 APIs")
        self.logger.info("=" * 70)

        try:
            # Fetch from all sources in parallel with timeout per source
            results = await asyncio.gather(
                self._fetch_google_trends(),
                self._fetch_reddit_json(),
                self._fetch_devto(),
                self._fetch_hashnode(),
                self._fetch_hackernews(),
                return_exceptions=True,
            )

            # Combine all topics
            all_topics = []
            sources = ["Google Trends", "Reddit", "Dev.to", "Hashnode", "HackerNews"]
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"⚠️  {sources[i]} failed: {type(result).__name__}")
                    continue
                if result:
                    all_topics.extend(result)
                    self.logger.info(f"✅ {sources[i]:15} → {len(result):2} topics")

            if not all_topics:
                self.logger.warning("❌ No topics from any source!")
                return self.cache

            # Deduplicate and sort
            topics = self._deduplicate_topics(all_topics)
            sorted_topics = sorted(topics, key=lambda t: t.score, reverse=True)
            result = sorted_topics[:limit]

            self.logger.info("-" * 70)
            self.logger.info(f"📊 COMBINED: {len(result)} topics from {len(sources)} sources")
            self.logger.info("=" * 70)
            
            self.cache = result
            self.last_fetch = datetime.now()
            return result

        except Exception as e:
            self.logger.error(f"❌ Multi-source error: {str(e)}")
            return self.cache

    # ========================================================================
    # SOURCE 1: Google Trends (100% free - pytrends)
    # ========================================================================

    async def _fetch_google_trends(self) -> List[TrendTopic]:
        """Fetch trending topics from Google Trends via HTTP"""
        try:
            # Try 2 approaches: pytrends, then fallback to RapidAPI or return empty
            loop = asyncio.get_event_loop()
            topics = await loop.run_in_executor(None, self._google_trends_sync)
            return topics or []
        except Exception as e:
            self.logger.debug(f"Google Trends async wrapper error: {type(e).__name__}")
            return []

    def _google_trends_sync(self) -> List[TrendTopic]:
        """Synchronous Google Trends fetch with fallback approach"""
        try:
            # First attempt: use pytrends with minimal configuration
            try:
                from pytrends.request import TrendReq
                
                self.logger.debug("Google Trends: Attempting pytrends...")
                # Most minimal setup possible
                pytrends = TrendReq(hl='en-US', tz=360)
                trending = pytrends.trending_searches(pn='united_states')
                
                if trending is not None and len(trending) > 0:
                    topics = []
                    for i, title in enumerate(trending.head(20).values.flatten(), 1):
                        title = str(title).strip()
                        if not title:
                            continue
                        
                        category = self._categorize_title(title)
                        score = max(60, 100 - (i * 2))
                        
                        topic = TrendTopic(
                            title=title,
                            description="Google Trending (US)",
                            category=category,
                            source="google_trends",
                            score=score,
                            url=f"https://trends.google.com/trends/explore?q={title.replace(' ', '%20')}",
                            timestamp=datetime.now(),
                        )
                        topics.append(topic)
                    
                    if topics:
                        self.logger.info(f"✅ Google Trends: Got {len(topics)} topics")
                        return topics
                    
                self.logger.debug("Google Trends: pytrends returned empty")
                return []
                
            except Exception as e:
                self.logger.debug(f"Google Trends pytrends failed: {type(e).__name__}")
                # Fallback: try Google Trends RSS (more reliable)
                pass

            # Second attempt: Google Trends RSS feed (harder to block)
            try:
                import httpx as httpx_sync
                self.logger.debug("Google Trends: Trying RSS fallback...")
                
                response = httpx_sync.get(
                    "https://trends.google.com/trending/rss?geo=US",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout=10.0,
                    follow_redirects=True,
                )
                
                if response.status_code == 200:
                    import re as re_mod
                    # Parse RSS XML for titles
                    titles = re_mod.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', response.text)
                    if not titles:
                        titles = re_mod.findall(r'<title>(.+?)</title>', response.text)
                    
                    topics = []
                    for i, title in enumerate(titles[:20], 1):
                        title = title.strip()
                        if title in ("Daily Search Trends", "Google Trends", ""):
                            continue
                        category = self._categorize_title(title)
                        score = max(60, 100 - (i * 2))
                        topics.append(TrendTopic(
                            title=title,
                            description="Google Trending (US - RSS)",
                            category=category,
                            source="google_trends",
                            score=score,
                            url=f"https://trends.google.com/trends/explore?q={title.replace(' ', '%20')}",
                            timestamp=datetime.now(),
                        ))
                    
                    if topics:
                        self.logger.info(f"✅ Google Trends (RSS): Got {len(topics)} topics")
                        return topics
                        
            except Exception as e:
                self.logger.debug(f"Google Trends RSS failed: {type(e).__name__}")
            
            return []
        
        except ImportError:
            self.logger.debug("pytrends not available for import")
            return []
        except Exception as e:
            self.logger.debug(f"Google Trends sync: {type(e).__name__}")
            return []

    # ========================================================================
    # SOURCE 2: Reddit JSON API (NO AUTH - just add .json!)
    # ========================================================================

    async def _fetch_reddit_json(self) -> List[TrendTopic]:
        """Fetch from Reddit using JSON trick (no auth needed!)"""
        try:
            subreddits = ["programming", "learnprogramming", "webdev", "devops"]
            topics = []

            for subreddit in subreddits:
                try:
                    # Reddit trick: old.reddit.com + .json - no auth!
                    response = await self.client.get(
                        f"https://old.reddit.com/r/{subreddit}/hot.json?limit=20",
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DataLayerBot/1.0"
                        },
                        timeout=10.0,
                        follow_redirects=True
                    )
                    response.raise_for_status()
                    data = response.json()

                    if "data" not in data or "children" not in data["data"]:
                        continue

                    for i, post in enumerate(data["data"]["children"][:8]):
                        post_data = post.get("data", {})
                        title = post_data.get("title", "").strip()
                        score = post_data.get("score", 0)
                        permalink = post_data.get("permalink", "")
                        url = f"https://reddit.com{permalink}" if permalink else ""

                        if not title or score < 50:
                            continue

                        category = self._categorize_title(title)
                        # Score from 70-100, with position weighting
                        normalized_score = max(70, 100 - (i * 2))
                        
                        topic = TrendTopic(
                            title=title[:100],
                            description=f"Reddit r/{subreddit}: {score} upvotes",
                            category=category,
                            source="reddit",
                            score=normalized_score,
                            url=url,
                            timestamp=datetime.now(),
                        )
                        topics.append(topic)

                except Exception as e:
                    self.logger.debug(f"Reddit r/{subreddit}: {type(e).__name__}")
                    continue

            return topics
        except Exception as e:
            self.logger.error(f"Reddit error: {type(e).__name__}")
            return []

    # ========================================================================
    # SOURCE 3: Dev.to API (unlimited free)
    # ========================================================================

    async def _fetch_devto(self) -> List[TrendTopic]:
        """Fetch trending articles from Dev.to"""
        try:
            # Multiple queries to get diverse content
            queries = [
                "https://dev.to/api/articles?tag=python&per_page=15&sort_by=trending",
                "https://dev.to/api/articles?tag=javascript&per_page=15&sort_by=trending",
                "https://dev.to/api/articles?tag=devops&per_page=15&sort_by=trending",
            ]
            
            topics = []
            for query_url in queries:
                try:
                    response = await self.client.get(query_url, timeout=10.0)
                    response.raise_for_status()
                    articles = response.json()

                    for i, article in enumerate(articles[:10]):
                        title = article.get("title", "").strip()
                        score = article.get("positive_reactions_count", 0)
                        url = article.get("url", "")
                        author = article.get("user", {}).get("name", "Anonymous")
                        published = article.get("published_at", "")

                        if not title:
                            continue

                        category = self._categorize_title(title)
                        # Score from 60-100, with position weighting
                        normalized_score = max(60, 100 - (i * 3))
                        
                        topic = TrendTopic(
                            title=title[:100],
                            description=f"Dev.to by {author}: {score} reactions",
                            category=category,
                            source="devto",
                            score=normalized_score,
                            url=url,
                            timestamp=datetime.now(),
                        )
                        topics.append(topic)
                
                except Exception as e:
                    self.logger.debug(f"Dev.to query error: {type(e).__name__}")
                    continue

            return topics
        except Exception as e:
            self.logger.error(f"Dev.to error: {type(e).__name__}")
            return []

    # ========================================================================
    # SOURCE 4: Hashnode GraphQL (100% free - no auth!)
    # ========================================================================

    async def _fetch_hashnode(self) -> List[TrendTopic]:
        """Fetch from Hashnode GraphQL API"""
        try:
            # More robust GraphQL query
            query = """
            query GetTrendingFeed {
              feed(first: 25) {
                edges {
                  node {
                    title
                    slug
                    brief
                    responseCount
                    author {
                      name
                    }
                  }
                }
              }
            }
            """

            response = await self.client.post(
                "https://gql.hashnode.com/",
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            # Don't raise for status - check manually
            if response.status_code != 200:
                self.logger.debug(f"Hashnode returned {response.status_code}")
                return []
            
            data = response.json()
            
            # Check for GraphQL errors
            if "errors" in data:
                self.logger.debug(f"Hashnode GraphQL error: {data['errors']}")
                return []

            topics = []
            if "data" in data and "feed" in data["data"]:
                for i, edge in enumerate(data["data"]["feed"]["edges"]):
                    node = edge.get("node", {})
                    title = node.get("title", "").strip()
                    slug = node.get("slug", "")
                    brief = node.get("brief", "").strip()
                    score = node.get("responseCount", 0)
                    author = node.get("author", {}).get("name", "")

                    if not title:
                        continue

                    category = self._categorize_title(title)
                    # Score from 60-100, with position weighting
                    normalized_score = max(60, 100 - (i * 2))
                    
                    topic = TrendTopic(
                        title=title[:100],
                        description=f"Hashnode by {author}: {score} responses",
                        category=category,
                        source="hashnode",
                        score=normalized_score,
                        url=f"https://hashnode.com/@{author}/{slug}",
                        timestamp=datetime.now(),
                    )
                    topics.append(topic)

            return topics
        except Exception as e:
            self.logger.error(f"Hashnode error: {type(e).__name__}: {str(e)}")
            return []

    # ========================================================================
    # SOURCE 5: HackerNews (100% free - no auth!)
    # ========================================================================

    async def _fetch_hackernews(self) -> List[TrendTopic]:
        """Fetch from HackerNews API"""
        try:
            response = await self.client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            response.raise_for_status()
            story_ids = response.json()[:20]

            if not story_ids:
                return []

            # Fetch story details in parallel
            tasks = [self._fetch_hn_story(sid) for sid in story_ids[:15]]
            stories = await asyncio.gather(*tasks, return_exceptions=True)

            topics = []
            for position, story in enumerate(stories):
                if isinstance(story, dict) and story:
                    topic = self._story_to_topic(story, position)
                    if topic:
                        topics.append(topic)

            return topics
        except Exception as e:
            self.logger.error(f"HackerNews error: {type(e).__name__}")
            return []

    async def _fetch_hn_story(self, story_id: int) -> Optional[dict]:
        """Fetch single HackerNews story"""
        try:
            response = await self.client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _story_to_topic(self, story: dict, position: int = 0) -> Optional[TrendTopic]:
        """Convert HackerNews story to TrendTopic"""
        try:
            title = story.get("title", "").strip()
            url = story.get("url", "")
            score = story.get("score", 0)
            story_id = story.get("id", 0)

            if not title or score < 10:
                return None

            category = self._categorize_title(title)
            hn_url = f"https://news.ycombinator.com/item?id={story_id}"
            # Score from 70-100, with position weighting
            normalized_score = max(70, 100 - (position * 2))

            return TrendTopic(
                title=title,
                description=f"HackerNews: {score} points",
                category=category,
                source="hackernews",
                score=normalized_score,
                url=url or hn_url,
                timestamp=datetime.now(),
            )
        except Exception:
            return None

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _categorize_title(self, title: str) -> str:
        """Categorize based on keywords"""
        title_lower = title.lower()

        for category, keywords in self.CATEGORIES.items():
            if any(keyword in title_lower for keyword in keywords):
                return category

        return "Backend"

    def _deduplicate_topics(self, topics: List[TrendTopic]) -> List[TrendTopic]:
        """Remove duplicates, keep highest score"""
        seen: Set[str] = set()
        deduplicated = []

        for topic in topics:
            normalized = topic.title.lower().strip()

            if normalized not in seen:
                seen.add(normalized)
                deduplicated.append(topic)
            else:
                existing = next(
                    (t for t in deduplicated if t.title.lower().strip() == normalized),
                    None
                )
                if existing and topic.score > existing.score:
                    deduplicated.remove(existing)
                    deduplicated.append(topic)

        return deduplicated

    async def refresh_trends(self) -> List[TrendTopic]:
        """Refresh trending topics"""
        return await self.get_trending_topics()

    async def calculate_trend(self, data: List[float]) -> Optional[float]:
        """Calculate linear trend"""
        if not data or len(data) < 2:
            return None

        try:
            n = len(data)
            x_mean = (n + 1) / 2
            y_mean = sum(data) / n

            numerator = sum((i + 1 - x_mean) * (data[i] - y_mean) for i in range(n))
            denominator = sum((i + 1 - x_mean) ** 2 for i in range(n))

            return numerator / denominator if denominator != 0 else 0
        except Exception as e:
            self.logger.error(f"Trend calc error: {str(e)}")
            return None

    async def aggregate_trends(self, trends: List[dict]) -> dict:
        """Aggregate trends"""
        return {
            "total_trends": len(trends),
            "average_value": sum(t.get("value", 0) for t in trends) / len(trends)
            if trends
            else 0,
        }
