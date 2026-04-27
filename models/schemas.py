"""Pydantic schemas for request/response validation"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Trend Schemas
# ============================================================================


class TrendBase(BaseModel):
    """Base trend model"""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    value: float = Field(..., gt=0)


class TrendResponse(TrendBase):
    """Trend response model"""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrendTopicResponse(BaseModel):
    """Trending topic response model"""

    title: str
    description: str
    category: str
    source: str
    score: float
    url: Optional[str] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Template Schemas
# ============================================================================


class TemplateBase(BaseModel):
    """Base template model"""

    name: str = Field(..., min_length=1, max_length=255)
    content: str
    template_type: str = Field(..., min_length=1, max_length=100)


class TemplateResponse(TemplateBase):
    """Template response model"""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateSection(BaseModel):
    """Template section model"""

    name: str
    type: str
    position: int
    properties: Dict[str, Any] = {}


class ScrapedTemplateResponse(BaseModel):
    """Scraped template response model"""

    title: str
    source_url: str
    layout_type: str = Field(..., description="grid, flow, list, masonry, etc.")
    num_sections: int
    sections: List[TemplateSection]
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class TemplateAnalysisResponse(BaseModel):
    """Template layout analysis response"""

    title: str
    layout_type: str
    total_sections: int
    section_types: Dict[str, int]
    complexity: str = Field(..., description="simple, moderate, complex")
    density: float


# ============================================================================
# Decision Engine Schemas
# ============================================================================


class DecideRequest(BaseModel):
    """Request for decision engine endpoint"""

    topic: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Optional user topic"
    )
    platform: str = Field(
        "linkedin",
        pattern="^(linkedin|instagram)$",
        description="Target platform: linkedin or instagram",
    )
    num_templates: int = Field(
        3, ge=1, le=10, description="Number of templates to select"
    )
    selected_template: Optional[Dict[str, Any]] = Field(
        None, description="Pre-selected template from user (template-first flow)"
    )
    selected_post: Optional[Dict[str, Any]] = Field(
        None, description="Real post selected by user (STEP 6: post-first flow)"
    )


class ContentPlanSchema(BaseModel):
    """Content plan structure"""

    title: str = Field(..., description="Main content title")
    sections: List[str] = Field(..., description="List of content sections")
    key_points: List[str] = Field(..., description="Key points to cover")
    call_to_action: str = Field(..., description="CTA message")


class TemplateSelectionSchema(BaseModel):
    """Selected template"""

    id: str
    name: str
    layout: str
    sections: int
    style: str


class DecideResponse(BaseModel):
    """Response from decision engine"""

    id: str = Field(..., description="Unique decision ID (UUID)")
    final_topic: str = Field(..., description="Selected topic")
    category: str = Field(..., description="Topic category (auto-detected)")
    source: str = Field(..., description="Data source")
    score: float = Field(..., ge=0, le=100, description="Topic relevance score")
    difficulty: str = Field(..., description="Difficulty level: beginner | intermediate | advanced")
    style_hint: str = Field(..., description="Visual style hint for image generation")
    selected_templates: List[TemplateSelectionSchema] = Field(
        ..., description="Selected templates"
    )
    content_plan: ContentPlanSchema = Field(..., description="Content structure")
    platform: str = Field(..., description="Target platform")
    reasoning: str = Field(..., description="Decision reasoning")


# ============================================================================
# Content Generation Schemas (Step 3)
# ============================================================================


class GenerateContentRequest(BaseModel):
    """Request for content generation endpoint"""

    decision_data: Dict[str, Any] = Field(
        ..., description="Full response from /decide endpoint"
    )


class GeneratedSectionSchema(BaseModel):
    """Generated content for a section"""

    heading: str = Field(..., description="Section heading")
    content: str = Field(..., description="Generated section content")


class GenerateContentResponse(BaseModel):
    """Response from content generation endpoint"""

    id: str = Field(..., description="Content generation ID (from decision)")
    title: str = Field(..., description="Generated/enhanced title")
    sections: List[GeneratedSectionSchema] = Field(
        ..., description="Generated content for each section"
    )
    caption: str = Field(..., description="Social media caption with Hook → Explanation → CTA")
    hashtags: List[str] = Field(..., min_length=5, max_length=8, description="5-8 relevant hashtags")
    platform: str = Field(..., description="Target platform")
    category: str = Field(..., description="Content category")
    style_hint: str = Field(..., description="Visual style hint for image generation")
    ai_provider: str = Field(
        ..., description="Which AI provider was used: groq or gemini"
    )


# ============================================================================
# Image Generation Schemas (Step 4)
# ============================================================================


class GenerateImageRequest(BaseModel):
    """Request for image generation endpoint"""

    content_data: Dict[str, Any] = Field(
        ..., description="Full response from /generate-content endpoint"
    )


class GenerateImageResponse(BaseModel):
    """Response from image generation endpoint"""

    id: str = Field(..., description="Image generation ID (from content)")
    image_url: str = Field(..., description="URL of generated infographic image")
    prompt_used: str = Field(..., description="Image generation prompt used")
    platform: str = Field(..., description="Target platform (linkedin or instagram)")
    provider: str = Field(
        ..., description="Which image provider was used: cloudflare:* or cloudflare_unavailable"
    )


# ============================================================================
# Export Schemas (Step 5)
# ============================================================================


class CaptionVariationSchema(BaseModel):
    """Caption variation for different styles"""

    text: str = Field(..., description="Caption text")
    style: str = Field(..., description="Style: professional, casual, technical, catchy")
    length: int = Field(..., description="Variation number (1, 2, 3)")
    char_count: int = Field(..., description="Character count of caption")


class PostMetadataSchema(BaseModel):
    """Metadata about the post"""

    character_count: int = Field(..., description="Total characters in post")
    hashtag_count: int = Field(..., description="Number of hashtags")
    section_count: int = Field(..., description="Number of content sections")
    has_image: bool = Field(..., description="Whether image is available")


class ExportRequest(BaseModel):
    """Request for export endpoint (Step 5)"""

    content_data: Dict[str, Any] = Field(
        ..., description="Full response from /generate-content endpoint"
    )
    image_data: Dict[str, Any] = Field(
        ..., description="Full response from /generate-image endpoint"
    )


class ExportResponse(BaseModel):
    """Response from export endpoint (Step 5)"""

    id: str = Field(..., description="Export ID (from content)")
    title: str = Field(..., description="Content title")
    image_url: str = Field(..., description="Image URL (may be empty)")
    caption: str = Field(..., description="Social media caption")
    hashtags: List[str] = Field(..., description="List of hashtags")
    full_post_text: str = Field(
        ..., description="Complete post text ready for posting"
    )
    platform: str = Field(..., description="Target platform (linkedin or instagram)")
    category: str = Field(..., description="Content category")
    style_hint: str = Field(..., description="Visual style hint")
    image_provider: str = Field(..., description="Image provider used")
    caption_variations: List[CaptionVariationSchema] = Field(
        ..., description="3 caption variations with different styles"
    )
    post_metadata: PostMetadataSchema = Field(
        ..., description="Post metadata and stats"
    )
    download_ready: bool = Field(
        ..., description="Whether content is ready for download/posting"
    )


class PlatformRecommendationSchema(BaseModel):
    """Platform-specific recommendations"""

    optimal_platform: str = Field(..., description="Recommended platform")
    best_posting_times: Dict[str, str] = Field(
        ..., description="Optimal posting times"
    )
    suggested_length: Dict[str, int] = Field(
        ..., description="Suggested post length (min, max, optimal)"
    )
    content_type: str = Field(..., description="Type of content")
    engagement_tips: List[str] = Field(
        ..., description="Platform-specific engagement tips"
    )
