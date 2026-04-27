"""Content Generator Service - Step 3 of AI Pipeline
Generates full content for ALL sections in a SINGLE LLM call (batched).
Uses Groq (primary) + Gemini (fallback).
Fixed: batched generation (7→1 calls), accurate ai_provider tracking, JSON fence stripping.
"""

import logging
import json
import re
import os
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

GROQ_TIMEOUT = 30.0
GEMINI_TIMEOUT = 30.0


def strip_markdown_json(text: str) -> str:
    """Strip markdown code fences from LLM responses."""
    text = text.strip()
    pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


class SectionContent:
    """Generated content for a single section"""

    def __init__(self, heading: str, content: str):
        self.heading = heading
        self.content = content

    def to_dict(self):
        return {"heading": self.heading, "content": self.content}


class ContentGenerationOutput:
    """Full generated content output"""

    def __init__(self, id, title, sections, caption, hashtags, platform, category, style_hint="", ai_provider="groq"):
        self.id = id
        self.title = title
        self.sections = sections
        self.caption = caption
        self.hashtags = hashtags
        self.platform = platform
        self.category = category
        self.style_hint = style_hint
        self.ai_provider = ai_provider

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "caption": self.caption,
            "hashtags": self.hashtags,
            "platform": self.platform,
            "category": self.category,
            "style_hint": self.style_hint,
            "ai_provider": self.ai_provider,
        }


class ContentGenerator:
    """AI Content Generation using Groq + Gemini fallback — BATCHED"""

    def __init__(self, groq_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key
        self.gemini_api_key = gemini_api_key
        preferred_groq_model = os.getenv("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
        self.groq_models = [preferred_groq_model, "llama-3.1-8b-instant"]
        self.gemini_model = "gemini-2.0-flash"

        if not groq_api_key and not gemini_api_key:
            logger.warning("⚠️ No API keys configured for content generation")

    async def generate(self, decision_data: Dict[str, Any]) -> ContentGenerationOutput:
        """
        Generate ALL content in a SINGLE batched LLM call.
        """
        topic = decision_data.get("final_topic", "")
        category = decision_data.get("category", "General")
        difficulty = decision_data.get("difficulty", "intermediate")
        platform = decision_data.get("platform", "linkedin")
        content_plan = decision_data.get("content_plan", {})
        style_hint = decision_data.get("style_hint", "")
        decision_id = decision_data.get("id", "unknown")

        sections_plan = content_plan.get("sections", [])
        key_points = content_plan.get("key_points", [])
        title = content_plan.get("title", topic)
        selected_templates = decision_data.get("selected_templates", [])

        template_style = "professional-clean"
        template_layout = "flow"
        if selected_templates and isinstance(selected_templates, list):
            first_template = selected_templates[0] if selected_templates else {}
            if isinstance(first_template, dict):
                template_style = first_template.get("style", template_style)
                template_layout = first_template.get("layout", template_layout)

        logger.info(f"📝 Generating ALL content in 1 batched call for: {topic}")

        # Build the batched prompt
        sections_list = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(sections_plan)])
        key_points_str = ", ".join(key_points[:5])
        difficulty_instruction = self._get_difficulty_instruction(difficulty)
        platform_tone = self._get_platform_tone(platform)

        prompt = f"""You are a world-class technical content strategist.
    Generate premium, highly-readable {platform} infographic post content.

Topic: {topic}
Category: {category}
Difficulty: {difficulty}
Tone: {platform_tone}
Visual style: {template_style}
Visual layout: {template_layout}
Key Points: {key_points_str}

{difficulty_instruction}

Generate content for ALL these sections:
{sections_list}

IMPORTANT: Return ONLY valid JSON (no markdown fences):

{{
  "sections": [
    {{"heading": "Section Name", "content": "2-4 sentence content for this section"}}
  ],
  "caption": "3-5 sentence social media caption with Hook → Explanation → CTA",
  "title": "Enhanced engaging title"
}}

Requirements:
- Return exactly {len(sections_plan)} sections in the same logical order as requested.
- Each section: 2-4 concise, high-signal, actionable sentences.
- Start each section with a strong insight, then practical context.
- Avoid fluff, generic claims, and repeated wording.
- Sections must flow logically and NOT repeat each other.
- Caption format: Hook (1 line) → Value explanation (2-3 lines) → CTA (1 line).
- Make it educational, shareable, and executive-friendly.
- Title should be specific and curiosity-driven, not clickbait.
- {"No emojis in caption" if platform == "linkedin" else "Include 1-2 emojis in caption"}
JSON STRICTNESS:
- Output raw JSON only.
- Use double quotes on all keys and string values.
- No trailing commas.
"""

        # Try Groq first, then Gemini
        actual_provider = "fallback"
        result_json = None

        if self.groq_api_key:
            raw = await self._call_groq(prompt)
            if raw:
                result_json = self._parse_json_response(raw)
                if result_json:
                    actual_provider = "groq"

        if not result_json and self.gemini_api_key:
            logger.info("⚠️ Groq failed, falling back to Gemini")
            raw = await self._call_gemini(prompt)
            if raw:
                result_json = self._parse_json_response(raw)
                if result_json:
                    actual_provider = "gemini"

        # Build output
        if result_json:
            sections_content = [
                SectionContent(s.get("heading", f"Section {i+1}"), s.get("content", ""))
                for i, s in enumerate(result_json.get("sections", []))
            ]
            caption = result_json.get("caption", "")
            title = result_json.get("title", title)
        else:
            # Fallback
            logger.warning("🚨 Both AI providers failed — using fallback content")
            sections_content = [
                SectionContent(heading, self._get_fallback_content(heading, difficulty))
                for heading in sections_plan
            ]
            caption = self._get_fallback_caption(topic, platform)

        hashtags = self._generate_hashtags(topic, category, platform)

        logger.info(f"✅ Content generated: {len(sections_content)} sections, provider={actual_provider}")

        return ContentGenerationOutput(
            id=decision_id,
            title=title,
            sections=sections_content,
            caption=caption,
            hashtags=hashtags,
            platform=platform,
            category=category,
            style_hint=style_hint,
            ai_provider=actual_provider,
        )

    def _parse_json_response(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response, stripping markdown fences."""
        clean = strip_markdown_json(raw)

        # Attempt 1: direct parse
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract likely JSON object block
        first = clean.find("{")
        last = clean.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = clean[first:last + 1]
        else:
            candidate = clean

        # Attempt 3: remove trailing commas before closing brackets/braces
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return None

    async def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API"""
        if not self.groq_api_key:
            return None
        tried = set()
        for model_name in self.groq_models:
            if not model_name or model_name in tried:
                continue
            tried.add(model_name)
            try:
                async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.4,
                            "max_tokens": 2200,
                        },
                    )
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        logger.info("✅ Groq API call successful (%s)", model_name)
                        return content

                logger.warning("Groq API error (%s): %s - %s", model_name, response.status_code, response.text[:200])
            except httpx.TimeoutException:
                logger.warning("⏱️ Groq API timeout (%s)", model_name)
            except Exception as e:
                logger.warning("🚨 Groq API error (%s): %s", model_name, str(e))

        return None

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API"""
        if not self.gemini_api_key:
            return None
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.45,
                "maxOutputTokens": 4096,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
                response = await client.post(endpoint, json=payload)
            if response.status_code != 200:
                logger.error("Gemini API error: %s - %s", response.status_code, response.text[:200])
                return None

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if content:
                logger.info("✅ Gemini API call successful (%s)", self.gemini_model)
                return content
            return None
        except httpx.TimeoutException:
            logger.error("⏱️ Gemini API timeout")
            return None
        except Exception as e:
            logger.error("🚨 Gemini API error: %s", str(e))
            return None

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _generate_hashtags(self, topic: str, category: str, platform: str) -> List[str]:
        """Generate 5-8 relevant hashtags"""
        category_tags = {
            "AI": ["#AI", "#MachineLearning", "#LLM", "#DeepLearning", "#GenerativeAI", "#NeuralNetworks", "#DataScience"],
            "System Design": ["#SystemDesign", "#Architecture", "#Scalability", "#Distributed", "#Microservices", "#HighPerformance"],
            "Backend": ["#Backend", "#API", "#Programming", "#SoftwareDevelopment", "#DevOps", "#WebDevelopment"],
            "DevOps": ["#DevOps", "#Docker", "#Kubernetes", "#CICD", "#CloudNative", "#Infrastructure"],
            "Database": ["#Database", "#SQL", "#NoSQL", "#DataEngineering", "#Performance", "#Optimization"],
        }

        tags = category_tags.get(category, ["#Technology", "#Development", "#Programming", "#SoftwareEngineering", "#CodeLife"])

        if platform == "instagram":
            tags.extend(["#TechTok", "#DeveloperLife", "#DevCommunity"])
        elif platform == "linkedin":
            tags.extend(["#TechLeadership", "#SoftwareEngineering", "#CareerGrowth", "#Innovation"])

        unique_tags = list(dict.fromkeys(tags))
        if len(unique_tags) > 8:
            unique_tags = unique_tags[:8]

        generic = ["#TechInnovation", "#NextGen", "#FutureOfTech"]
        while len(unique_tags) < 5:
            for tag in generic:
                if tag not in unique_tags:
                    unique_tags.append(tag)
                    if len(unique_tags) >= 5:
                        break

        return unique_tags[:8]

    def _get_difficulty_instruction(self, difficulty: str) -> str:
        instructions = {
            "beginner": "Explain in simple terms. Avoid jargon. Focus on basics.",
            "intermediate": "Balance technical depth with accessibility.",
            "advanced": "Assume expert knowledge. Include technical depth and nuanced insights.",
        }
        return instructions.get(difficulty, instructions["intermediate"])

    def _get_platform_tone(self, platform: str) -> str:
        tones = {
            "linkedin": "Professional, educational, thought-leadership style",
            "instagram": "Conversational, visual-friendly, bite-sized insights",
        }
        return tones.get(platform, "Professional and engaging")

    def _get_fallback_content(self, section_heading: str, difficulty: str) -> str:
        fallbacks = {
            "beginner": "This covers the fundamentals. Start here to build your foundation.",
            "intermediate": "Build on the basics with practical applications and real-world examples.",
            "advanced": "Deep dive into technical implementation and advanced patterns.",
        }
        base = fallbacks.get(difficulty, fallbacks["intermediate"])
        return f"{section_heading}: {base}"

    def _get_fallback_caption(self, topic: str, platform: str) -> str:
        if platform == "instagram":
            return f"Explore the latest on: {topic}\n\nWhat's your take? 💭\n\n#TechTok #Development"
        return f"Insights on: {topic}\n\nKey takeaway: Understanding the fundamentals is crucial.\n\nWhat's your experience? Share in the comments! 👇"

    async def close(self):
        pass
