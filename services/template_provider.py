"""Template Provider Service - Infographic Template Storage
Templates matched to REAL LinkedIn/social infographic styles:
  t1: Mind Map / Ecosystem
  t2: Step-by-Step Guide
  t3: Comparison Grid
  t4: Cheat Sheet
  t5: Architecture Diagram
  t6: Roadmap / Timeline
  t7: Listicle / Top N
  t8: Visual Explainer
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TemplateMetadata:
    """Represents template metadata"""

    id: str
    name: str
    layout: str        # "flow", "grid", "list", "steps", "comparison"
    sections: int      # number of sections
    style: str         # "dark", "minimal", "colorful", "professional"
    description: str = ""
    preview_url: str = ""
    visual_type: str = ""  # matches post visual_type

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "layout": self.layout,
            "sections": self.sections,
            "style": self.style,
            "description": self.description,
            "preview_url": self.preview_url,
            "visual_type": self.visual_type,
        }


class TemplateProvider:
    """Service for providing infographic template metadata"""

    TEMPLATES: List[TemplateMetadata] = [
        TemplateMetadata(
            id="t1",
            name="Mind Map / Ecosystem",
            layout="flow",
            sections=6,
            style="colorful",
            description="Central concept with branching categories — like 'Google AI Ecosystem 2026'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t1",
            visual_type="mind_map",
        ),
        TemplateMetadata(
            id="t2",
            name="Step-by-Step Guide",
            layout="flow",
            sections=6,
            style="minimal",
            description="Numbered steps with icons — like 'Deploy to AWS in 6 Steps'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t2",
            visual_type="steps",
        ),
        TemplateMetadata(
            id="t3",
            name="Comparison Grid",
            layout="grid",
            sections=4,
            style="professional",
            description="Side-by-side comparison — like 'React vs Vue vs Angular'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t3",
            visual_type="comparison",
        ),
        TemplateMetadata(
            id="t4",
            name="Cheat Sheet",
            layout="grid",
            sections=8,
            style="dark",
            description="Dense reference card — like 'Docker Commands Cheat Sheet'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t4",
            visual_type="cheat_sheet",
        ),
        TemplateMetadata(
            id="t5",
            name="Architecture Diagram",
            layout="flow",
            sections=5,
            style="minimal",
            description="System components with arrows — like 'Netflix System Design'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t5",
            visual_type="architecture",
        ),
        TemplateMetadata(
            id="t6",
            name="Roadmap / Timeline",
            layout="flow",
            sections=7,
            style="colorful",
            description="Sequential milestones — like 'Frontend Developer Roadmap 2026'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t6",
            visual_type="roadmap",
        ),
        TemplateMetadata(
            id="t7",
            name="Listicle / Top N",
            layout="list",
            sections=7,
            style="professional",
            description="Numbered items with descriptions — like '10 Python Libraries You Need'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t7",
            visual_type="listicle",
        ),
        TemplateMetadata(
            id="t8",
            name="Visual Explainer",
            layout="flow",
            sections=5,
            style="colorful",
            description="Concept breakdown with visuals — like 'How HTTPS Works'",
            preview_url="http://127.0.0.1:8000/api/v1/preview/t8",
            visual_type="explainer",
        ),
    ]

    def __init__(self):
        self.logger = logger

    async def get_all_templates(self) -> List[TemplateMetadata]:
        """Get all available templates"""
        self.logger.info("Fetching all %d templates from memory", len(self.TEMPLATES))
        return self.TEMPLATES

    async def get_templates_by_layout(self, layout: str) -> List[TemplateMetadata]:
        """Get templates filtered by layout type"""
        filtered = [t for t in self.TEMPLATES if t.layout == layout]
        self.logger.info("Found %d templates with layout: %s", len(filtered), layout)
        return filtered

    async def get_templates_by_style(self, style: str) -> List[TemplateMetadata]:
        """Get templates filtered by style"""
        filtered = [t for t in self.TEMPLATES if t.style == style]
        self.logger.info("Found %d templates with style: %s", len(filtered), style)
        return filtered

    async def get_template_by_id(self, template_id: str) -> Optional[TemplateMetadata]:
        """Get specific template by ID"""
        template = next((t for t in self.TEMPLATES if t.id == template_id), None)
        if template:
            self.logger.info("Found template: %s", template_id)
        else:
            self.logger.warning("Template not found: %s", template_id)
        return template

    async def get_template_by_visual_type(self, visual_type: str) -> Optional[TemplateMetadata]:
        """Get template matching a visual type (from post detection)"""
        template = next(
            (t for t in self.TEMPLATES if t.visual_type == visual_type), None
        )
        if not template:
            # Fallback to first template
            template = self.TEMPLATES[0]
        return template
