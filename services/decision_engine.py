"""Decision Engine - Input + Decision Logic for AI Content Generation
Selects best topic + templates + generates content structure
"""

import logging
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fallback static topics if trends API fails
FALLBACK_TOPICS = [
    {
        "title": "AI agents are reshaping software development",
        "category": "AI",
        "score": 95,
        "description": "Latest trends in AI-powered agents",
        "source": "fallback",
    },
    {
        "title": "Microservices architecture patterns",
        "category": "System Design",
        "score": 90,
        "description": "Best practices for distributed systems",
        "source": "fallback",
    },
    {
        "title": "Backend scalability at scale",
        "category": "Backend",
        "score": 88,
        "description": "Handling millions of requests",
        "source": "fallback",
    },
]

PREFERRED_CATEGORIES = {"AI", "System Design", "Backend"}

PLATFORM_TEMPLATES = {
    "linkedin": {
        "layouts": {"flow"},
        "sections_range": (4, 6),
        "description": "Professional, flow-based, thought leadership",
    },
    "instagram": {
        "layouts": {"grid", "list"},
        "sections_range": (2, 4),
        "description": "Visual, minimal, attention-grabbing",
    },
}

# Keyword mapping for difficulty levels
DIFFICULTY_KEYWORDS = {
    "advanced": [
        "architecture", "system design", "microservices", "kubernetes",
        "distributed", "scalability", "deployment", "optimization",
        "performance", "infrastructure", "networking", "protocol",
        "algorithm", "complexity", "concurrency", "consensus",
    ],
    "beginner": [
        "intro", "basics", "getting started", "tutorial", "learn",
        "simple", "guide", "beginner", "start", "setup", "hello world",
        "javascript", "python basics", "web", "css", "html",
    ],
    "intermediate": [
        "practical", "pattern", "best practices", "tips", "tricks",
        "debugging", "testing", "code review", "refactor", "improve",
        "framework", "library", "tools", "workflow", "development",
    ],
}

# Style hint generation based on platform and category
STYLE_HINTS = {
    "linkedin": {
        "AI": "dark tech infographic with flow arrows, neural networks",
        "Backend": "minimalist system design diagram, blue-white palette",
        "System Design": "clean architecture diagram, grayscale with accent colors",
        "DevOps": "infrastructure topology, tech stack visualization",
        "Database": "database schema, data flow diagram",
    },
    "instagram": {
        "AI": "vibrant gradient, AI robots, neon elements",
        "Backend": "code snippets, colorful syntax highlighting",
        "System Design": "bold geometric shapes, modern minimalism",
        "DevOps": "pipeline flow, deployment stages with icons",
        "Database": "data visualization, colorful charts and graphs",
    },
}


@dataclass
class ContentPlan:
    """Represents structured content plan"""

    title: str
    sections: List[str]
    key_points: List[str]
    call_to_action: str

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "sections": self.sections,
            "key_points": self.key_points,
            "call_to_action": self.call_to_action,
        }


@dataclass
class DecisionOutput:
    """Output of decision engine"""

    id: str  # UUID for tracking
    final_topic: str
    category: str
    source: str
    score: float
    difficulty: str  # beginner | intermediate | advanced
    style_hint: str  # For image generation
    selected_templates: List[Dict[str, Any]]
    content_plan: ContentPlan
    platform: str
    reasoning: str

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "final_topic": self.final_topic,
            "category": self.category,
            "source": self.source,
            "score": self.score,
            "difficulty": self.difficulty,
            "style_hint": self.style_hint,
            "selected_templates": self.selected_templates,
            "content_plan": self.content_plan.to_dict(),
            "platform": self.platform,
            "reasoning": self.reasoning,
        }


class DecisionEngine:
    """Input + Decision Logic for AI Content Generation"""

    def __init__(self, trend_engine=None, template_provider=None):
        """Initialize with dependencies"""
        self.trend_engine = trend_engine
        self.template_provider = template_provider
        self.logger = logging.getLogger(__name__)

    async def decide(
        self,
        topic: Optional[str] = None,
        platform: str = "linkedin",
        num_templates: int = 3,
        selected_template: Optional[Dict[str, Any]] = None,
    ) -> DecisionOutput:
        """
        Main decision logic: Select best topic + templates + content structure

        Args:
            topic: Optional user-provided topic
            platform: "linkedin" or "instagram"
            num_templates: Number of templates to select
            selected_template: Pre-selected template from user (template-first flow)

        Returns:
            DecisionOutput with final topic, templates, and content plan
        """
        # Generate unique ID for tracking
        decision_id = str(uuid.uuid4())[:8]
        
        self.logger.info(
            f"🤖 DECISION ENGINE [ID: {decision_id}]: topic={topic}, platform={platform}, num_templates={num_templates}, template_provided={selected_template is not None}"
        )

        # ================================================================
        # STEP 1: Topic Selection
        # ================================================================
        if topic:
            # User provided topic - auto-detect category
            selected_topic = topic
            selected_category = self._detect_category(topic)
            selected_source = "user_input"
            selected_score = 100.0

            self.logger.info(f"✅ Using user-provided topic: {topic} (category: {selected_category})")

        else:
            # Fetch from trends and select best
            (
                selected_topic,
                selected_category,
                selected_source,
                selected_score,
            ) = await self._select_best_topic()

            self.logger.info(f"✅ Selected topic: {selected_topic} (score: {selected_score})")

        # ================================================================
        # STEP 2: Template Selection
        # ================================================================
        # 🎯 NEW: If user pre-selected a template, use it!
        if selected_template:
            selected_templates = [selected_template]
            self.logger.info(f"✅ Using user-selected template: {selected_template.get('name', 'Unknown')}")
        else:
            selected_templates = await self._select_templates(
                platform=platform, num_templates=num_templates
            )

        self.logger.info(
            f"✅ Selected {len(selected_templates)} templates for {platform}"
        )

        # ================================================================
        # STEP 3: Difficulty Detection
        # ================================================================
        difficulty = self._detect_difficulty(selected_topic, selected_category)
        
        # ================================================================
        # STEP 4: Style Hint Generation
        # ================================================================
        style_hint = self._generate_style_hint(selected_category, platform)

        # ================================================================
        # STEP 5: Content Plan Generation
        # ================================================================
        content_plan = self._generate_content_plan(
            topic=selected_topic,
            category=selected_category,
            platform=platform,
            templates=selected_templates,
        )

        self.logger.info(f"✅ Generated content plan with {len(content_plan.sections)} sections")

        # ================================================================
        # STEP 6: Return Decision
        # ================================================================
        decision = DecisionOutput(
            id=decision_id,
            final_topic=selected_topic,
            category=selected_category,
            source=selected_source,
            score=selected_score,
            difficulty=difficulty,
            style_hint=style_hint,
            selected_templates=selected_templates,
            content_plan=content_plan,
            platform=platform,
            reasoning=f"Selected {selected_category} topic ({difficulty} level) with score {selected_score:.1f}. "
            f"Templates optimized for {platform}. Style: {style_hint}",
        )

        self.logger.info("🎯 DECISION COMPLETE")
        return decision

    async def _select_best_topic(self) -> tuple:
        """
        Fetch trends and select best topic based on:
        - Score (highest)
        - Category (AI, System Design, Backend preferred)

        Returns:
            (topic, category, source, score)
        """
        try:
            if not self.trend_engine:
                self.logger.warning("Trend engine not available, using fallback topics")
                return self._select_from_fallback()

            # Fetch 20 trends
            topics = await self.trend_engine.get_trending_topics(limit=20)

            if not topics:
                self.logger.warning("No topics fetched, using fallback")
                return self._select_from_fallback()

            # Sort by preferred category, then score
            preferred = []
            other = []

            for topic in topics:
                if topic.category in PREFERRED_CATEGORIES:
                    preferred.append(topic)
                else:
                    other.append(topic)

            # Sort preferred by score (descending)
            preferred.sort(key=lambda x: x.score, reverse=True)

            if preferred:
                best = preferred[0]
            else:
                # Fallback to highest score regardless of category
                topics.sort(key=lambda x: x.score, reverse=True)
                best = topics[0]

            return (best.title, best.category, best.source, best.score)

        except Exception as e:
            self.logger.error(f"Error selecting topic: {str(e)}")
            return self._select_from_fallback()

    def _select_from_fallback(self) -> tuple:
        """Select from static fallback topics"""
        topic = FALLBACK_TOPICS[0]
        return (topic["title"], topic["category"], topic["source"], topic["score"])

    async def _select_templates(
        self, platform: str = "linkedin", num_templates: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Select templates based on:
        - Platform (linkedin = flow layout, instagram = visual)
        - Sections count (4-6 preferred)

        Returns:
            List of selected template dictionaries
        """
        try:
            if not self.template_provider:
                self.logger.warning("Template provider not available")
                return []

            all_templates = await self.template_provider.get_all_templates()

            if not all_templates:
                self.logger.warning("No templates available")
                return []

            self.logger.debug(f"Available templates: {len(all_templates)}")

            # Get platform preferences
            platform_config = PLATFORM_TEMPLATES.get(
                platform, PLATFORM_TEMPLATES["linkedin"]
            )
            preferred_layouts = platform_config["layouts"]
            preferred_sections = platform_config["sections_range"]

            self.logger.debug(f"Platform: {platform}, Preferred layouts: {preferred_layouts}, Sections: {preferred_sections}")

            # Filter templates by layout
            filtered = [
                t
                for t in all_templates
                if t.layout in preferred_layouts
            ]

            self.logger.debug(f"After layout filter: {len(filtered)} templates")

            # If not enough, add any template
            if len(filtered) < num_templates:
                filtered.extend([t for t in all_templates if t not in filtered])

            self.logger.debug(f"After extending: {len(filtered)} templates")

            # Sort by section count closeness to preferred range
            min_sec, max_sec = preferred_sections
            filtered.sort(
                key=lambda t: abs(t.sections - ((min_sec + max_sec) / 2))
            )

            # Take top N
            selected = filtered[:num_templates]

            self.logger.info(f"Selected {len(selected)} templates for {platform}")

            # Convert to dicts
            result = [
                {
                    "id": t.id,
                    "name": t.name,
                    "layout": t.layout,
                    "sections": t.sections,
                    "style": t.style,
                }
                for t in selected
            ]

            return result

        except Exception as e:
            self.logger.error(f"Error selecting templates: {str(e)}", exc_info=True)
            return []

    def _detect_category(self, topic: str) -> str:
        """
        Auto-detect category from topic text using keyword matching
        Returns: AI | System Design | Backend | DevOps | Database | (detected keyword)
        """
        topic_lower = topic.lower()
        
        # Check for AI-related keywords
        ai_keywords = ["ai", "artificial intelligence", "machine learning", "llm", "neural", "gpt", "agent", "deep learning"]
        if any(kw in topic_lower for kw in ai_keywords):
            return "AI"
        
        # Check for System Design keywords
        design_keywords = ["architecture", "system design", "scalability", "distributed", "microservices"]
        if any(kw in topic_lower for kw in design_keywords):
            return "System Design"
        
        # Check for Backend keywords
        backend_keywords = ["backend", "server", "api", "database", "sql", "nosql", "rest", "graphql"]
        if any(kw in topic_lower for kw in backend_keywords):
            return "Backend"
        
        # Check for DevOps keywords
        devops_keywords = ["devops", "deployment", "kubernetes", "docker", "ci/cd", "infrastructure", "cloud"]
        if any(kw in topic_lower for kw in devops_keywords):
            return "DevOps"
        
        # Check for Database keywords
        db_keywords = ["database", "postgres", "mongodb", "redis", "cassandra", "indexing", "query"]
        if any(kw in topic_lower for kw in db_keywords):
            return "Database"
        
        # Default to Backend if no match
        return "Backend"

    def _detect_difficulty(self, topic: str, category: str) -> str:
        """
        Detect difficulty level based on topic keywords and category
        Returns: beginner | intermediate | advanced
        """
        topic_lower = topic.lower()
        
        # Count keyword matches for each difficulty
        advanced_count = sum(1 for kw in DIFFICULTY_KEYWORDS["advanced"] if kw in topic_lower)
        beginner_count = sum(1 for kw in DIFFICULTY_KEYWORDS["beginner"] if kw in topic_lower)
        intermediate_count = sum(1 for kw in DIFFICULTY_KEYWORDS["intermediate"] if kw in topic_lower)
        
        # Determine difficulty
        if advanced_count > intermediate_count and advanced_count > beginner_count:
            return "advanced"
        elif beginner_count > intermediate_count and beginner_count > advanced_count:
            return "beginner"
        elif intermediate_count > 0:
            return "intermediate"
        else:
            # Default based on category
            if category in ["System Design", "DevOps"]:
                return "advanced"
            elif category in ["AI", "Database"]:
                return "intermediate"
            else:
                return "intermediate"

    def _generate_style_hint(self, category: str, platform: str) -> str:
        """
        Generate style hint for image generation based on category and platform
        Returns: Description of visual style for image generation
        """
        try:
            # Get from lookup table
            style_map = STYLE_HINTS.get(platform, STYLE_HINTS["linkedin"])
            return style_map.get(category, style_map.get("Backend", "minimalist tech design"))
        except Exception as e:
            self.logger.error(f"Error generating style hint: {str(e)}")
            return "professional tech design"

    def _generate_content_plan(
        self,
        topic: str,
        category: str,
        platform: str,
        templates: List[Dict[str, Any]],
    ) -> ContentPlan:
        """
        Generate structured content plan based on topic + platform

        Returns:
            ContentPlan with title, sections, key points, CTA
        """
        # Default structure
        if platform == "linkedin":
            sections = [
                "Intro: Why this matters",
                "Core Concept",
                "Real-world Architecture",
                "Implementation Tips",
                "Key Takeaway",
                "Call to Action",
            ]
            key_points = [
                "Industry trend",
                "Technical depth",
                "Practical value",
                "Business impact",
            ]
            cta = "Share your thoughts in the comments"

        else:  # instagram
            sections = [
                "Hook",
                "Main Insight",
                "Actionable Tip",
                "Summary",
            ]
            key_points = [
                "Visual appeal",
                "Quick learning",
                "Shareable insight",
            ]
            cta = "Save this for later"

        return ContentPlan(
            title=topic,
            sections=sections,
            key_points=key_points,
            call_to_action=cta,
        )
