"""
Template Detector Service - Analyze posts and detect template style
Uses LLM (Groq primary, Gemini fallback) to understand post structure
Fixed: JSON parsing with markdown fence stripping, updated template types
"""

import json
import re
import logging
from typing import Dict, Any, Optional
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def strip_markdown_json(text: str) -> str:
    """Strip markdown code fences from LLM JSON responses.
    Handles: ```json ... ```, ``` ... ```, and raw JSON.
    """
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Already raw JSON
    return text


class TemplateDetector:
    """Detect template type from post analysis"""

    GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
    GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    # Updated template mapping — infographic-focused
    TEMPLATE_MAP = {
        "mind_map": "t1",
        "steps": "t2",
        "comparison": "t3",
        "cheat_sheet": "t4",
        "architecture": "t5",
        "roadmap": "t6",
        "listicle": "t7",
        "explainer": "t8",
        # Legacy fallbacks
        "flow": "t1",
        "grid": "t3",
        "list": "t7",
        "infographic": "t8",
    }

    def __init__(self):
        """Initialize template detector"""
        self.groq_key = settings.GROQ_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        self.timeout = 15
        logger.info("✅ TemplateDetector initialized")

    async def detect_template(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze post and detect template type.

        Returns:
            {
                "template_id": "t1",
                "template_type": "mind_map",
                "section_count": 5,
                "style": "colorful",
                "confidence": 0.95
            }
        """
        title = post.get("title", "")
        description = post.get("description", "")
        source = post.get("source", "")
        tags = ", ".join(post.get("tags", []))

        logger.info(f"🔍 Detecting template for: {title[:60]}...")

        prompt = f"""Analyze this social media post and determine its INFOGRAPHIC template structure:

Title: {title}
Description: {description}
Source: {source}
Tags: {tags}

Classify into ONE template type:
- mind_map: Central concept with branching categories (ecosystem, landscape, overview)
- steps: Step-by-step numbered guide (how-to, tutorial)
- comparison: Side-by-side comparison of tools/frameworks (vs, differences)
- cheat_sheet: Dense reference card with commands/shortcuts
- architecture: System components with connections/arrows (system design)
- roadmap: Sequential timeline/milestones (career path, learning path)
- listicle: Numbered list of items (top 10, best tools, resources)
- explainer: Visual breakdown of a concept (how it works, explained)

Also analyze:
- How many main sections? (3-8)
- Style: dark / minimal / colorful / professional

IMPORTANT: Return ONLY valid JSON, NO markdown:

{{"template_type": "mind_map", "section_count": 6, "style": "colorful", "confidence": 0.85, "reasoning": "Brief explanation"}}
"""

        # Try Groq first, then Gemini, then default
        for provider_name, call_fn in [("Groq", self._call_groq), ("Gemini", self._call_gemini)]:
            try:
                result = await call_fn(prompt)
                if result:
                    logger.info(f"✅ Template detected ({provider_name}): {result.get('template_type')}")
                    return self._map_template(result)
            except Exception as e:
                logger.warning(f"⚠️ {provider_name} failed: {e}")

        # Default fallback
        logger.warning("⚠️ Using default template (mind_map)")
        return {
            "template_id": "t1",
            "template_type": "mind_map",
            "section_count": 5,
            "style": "colorful",
            "confidence": 0.0,
        }

    async def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq API with robust JSON parsing"""
        if not self.groq_key:
            return None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.GROQ_API,
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 300,
                    },
                )
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Strip markdown fences before parsing
                clean_json = strip_markdown_json(content)
                return json.loads(clean_json)

            except json.JSONDecodeError as e:
                logger.warning(f"Groq JSON parse error: {e}")
                return None
            except Exception as e:
                logger.error(f"Groq error: {e}")
                return None

    async def _call_gemini(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Gemini API with robust JSON parsing"""
        if not self.gemini_key:
            return None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.GEMINI_API}?key={self.gemini_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 300,
                        },
                    },
                )
                response.raise_for_status()

                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]

                # Strip markdown fences before parsing
                clean_json = strip_markdown_json(content)
                return json.loads(clean_json)

            except json.JSONDecodeError as e:
                logger.warning(f"Gemini JSON parse error: {e}")
                return None
            except Exception as e:
                logger.error(f"Gemini error: {e}")
                return None

    def _map_template(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Map detected template to internal template ID"""
        template_type = detection.get("template_type", "mind_map").lower().strip()

        # Find best match
        template_id = self.TEMPLATE_MAP.get(template_type, "t1")

        return {
            "template_id": template_id,
            "template_type": template_type,
            "section_count": max(3, min(8, detection.get("section_count", 5))),
            "style": detection.get("style", "colorful"),
            "confidence": detection.get("confidence", 0.5),
        }
