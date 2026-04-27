"""
Step 5: Export Engine
Combines content + image into post-ready outputs for multiple platforms
"""

import logging
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)


class CaptionVariation:
    """Represents a caption variation for a specific platform"""
    
    def __init__(self, text: str, style: str, length: int):
        self.text = text
        self.style = style  # "professional", "casual", "technical", "catchy"
        self.length = length
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "style": self.style,
            "length": self.length,
            "char_count": len(self.text)
        }


class PlatformFormatter:
    """Handles platform-specific formatting"""
    
    PLATFORM_SPECS = {
        "linkedin": {
            "max_caption_length": 3000,
            "tone": "professional",
            "hashtag_max": 8,
            "line_break": "\n",
            "emoji_style": "minimal",
            "cta": "💼 Let me know your thoughts! 👇"
        },
        "instagram": {
            "max_caption_length": 2200,
            "tone": "casual_catchy",
            "hashtag_max": 30,
            "line_break": "\n",
            "emoji_style": "vibrant",
            "cta": "💭 What's your take? 👇"
        },
        "twitter": {
            "max_caption_length": 280,
            "tone": "casual",
            "hashtag_max": 3,
            "line_break": " ",
            "emoji_style": "minimal",
            "cta": ""
        },
        "default": {
            "max_caption_length": 500,
            "tone": "balanced",
            "hashtag_max": 10,
            "line_break": "\n",
            "emoji_style": "minimal",
            "cta": ""
        }
    }
    
    @staticmethod
    def get_platform_spec(platform: str) -> Dict[str, Any]:
        """Get format specification for platform"""
        return PlatformFormatter.PLATFORM_SPECS.get(
            platform.lower(), 
            PlatformFormatter.PLATFORM_SPECS["default"]
        )
    
    @staticmethod
    def build_post_text(
        title: str,
        caption: str,
        hashtags: List[str],
        platform: str = "linkedin"
    ) -> str:
        """Build complete post text with platform-specific formatting"""
        
        spec = PlatformFormatter.get_platform_spec(platform)
        
        # Start with title as hook
        post_parts = [f"🎯 {title}"]
        
        # Add caption
        if caption:
            post_parts.append(caption)
        
        # Add hashtags (limit by platform)
        hashtag_limit = spec["hashtag_max"]
        selected_hashtags = hashtags[:hashtag_limit]
        
        if selected_hashtags:
            hashtag_text = " ".join(selected_hashtags)
            post_parts.append(hashtag_text)
        
        # Add platform-specific CTA
        if spec["cta"]:
            post_parts.append(spec["cta"])
        
        # Join with platform line breaks
        full_post = spec["line_break"].join(post_parts)
        
        # Truncate if needed
        if len(full_post) > spec["max_caption_length"]:
            full_post = full_post[:spec["max_caption_length"] - 3] + "..."
        
        return full_post
    
    @staticmethod
    def generate_caption_variations(
        sections: List[Dict[str, str]],
        platform: str = "linkedin"
    ) -> List[CaptionVariation]:
        """Generate 3 caption variations for the platform"""
        
        variations = []
        
        if not sections:
            return variations
        
        # Extract key points from sections
        main_section = sections[0] if sections else {}
        main_content = main_section.get("content", "")[:150]
        
        # Variation 1: Professional/Educational
        variation1 = CaptionVariation(
            text=f"Deep dive into this concept: {main_content}...\n\n"
                 "Understanding the fundamentals is key to mastering this domain. "
                 "Share your insights! 💭",
            style="professional",
            length=1
        )
        variations.append(variation1)
        
        # Variation 2: Casual/Engaging
        variation2 = CaptionVariation(
            text=f"Just learned something cool: {main_content}...\n\n"
                 "This changes everything I thought I knew! "
                 "Have you experienced this? 🤔",
            style="casual",
            length=2
        )
        variations.append(variation2)
        
        # Variation 3: Technical/In-depth
        variation3 = CaptionVariation(
            text=f"Technical breakdown: {main_content}...\n\n"
                 "The architecture behind this is fascinating. "
                 "Full analysis in my latest post! 🔧",
            style="technical",
            length=3
        )
        variations.append(variation3)
        
        return variations


class ExportEngine:
    """Main export service combining content and images"""
    
    def __init__(self):
        self.formatter = PlatformFormatter()
        logger.info("✅ ExportEngine initialized (Step 5: Export + Post-ready Output)")
    
    async def export(self, content_data: Dict[str, Any], image_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export combined content and image into post-ready format
        
        Args:
            content_data: Output from Step 3 (ContentGenerator)
            image_data: Output from Step 4 (ImageGenerator)
        
        Returns:
            Export response with platform-specific formatting
        """
        
        logger.info(f"📤 Exporting content + image...")
        
        try:
            # Extract data
            export_id = content_data.get("id", "unknown")
            title = content_data.get("title", "Untitled")
            caption = content_data.get("caption", "")
            hashtags = content_data.get("hashtags", [])
            sections = content_data.get("sections", [])
            platform = content_data.get("platform", "linkedin")
            category = content_data.get("category", "general")
            style_hint = content_data.get("style_hint", "")
            
            image_url = image_data.get("image_url", "")
            image_provider = image_data.get("provider", "unknown")
            
            # Handle missing caption - regenerate from sections
            if not caption and sections:
                logger.info("⚠️  Caption missing, regenerating from sections...")
                caption = self._regenerate_caption(sections, platform)
            
            # Build full post text
            full_post_text = self.formatter.build_post_text(
                title=title,
                caption=caption,
                hashtags=hashtags,
                platform=platform
            )
            
            # Generate caption variations
            caption_variations = self.formatter.generate_caption_variations(
                sections=sections,
                platform=platform
            )
            
            # Build export response
            export_response = {
                "id": export_id,
                "title": title,
                "image_url": image_url,
                "caption": caption,
                "hashtags": hashtags,
                "full_post_text": full_post_text,
                "platform": platform,
                "category": category,
                "style_hint": style_hint,
                "image_provider": image_provider,
                "caption_variations": [var.to_dict() for var in caption_variations],
                "download_ready": bool(image_url),
                "post_metadata": {
                    "character_count": len(full_post_text),
                    "hashtag_count": len(hashtags),
                    "section_count": len(sections),
                    "has_image": bool(image_url)
                }
            }
            
            logger.info(f"✅ Export complete: {len(full_post_text)} chars, {len(hashtags)} hashtags")
            
            return export_response
        
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            raise
    
    def _regenerate_caption(self, sections: List[Dict[str, str]], platform: str) -> str:
        """Regenerate caption from sections if missing"""
        
        if not sections:
            return "Check out this content!"
        
        # Use first 2 sections
        section_texts = []
        for section in sections[:2]:
            heading = section.get("heading", "")
            content = section.get("content", "")[:100]
            if heading and content:
                section_texts.append(f"{heading}: {content}")
        
        caption = " → ".join(section_texts) if section_texts else "Great content!"
        
        if platform.lower() == "instagram":
            return f"✨ {caption}\n\nFull breakdown 👇"
        elif platform.lower() == "linkedin":
            return f"Insights on: {caption}"
        else:
            return caption
    
    def get_platform_recommendations(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get platform-specific recommendations"""
        
        platform = content_data.get("platform", "linkedin")
        category = content_data.get("category", "general")
        
        recommendations = {
            "optimal_platform": platform,
            "best_posting_times": self._get_posting_times(platform),
            "suggested_length": self._get_suggested_length(platform),
            "content_type": self._get_content_type(category),
            "engagement_tips": self._get_engagement_tips(platform)
        }
        
        return recommendations
    
    @staticmethod
    def _get_posting_times(platform: str) -> Dict[str, str]:
        """Get optimal posting times for platform"""
        times = {
            "linkedin": {"weekday": "Tuesday-Thursday", "time": "8:00 AM - 10:00 AM"},
            "instagram": {"weekday": "Monday, Wednesday, Friday", "time": "6:00 AM - 9:00 AM"},
            "twitter": {"weekday": "Any day", "time": "9:00 AM - 3:00 PM"},
        }
        return times.get(platform.lower(), {"weekday": "Any", "time": "9:00 AM - 5:00 PM"})
    
    @staticmethod
    def _get_suggested_length(platform: str) -> Dict[str, int]:
        """Get suggested post length for platform"""
        lengths = {
            "linkedin": {"min": 150, "max": 1300, "optimal": 650},
            "instagram": {"min": 50, "max": 2200, "optimal": 150},
            "twitter": {"min": 50, "max": 280, "optimal": 200},
        }
        return lengths.get(platform.lower(), {"min": 50, "max": 500, "optimal": 200})
    
    @staticmethod
    def _get_content_type(category: str) -> str:
        """Get content type based on category"""
        types = {
            "AI": "Educational + Technical",
            "Backend": "Technical + Best Practices",
            "Frontend": "Tutorial + Code Examples",
            "DevOps": "Configuration + Best Practices",
            "Career": "Motivational + Advice",
        }
        return types.get(category, "Educational")
    
    @staticmethod
    def _get_engagement_tips(platform: str) -> List[str]:
        """Get engagement tips for platform"""
        tips = {
            "linkedin": [
                "Start with a hook or question",
                "Use 3-5 bullet points or sections",
                "Include a call-to-action",
                "Mention relevant people or companies",
                "Respond to comments within first hour"
            ],
            "instagram": [
                "Use 20-30 relevant hashtags",
                "Ask a question in caption",
                "Use story stickers for engagement",
                "Reply to comments with emojis",
                "Post Stories 2-3x per week"
            ],
            "twitter": [
                "Keep it concise and punchy",
                "Use relevant hashtags (2-3)",
                "Thread related tweets together",
                "Engage with replies quickly",
                "Share interesting images/videos"
            ],
        }
        return tips.get(platform.lower(), [
            "Be authentic",
            "Engage with community",
            "Post consistently",
            "Use visuals",
            "Respond to feedback"
        ])
