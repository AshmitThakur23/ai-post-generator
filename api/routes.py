"""API Routes — Full Pipeline Endpoints (Zones A-G)"""

import logging
import io
import os
import shutil
import uuid
import zipfile
import time
import json
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse

from services.trend_engine import TrendEngine, TrendTopic
from services.template_provider import TemplateProvider, TemplateMetadata
from services.post_fetcher import PostFetcher
from services.template_detector import TemplateDetector
from services.decision_engine import DecisionEngine
from services.content_generator import ContentGenerator
from services.image_generator import ImageGenerator
from services.export_engine import ExportEngine
from services.html_builder import HTMLBuilder, apply_tweaks, PLATFORM_SIZES
from services.template_scraper import TemplateScraper
from services.frame_recorder import FrameRecorder
from services.ffmpeg_exporter import FFmpegExporter
from services.format_router import FormatRouter
from models.schemas import DecideRequest, DecideResponse, GenerateContentRequest, GenerateContentResponse, GenerateImageRequest, GenerateImageResponse, ExportRequest, ExportResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["api"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
GENERATED_IMAGES_DIR = os.path.join(BASE_DIR, "generated_images")
FRAMES_DIR = os.path.join(TEMP_DIR, "frames")


# ============================================================================
# Service Instances (set by main.py)
trend_engine = None
template_provider = None
post_fetcher = None
template_detector = None
decision_engine = None
content_generator = None
image_generator = None
export_engine = None
html_builder = None
template_scraper = None
frame_recorder = None
ffmpeg_exporter = None
format_router = None


def _normalize_public_url(raw_url: str, source_name: str = "") -> str:
    """Normalize URL values from mixed source payloads into clickable absolute links."""
    value = str(raw_url or "").strip()
    if not value:
        return ""

    source_key = str(source_name or "").lower()

    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("www."):
        return f"https://{value}"

    if value.startswith("/"):
        if "reddit" in source_key:
            return f"https://reddit.com{value}"
        return ""

    if "reddit" in source_key and value.startswith("r/"):
        return f"https://reddit.com/{value}"

    return ""


def _extract_template_source_url(post: dict, source_name: str) -> str:
    """Pick the best source URL for template cards across all source schemas."""
    candidates = [
        post.get("url", ""),
        post.get("post_url", ""),
        post.get("source_url", ""),
        post.get("sourceUrl", ""),
        post.get("link", ""),
        post.get("permalink", ""),
    ]

    for candidate in candidates:
        normalized = _normalize_public_url(candidate, source_name)
        if normalized:
            return normalized

    if source_name == "hackernews":
        raw_id = str(post.get("id", "")).strip()
        story_id = ""
        if raw_id.startswith("hn_"):
            story_id = raw_id.split("_", 1)[1]
        elif raw_id.isdigit():
            story_id = raw_id
        if story_id:
            return f"https://news.ycombinator.com/item?id={story_id}"

    return ""


def set_services(engine=None, provider=None, fetcher=None, detector=None,
                 decision=None, generator=None, image_gen=None, export_gen=None,
                 builder=None, scraper=None, recorder=None, ffmpeg=None, router=None, **kw):
    global trend_engine, template_provider, post_fetcher, template_detector
    global decision_engine, content_generator, image_generator, export_engine
    global html_builder, template_scraper, frame_recorder, ffmpeg_exporter, format_router
    trend_engine = engine
    template_provider = provider
    post_fetcher = fetcher
    template_detector = detector
    decision_engine = decision
    content_generator = generator
    image_generator = image_gen
    export_engine = export_gen
    html_builder = builder
    template_scraper = scraper
    frame_recorder = recorder
    ffmpeg_exporter = ffmpeg
    format_router = router


# ============================================================================
# TRENDS ENDPOINT
# ========================================================================== 

@router.get("/trends", response_model=dict)
async def get_trends(limit: int = Query(10, ge=1, le=50)):
    """
    Get REAL trending technical topics from HackerNews API
    
    Args:
        limit: Number of topics to return (1-50)
    
    Returns:
        {
            "status": "success",
            "count": int,
            "source": "hackernews",
            "topics": [
                {
                    "title": str,
                    "description": str,
                    "category": str,
                    "source": str,
                    "score": float,
                    "url": str,
                    "timestamp": str
                }
            ]
        }
    """
    if not trend_engine:
        raise HTTPException(status_code=500, detail="Trend engine not initialized")
    
    logger.info("📊 GET /trends - Fetching %d trending topics", limit)
    
    try:
        topics = await trend_engine.get_trending_topics(limit=limit)
        
        return {
            "status": "success",
            "count": len(topics),
            "source": "hackernews",
            "topics": [topic.to_dict() for topic in topics],
        }
    except Exception as e:
        logger.error("Error fetching trends: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEMPLATES ENDPOINT
# ========================================================================== 

@router.get("/templates", response_model=dict)
async def get_templates(
    layout: str = Query(None, description="Filter by layout: flow, grid, list"),
    style: str = Query(None, description="Filter by style: dark, minimal, colorful"),
):
    """
    Get template metadata (in-memory storage, no database)
    
    Query params:
        layout: Optional - "flow", "grid", or "list"
        style: Optional - "dark", "minimal", or "colorful"
    
    Returns:
        {
            "status": "success",
            "count": int,
            "templates": [
                {
                    "id": str,
                    "name": str,
                    "layout": str,
                    "sections": int,
                    "style": str
                }
            ]
        }
    """
    if not template_provider:
        raise HTTPException(status_code=500, detail="Template provider not initialized")
    
    logger.info("📋 GET /templates - layout: %s, style: %s", layout, style)
    
    try:
        # Start with all templates
        templates = await template_provider.get_all_templates()
        
        # Apply filters if provided
        if layout:
            templates = [t for t in templates if t.layout == layout]
        if style:
            templates = [t for t in templates if t.style == style]
        
        return {
            "status": "success",
            "count": len(templates),
            "templates": [t.to_dict() for t in templates],
        }
    except Exception as e:
        logger.error("Error fetching templates: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POSTS ENDPOINT - Get REAL trending posts
# ========================================================================== 

@router.get("/posts", response_model=dict)
async def get_posts(limit: int = Query(10, ge=1, le=50)):
    """
    Get REAL trending posts from Dev.to, Hashnode, GitHub
    
    This is STEP 6: User selects real posts they like
    System analyzes them to understand template style
    Then generates similar content
    
    Args:
        limit: Number of posts (1-50)
    
    Returns:
        {
            "status": "success",
            "count": int,
            "posts": [
                {
                    "id": str,
                    "title": str,
                    "url": str,
                    "cover_image": str,
                    "description": str,
                    "source": "Dev.to | Hashnode | GitHub",
                    "author": str,
                    "engagement": int,
                    "likes": int,
                    "comments": int,
                    "published": str,
                    "tags": [str]
                }
            ]
        }
        
    """
    logger.info("📲 GET /posts - Fetching %d trending posts", limit)
    
    if not post_fetcher:
        raise HTTPException(status_code=500, detail="Post fetcher not initialized")
    
    try:
        posts = await post_fetcher.get_trending_posts(limit=limit)
        
        return {
            "status": "success",
            "count": len(posts),
            "posts": posts,
        }
    except Exception as e:
        logger.error("Error fetching posts: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OLD ENDPOINT - Keep for backwards compatibility
# ========================================================================== 

@router.get("/real-posts", response_model=dict)
async def get_real_posts(limit: int = Query(10, ge=1, le=50)):
    """Redirect to /posts endpoint (deprecated)"""
    return await get_posts(limit=limit)


# ============================================================================
# TEMPLATE PREVIEW ENDPOINT - Shows HTML preview in browser
# ========================================================================== 

@router.get("/preview/{template_id}", response_class=HTMLResponse)
async def preview_template(template_id: str):
    """
    Get HTML preview of a template in the browser
    
    Args:
        template_id: Template ID (t1-t8)
    
    Returns:
        HTML page with template preview
    """
    if not template_provider:
        raise HTTPException(status_code=500, detail="Template provider not initialized")
    
    logger.info("📺 GET /preview/%s - Generating HTML preview", template_id)
    
    try:
        template = await template_provider.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        # Generate HTML preview based on template style
        html = _generate_template_preview_html(template)
        return html
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating preview: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _generate_template_preview_html(template: TemplateMetadata) -> str:
    """Generate HTML preview for a template"""
    
    # Color schemes based on style
    styles = {
        "minimal": {"bg": "#f8f9fa", "text": "#333", "accent": "#0066cc", "card": "#ffffff"},
        "dark": {"bg": "#1a1a1a", "text": "#ffffff", "accent": "#ff6b6b", "card": "#2d2d2d"},
        "colorful": {"bg": "#fff0f5", "text": "#333", "accent": "#ff1493", "card": "#ffe4e1"},
    }
    
    style_config = styles.get(template.style, styles["minimal"])
    
    # Generate section cards
    section_cards = ""
    colors = ["#e3f2fd", "#f3e5f5", "#e8f5e9", "#fff3e0", "#fce4ec"]
    
    for i in range(min(template.sections, 5)):  # Show max 5 sections
        color = colors[i % len(colors)]
        section_cards += f"""
        <div class="section-card" style="background-color: {color};">
            <h3>Section {i+1}: {template.name}</h3>
            <p>Lorem ipsum dolor sit amet. This is a preview of section {i+1}.</p>
        </div>
        """
    
    if template.sections > 5:
        section_cards += f'<div class="section-card" style="background-color: #e0e0e0; text-align: center;"><p>+ {template.sections - 5} more sections...</p></div>'
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{template.name} - Preview</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                background: linear-gradient(135deg, {style_config['bg']} 0%, #ffffff 100%);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                min-height: 100vh;
                padding: 40px 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 50px;
                color: {style_config['text']};
            }}
            
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
                color: {style_config['accent']};
            }}
            
            .template-info {{
                display: flex;
                gap: 20px;
                justify-content: center;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}
            
            .info-badge {{
                background: {style_config['card']};
                padding: 10px 20px;
                border-radius: 20px;
                font-weight: bold;
                color: {style_config['text']};
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            
            .layout-indicator {{
                font-size: 0.9em;
                opacity: 0.7;
            }}
            
            .sections-container {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            
            .section-card {{
                background: {style_config['card']};
                border: 2px solid {style_config['accent']};
                border-radius: 8px;
                padding: 25px;
                color: {style_config['text']};
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }}
            
            .section-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.2);
            }}
            
            .section-card h3 {{
                color: {style_config['accent']};
                margin-bottom: 10px;
                font-size: 1.2em;
            }}
            
            .section-card p {{
                font-size: 0.95em;
                line-height: 1.6;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 50px;
                padding-top: 20px;
                border-top: 2px solid {style_config['accent']};
                color: {style_config['text']};
                opacity: 0.7;
            }}
            
            .back-button {{
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background: {style_config['accent']};
                color: white;
                text-decoration: none;
                border-radius: 5px;
                transition: opacity 0.3s ease;
            }}
            
            .back-button:hover {{
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✨ {template.name}</h1>
                <p style="font-size: 1.1em; margin-bottom: 20px;">{template.description}</p>
            </div>
            
            <div class="template-info">
                <div class="info-badge">📐 Layout: <span style="font-weight: bold; text-transform: capitalize;">{template.layout}</span></div>
                <div class="info-badge">📄 Sections: <span style="font-weight: bold;">{template.sections}</span></div>
                <div class="info-badge">🎨 Style: <span style="font-weight: bold; text-transform: capitalize;">{template.style}</span></div>
            </div>
            
            <div class="sections-container">
                {section_cards}
            </div>
            
            <div class="footer">
                <p>This is a preview of the {template.name} template</p>
                <p>Select this template in the CLI to generate your post!</p>
                <a href="javascript:history.back()" class="back-button">← Back to CLI</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


# ============================================================================
# REFRESH TRENDS ENDPOINT
# ========================================================================== 

@router.post("/refresh-trends", response_model=dict)
async def refresh_trends():
    """
    Manually refresh trending topics from HackerNews API
    
    Returns:
        {
            "status": "success",
            "refreshed": bool,
            "count": int,
            "message": str
        }
    """
    if not trend_engine:
        raise HTTPException(status_code=500, detail="Trend engine not initialized")
    
    logger.info("🔄 POST /refresh-trends - Manually refreshing trends")
    
    try:
        topics = await trend_engine.refresh_trends()
        
        return {
            "status": "success",
            "refreshed": True,
            "count": len(topics),
            "message": f"✅ Refreshed {len(topics)} trending topics from HackerNews",
        }
    except Exception as e:
        logger.error("Error refreshing trends: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DECISION ENGINE ENDPOINT - Step 2
# ========================================================================== 

@router.post("/decide", response_model=DecideResponse)
async def decide(request: DecideRequest):
    """
    Decision Engine: Select best topic + templates + content plan
    
    NEW STEP 6 FLOW:
    If selected_post provided:
    1. Run template detector
    2. Analyze post to determine template style
    3. Use detected template
    4. Extract topic from post
    
    Otherwise: Use existing flow
    
    Input:
        - selected_post: Real post selected by user (NEW - STEP 6)
        - topic: Optional topic string (if not provided, selects from trends)
        - platform: "linkedin" or "instagram"
        - num_templates: Number of templates to select (1-10)
    
    Returns:
        {
            "final_topic": str,
            "category": str,
            "source": str,
            "score": float,
            "selected_templates": [...],
            "content_plan": {...},
            "platform": str,
            "reasoning": str
        }
    """
    if not decision_engine:
        raise HTTPException(status_code=500, detail="Decision engine not initialized")
    
    logger.info("🤖 POST /decide - topic: %s, platform: %s", request.topic, request.platform)
    
    try:
        # Use local variables instead of mutating request
        topic = request.topic
        selected_template = request.selected_template

        # STEP 6: If real post selected, detect template first
        if request.selected_post:
            logger.info("📊 STEP 6: Real post detected - running template detector...")
            
            if not template_detector:
                raise HTTPException(status_code=500, detail="Template detector not initialized")
            
            # Detect template from post
            detection = await template_detector.detect_template(request.selected_post)
            logger.info(f"🎯 Detected template: {detection['template_type']} (confidence: {detection['confidence']})")
            
            # Get the template object
            detected_template = await template_provider.get_template_by_id(detection["template_id"])
            if detected_template:
                selected_template = detected_template.to_dict()
                logger.info(f"✅ Using template: {detected_template.name}")
            
            # Extract topic from post title if not provided
            if not topic:
                topic = request.selected_post.get("title", "Interesting Topic")[:100]
                logger.info(f"📝 Extracted topic from post: {topic}")
        
        # Call decision engine with local variables
        decision = await decision_engine.decide(
            topic=topic,
            platform=request.platform,
            num_templates=request.num_templates,
            selected_template=selected_template,
        )
        
        return decision.to_dict()
    except Exception as e:
        logger.error("Error in decision engine: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONTENT GENERATION ENDPOINT - Step 3
# ========================================================================== 

@router.post("/generate-content", response_model=GenerateContentResponse)
async def generate_content(request: GenerateContentRequest):
    """
    AI Content Generation: Generate full content for all sections
    
    Input:
        - decision_data: Full response from /decide endpoint
    
    Returns:
        {
            "id": str,
            "title": str,
            "sections": [
                {"heading": str, "content": str}
            ],
            "caption": str,
            "hashtags": [str, ...],
            "platform": str,
            "category": str,
            "ai_provider": "groq" or "gemini"
        }
    """
    if not content_generator:
        raise HTTPException(status_code=500, detail="Content generator not initialized")
    
    logger.info("📝 POST /generate-content - Generating content")
    
    try:
        result = await content_generator.generate(request.decision_data)
        
        return result.to_dict()
    except Exception as e:
        logger.error("Error in content generation: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# IMAGE GENERATION ENDPOINT - Step 4
# ========================================================================== 

@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest):
    """
    Image Generation: Generate infographic from content
    
    Input:
        - content_data: Full response from /generate-content endpoint
    
    Returns:
        {
            "id": str,
            "image_url": str,
            "prompt_used": str,
            "platform": str,
            "provider": "cloudflare:*" or "cloudflare_unavailable"
        }
    """
    if not image_generator:
        raise HTTPException(status_code=500, detail="Image generator not initialized")
    
    logger.info("🖼️ POST /generate-image - Generating infographic")
    
    try:
        result = await image_generator.generate(request.content_data)
        
        return result.to_dict()
    except Exception as e:
        logger.error("Error in image generation: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXPORT ENDPOINT - Step 5
# ========================================================================== 

@router.post("/export", response_model=ExportResponse)
async def export_content(request: ExportRequest):
    """
    Export: Combine content + image into post-ready format
    
    Input:
        - content_data: Full response from /generate-content endpoint
        - image_data: Full response from /generate-image endpoint
    
    Returns:
        {
            "id": str,
            "title": str,
            "image_url": str,
            "caption": str,
            "hashtags": [str, ...],
            "full_post_text": str,
            "platform": str,
            "category": str,
            "style_hint": str,
            "image_provider": str,
            "caption_variations": [{
                "text": str,
                "style": str,
                "length": int,
                "char_count": int
            }],
            "post_metadata": {
                "character_count": int,
                "hashtag_count": int,
                "section_count": int,
                "has_image": bool
            },
            "download_ready": bool
        }
    """
    if not export_engine:
        raise HTTPException(status_code=500, detail="Export engine not initialized")
    
    logger.info("📤 POST /export - Exporting content + image")
    
    try:
        result = await export_engine.export(request.content_data, request.image_data)
        
        return result
    except Exception as e:
        logger.error("Error in export: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/recommendations", response_model=dict)
async def get_export_recommendations(
    platform: str = Query("linkedin", description="Platform: linkedin or instagram")
):
    """
    Get platform-specific recommendations for posting
    
    Args:
        platform: Target platform (linkedin or instagram)
    
    Returns:
        {
            "optimal_platform": str,
            "best_posting_times": {...},
            "suggested_length": {...},
            "content_type": str,
            "engagement_tips": [...]
        }
    """
    if not export_engine:
        raise HTTPException(status_code=500, detail="Export engine not initialized")
    
    logger.info("📋 GET /export/recommendations - Platform: %s", platform)
    
    try:
        recommendations = export_engine.get_platform_recommendations({
            "platform": platform,
            "category": "general"
        })
        
        return {
            "status": "success",
            "platform": platform,
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error("Error getting recommendations: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ZONE D/E/F/G — FULL PIPELINE (HTML builder + frames + FFmpeg + format)
# ============================================================================

@router.post("/pipeline/full")
async def run_full_pipeline(request: dict):
    """Run pipeline with 2 output modes:
    
    - 'image': Groq content + AI image → direct PNG download
    - 'animated': Groq content + Gemini HTML/CSS → Playwright frames → FFmpeg GIF → direct GIF download
    
    Selected templates influence the style of the output.
    """
    topic = request.get("topic", "")
    platform = request.get("platform", "linkedin")

    requested_output_format = str(request.get("output_format", "image")).lower()
    if requested_output_format in {"image", "png", "static"}:
        output_format = "image"
    elif requested_output_format in {"animated", "gif", "live"}:
        output_format = "animated"
    else:
        output_format = "image"

    tweaks = request.get("tweaks", {})
    selected_templates = request.get("selected_templates", [])
    include_ai_image_raw = request.get("include_ai_image", None)

    def _coerce_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    include_ai_image = _coerce_bool(include_ai_image_raw, default=(output_format == "image"))

    result = {
        "steps": [],
        "output_format": output_format,
        "requested_output_format": requested_output_format,
    }

    try:
        # ---- Zone B: Decision ----
        if decision_engine:
            dec_out = await decision_engine.decide(topic=topic or None, platform=platform, num_templates=1)
            dec = dec_out.to_dict() if hasattr(dec_out, 'to_dict') else dec_out
        else:
            dec = {
                "final_topic": topic, "category": "Tech", "platform": platform,
                "content_plan": {"sections": [], "key_points": []}, "selected_templates": []
            }

        # Use user-selected templates if provided
        if selected_templates:
            dec["selected_templates"] = selected_templates

        result["decision"] = dec
        result["steps"].append({"zone": "B", "step": "Decision Engine", "status": "done",
                                "detail": dec.get("final_topic", topic)})

        # ---- Zone C: Content + Image in PARALLEL ----
        import asyncio

        async def gen_content():
            if content_generator:
                out = await content_generator.generate(dec)
                return out.to_dict() if hasattr(out, 'to_dict') else out
            return {}

        async def gen_image():
            if image_generator:
                selected_template = {}
                if dec.get("selected_templates") and isinstance(dec.get("selected_templates"), list):
                    first_template = dec["selected_templates"][0] if dec["selected_templates"] else {}
                    if isinstance(first_template, dict):
                        selected_template = first_template

                img_input = {
                    "title": dec.get("final_topic", topic),
                    "category": dec.get("category", "Tech"),
                    "platform": platform,
                    "sections": dec.get("content_plan", {}).get("sections", []),
                    "key_points": dec.get("content_plan", {}).get("key_points", []),
                    "style_hint": dec.get("style_hint", "professional minimal design"),
                    "template_style": selected_template.get("style", ""),
                    "template_layout": selected_template.get("layout", ""),
                }
                out = await image_generator.generate(img_input)
                return out.to_dict() if hasattr(out, 'to_dict') else out
            return {}

        if include_ai_image:
            cont, img = await asyncio.gather(gen_content(), gen_image())
            image_step_status = "done"
            image_step_detail = (img.get("image_url", "none") or "none")[:60]
            image_step_name = f"AI Image ({img.get('provider','?')})"
        else:
            cont = await gen_content()
            img = {
                "id": dec.get("id", "no-image"),
                "image_url": "",
                "platform": platform,
                "provider": "skipped",
                "prompt_used": "skipped_in_animated_mode",
            }
            image_step_status = "done"
            image_step_detail = "Skipped in animated mode (API saver)"
            image_step_name = "AI Image (skipped)"

        result["content"] = cont
        result["image"] = img
        result["steps"].append({"zone": "C", "step": f"AI Content ({cont.get('ai_provider','?')})", "status": "done",
                                "detail": f"{len(cont.get('sections',[]))} sections"})
        result["steps"].append({"zone": "C", "step": image_step_name, "status": image_step_status,
                                "detail": image_step_detail})

        # ---- MODE: IMAGE → build high-quality composed static PNG ----
        if output_format == "image":
            composed_png_url = ""
            source_image_url = img.get("image_url", "")

            if html_builder and frame_recorder:
                try:
                    template = {}
                    if dec.get("selected_templates") and isinstance(dec["selected_templates"], list) and len(dec["selected_templates"]) > 0:
                        t = dec["selected_templates"][0] if isinstance(dec["selected_templates"][0], dict) else {}
                        template = {"style": t.get("style", "dark"), "layout": t.get("layout", "flow")}

                    html_path = await html_builder.build_animated_html(
                        content=cont,
                        image_path=source_image_url,
                        template=template,
                        tweaks=tweaks,
                        platform=platform,
                    )
                    result["html_path"] = html_path
                    result["html_generated_by"] = "gemini_ai" if html_builder.gemini_api_key else "local_template"
                    result["steps"].append({
                        "zone": "D",
                        "step": f"HTML Builder ({result['html_generated_by']})",
                        "status": "done",
                        "detail": "Static composition HTML generated",
                    })

                    size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["default"])
                    frame_count = await frame_recorder.record_frames(
                        html_path,
                        "simple",
                        size["width"],
                        size["height"],
                    )
                    if frame_count > 0:
                        first_frame = os.path.join(FRAMES_DIR, "frame_0001.png")
                        if os.path.exists(first_frame):
                            os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
                            composed_name = f"rendered_infographic_{uuid.uuid4().hex[:8]}.png"
                            composed_path = os.path.join(GENERATED_IMAGES_DIR, composed_name)
                            shutil.copy2(first_frame, composed_path)

                            composed_png_url = f"/api/v1/serve-image/{composed_name}"
                            result["image"]["source_image_url"] = source_image_url
                            result["image"]["image_url"] = composed_png_url
                            prior_provider = result["image"].get("provider", "unknown")
                            result["image"]["provider"] = f"{prior_provider}+html_render"

                            # Remove raw Cloudflare snapshot after composition so gallery/folder focus on final quality renders.
                            if source_image_url.startswith("/api/v1/serve-image/"):
                                raw_name = os.path.basename(source_image_url)
                                if raw_name.startswith("cloudflare_infographic_"):
                                    raw_path = os.path.join(GENERATED_IMAGES_DIR, raw_name)
                                    if os.path.isfile(raw_path):
                                        try:
                                            os.remove(raw_path)
                                        except Exception:
                                            pass

                            result["steps"].append({
                                "zone": "D",
                                "step": "Static Render",
                                "status": "done",
                                "detail": composed_name,
                            })
                except Exception as render_error:
                    logger.warning("Static image composition failed, falling back to raw image: %s", str(render_error))
                    result["steps"].append({
                        "zone": "D",
                        "step": "Static Render",
                        "status": "error",
                        "detail": str(render_error),
                    })

            detail = "High-quality composed PNG download" if composed_png_url else "Direct Cloudflare PNG download"
            result["steps"].append({"zone": "D", "step": "Image Ready", "status": "done", "detail": detail})

        # ---- MODE: ANIMATED → HTML → Frames → FFmpeg → GIF ----
        elif output_format == "animated":
            # Zone D: Gemini writes HTML/CSS
            if html_builder:
                image_url = img.get("image_url", "")
                template = {}
                if dec.get("selected_templates") and isinstance(dec["selected_templates"], list) and len(dec["selected_templates"]) > 0:
                    t = dec["selected_templates"][0] if isinstance(dec["selected_templates"][0], dict) else {}
                    template = {"style": t.get("style", "dark"), "layout": t.get("layout", "flow")}

                html_path = await html_builder.build_animated_html(
                    content=cont, image_path=image_url, template=template,
                    tweaks=tweaks, platform=platform,
                )
                result["html_path"] = html_path
                result["html_generated_by"] = "gemini_ai" if html_builder.gemini_api_key else "local_template"
                result["steps"].append({"zone": "D", "step": f"HTML Builder ({result['html_generated_by']})", "status": "done",
                                        "detail": "Animated HTML generated"})

                # Zone D.2: Frame Recorder (Playwright captures frames)
                if frame_recorder:
                    size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["default"])
                    frame_count = await frame_recorder.record_frames(
                        html_path, "live", size["width"], size["height"]
                    )
                    result["frame_count"] = frame_count
                    result["steps"].append({"zone": "D", "step": "Frame Recorder", "status": "done",
                                            "detail": f"{frame_count} frames"})

                    # Zone E: FFmpeg → GIF
                    if ffmpeg_exporter:
                        output_files = await ffmpeg_exporter.export_files(
                            frame_count, "live", include_video=False, include_static=False
                        )
                        result["output_files"] = output_files
                        result["output_urls"] = [
                            f"/api/v1/serve-file/{os.path.basename(fp)}" for fp in output_files
                        ]

                        # Find the GIF file
                        gif_file = None
                        for fp in output_files:
                            if fp.endswith(".gif"):
                                gif_file = fp

                        if gif_file:
                            result["gif_path"] = gif_file
                            result["gif_url"] = f"/api/v1/serve-file/{os.path.basename(gif_file)}"
                            result["steps"].append({"zone": "E", "step": "GIF Export", "status": "done",
                                                    "detail": f"GIF ready: {os.path.basename(gif_file)}"})
                        else:
                            result["steps"].append({"zone": "E", "step": "GIF Export", "status": "error",
                                                    "detail": "GIF not generated"})

        # ---- Zone E: Text Export (always) ----
        if export_engine:
            exp = await export_engine.export(cont, img)
            result["export"] = exp

        result["status"] = "complete"

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)
        result["steps"].append({"zone": "?", "step": "ERROR", "status": "error", "detail": str(e)})

    return result


@router.get("/serve-image/{filename}")
async def serve_image(filename: str, download: bool = Query(False)):
    """Serve generated images from generated_images (with temp fallback)."""
    safe_filename = os.path.basename(filename)
    candidates = [
        os.path.join(GENERATED_IMAGES_DIR, safe_filename),
        os.path.join(TEMP_DIR, safe_filename),
    ]
    filepath = next((path for path in candidates if os.path.exists(path)), "")

    if filepath:
        ext = os.path.splitext(safe_filename.lower())[1]
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = media_types.get(ext, "application/octet-stream")
        if download:
            return FileResponse(filepath, media_type=media_type, filename=safe_filename)
        return FileResponse(filepath, media_type=media_type)
    raise HTTPException(404, "Image not found")


@router.get("/serve-file/{filename}")
async def serve_file(filename: str, download: bool = Query(False)):
    """Serve generated files from temp directory; optionally force download."""
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp", safe_filename)
    if os.path.exists(filepath):
        ext = os.path.splitext(safe_filename.lower())[1]
        media_types = {
            ".gif": "image/gif",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".html": "text/html; charset=utf-8",
            ".zip": "application/zip",
        }
        media_type = media_types.get(ext, "application/octet-stream")
        if download:
            return FileResponse(filepath, media_type=media_type, filename=safe_filename)
        return FileResponse(filepath, media_type=media_type)
    raise HTTPException(404, "File not found")



@router.post("/pipeline/html-preview")
async def html_preview(request: dict):
    """Zone D: Build animated HTML and return for iframe preview."""
    if not html_builder:
        raise HTTPException(500, "HTMLBuilder not initialized")

    content = request.get("content_data", {})
    image_url = request.get("image_url", "")
    platform = request.get("platform", "linkedin")
    tweaks = request.get("tweaks", {})
    template = request.get("template", {})

    html_path = await html_builder.build_animated_html(
        content=content, image_path=image_url, template=template,
        tweaks=tweaks, platform=platform,
    )

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    return HTMLResponse(content=html)


@router.post("/pipeline/tweak")
async def tweak_html(request: dict):
    """Zone F: Apply tweaks to existing HTML via string replacement."""
    html_path = request.get("html_path", os.path.join("temp", "output.html"))

    if not os.path.exists(html_path):
        raise HTTPException(404, "HTML file not found — run pipeline first")

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    tweaks = request.get("tweaks", {})
    modified = apply_tweaks(html, tweaks)

    # Save back
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(modified)

    return HTMLResponse(content=modified)


@router.get("/pipeline/download-zip")
async def download_final_zip():
    """Zone G: Download the final ZIP package from output/final_package.zip"""
    zip_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "final_package.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(404, "ZIP not found — run full pipeline first")
    return FileResponse(zip_path, media_type="application/zip", filename="final_package.zip")


@router.get("/scraped-templates")
async def get_scraped_templates():
    """Zone A: Build template gallery from all sources.

    Priority order in returned list:
    1) LinkedIn
    2) Twitter
    3) Reddit
    4) Dev.to
    5) Hashnode
    6) HackerNews
    """
    templates = []

    # 1. Get scraped templates (Dev.to + Hashnode via TemplateScraper)
    if template_scraper:
        scraped = template_scraper.get_templates()
        templates.extend(scraped)

    # 2. Convert real posts from all sources into template cards
    if post_fetcher:
        try:
            # Read from cache first
            source_posts = {
                "linkedin": post_fetcher._get_cached("linkedin", 7200) or [],
                "twitter": post_fetcher._get_cached("twitter", 7200) or [],
                "reddit": post_fetcher._get_cached("reddit", 1800) or [],
                "devto": post_fetcher._get_cached("devto", 1800) or [],
                "hashnode": post_fetcher._get_cached("hashnode", 1800) or [],
                "hackernews": post_fetcher._get_cached("hackernews", 1800) or [],
            }

            # Fetch missing sources
            missing = [key for key, items in source_posts.items() if not items]
            if missing:
                import asyncio

                source_fetchers = {
                    "linkedin": post_fetcher._fetch_linkedin_posts,
                    "twitter": post_fetcher._fetch_twitter_posts,
                    "reddit": post_fetcher._fetch_reddit_posts,
                    "devto": post_fetcher._fetch_devto_posts,
                    "hashnode": post_fetcher._fetch_hashnode_posts,
                    "hackernews": post_fetcher._fetch_hackernews_posts,
                }

                tasks = [source_fetchers[name](limit=8) for name in missing if name in source_fetchers]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, name in enumerate([n for n in missing if n in source_fetchers]):
                    if i < len(results) and not isinstance(results[i], Exception):
                        source_posts[name] = results[i]

            def to_template(post: dict, source_name: str, idx: int) -> dict:
                visual_type = str(post.get("visual_type", "")).lower()
                section_map = {
                    "mind_map": 6,
                    "steps": 6,
                    "comparison": 5,
                    "cheat_sheet": 4,
                    "architecture": 6,
                    "roadmap": 5,
                    "listicle": 5,
                    "explainer": 4,
                }
                section_count = section_map.get(visual_type, 4)

                layout_map = {
                    "linkedin": "carousel",
                    "twitter": "thread",
                    "reddit": "grid",
                    "devto": "single",
                    "hashnode": "single",
                    "hackernews": "list",
                }
                style_map = {
                    "linkedin": "dark",
                    "twitter": "dark",
                    "reddit": "dark",
                    "devto": "light",
                    "hashnode": "dark",
                    "hackernews": "light",
                }

                source_label = source_name
                if source_name == "reddit" and post.get("source"):
                    source_label = str(post.get("source")).lower()

                return {
                    "id": f"{source_name}_{idx+1}",
                    "source": source_label,
                    "title": post.get("title", ""),
                    "coverImage": post.get("image_url", "") or post.get("image", "") or post.get("thumbnail", ""),
                    "sectionCount": section_count,
                    "style": style_map.get(source_name, "dark"),
                    "layout": layout_map.get(source_name, "single"),
                    "tags": post.get("tags", []),
                    "url": _extract_template_source_url(post, source_name),
                }

            # Priority order: LinkedIn + Twitter first, then others
            ordered_sources = ["linkedin", "twitter", "reddit", "devto", "hashnode", "hackernews"]
            for src in ordered_sources:
                items = source_posts.get(src, [])[:10]
                for i, post in enumerate(items):
                    templates.append(to_template(post, src, i))

        except Exception as e:
            logger.warning(f"Template conversion from post sources failed: {e}")

    # Assign unique IDs to scraped templates that don't have one
    for i, t in enumerate(templates):
        if not t.get("id"):
            t["id"] = f"scraped_{i+1}"

    source_counts = {}
    for t in templates:
        src = t.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "templates": templates,
        "count": len(templates),
        "source": f"All sources (priority: LinkedIn + Twitter) ({', '.join(f'{k}: {v}' for k, v in source_counts.items())})",
    }


@router.post("/refresh-sources")
async def refresh_sources(request: dict = None):
    """Force refresh for Zone A data panels.

    Refreshes:
    - posts cache (all sources)
    - trends cache
    - template scrape cache (optional)
    """
    request = request or {}
    include_template_scrape = bool(request.get("include_template_scrape", True))

    result = {
        "status": "success",
        "steps": [],
        "counts": {},
    }

    try:
        if post_fetcher:
            post_fetcher._cache.clear()
            posts = await post_fetcher.get_trending_posts(limit=30)
            result["counts"]["posts"] = len(posts)
            result["steps"].append("posts refreshed")

        if trend_engine:
            try:
                topics = await trend_engine.refresh_trends()
            except Exception:
                topics = await trend_engine.get_trending_topics(limit=20)
            result["counts"]["trends"] = len(topics)
            result["steps"].append("trends refreshed")

        if include_template_scrape and template_scraper:
            templates = await template_scraper.scrape_templates()
            result["counts"]["scraped_templates"] = len(templates)
            result["steps"].append("templates refreshed")

        return result
    except Exception as e:
        logger.error("refresh-sources failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scraped-templates/refresh")
async def refresh_scraped_templates():
    """Zone A: Re-scrape templates from Dev.to + Hashnode."""
    if not template_scraper:
        raise HTTPException(500, "TemplateScraper not initialized")

    templates = await template_scraper.scrape_templates()
    return {
        "templates": templates,
        "count": len(templates),
        "message": f"Scraped {len(templates)} templates",
    }


@router.get("/pipeline/platforms")
async def get_platform_specs():
    """Zone G: Get platform size specifications."""
    return {
        "platforms": {
            k: {"width": v["width"], "height": v["height"], "label": f"{v['width']}×{v['height']}"}
            for k, v in PLATFORM_SIZES.items()
        }
    }


# ============================================================================
# HEALTH CHECK
# ========================================================================== 

@router.get("/health", response_model=dict)
async def health_check():
    """Check if API is running"""
    return {
        "status": "healthy",
        "message": "AI Content Pipeline is running",
    }


# ============================================================================
# DOWNLOAD ZIP
# ============================================================================

@router.post("/download")
async def download_zip(request: dict):
    """Download generated content as a ZIP file.
    
    Expects: {content_data: {...}, image_data: {...}, export_data: {...}}
    Returns: ZIP file with post.txt, metadata.json, captions.txt
    """
    content_data = request.get("content_data", {})
    image_data = request.get("image_data", {})
    export_data = request.get("export_data", {})

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Full post text
        post_text = export_data.get("full_post_text", "No content generated")
        zf.writestr("post.txt", post_text)

        # 2. Caption variations
        captions = export_data.get("caption_variations", [])
        caption_text = ""
        for i, cap in enumerate(captions, 1):
            style = cap.get("style", f"Variation {i}")
            text = cap.get("text", cap.get("caption", ""))
            caption_text += f"--- {style.upper()} ---\n{text}\n\n"
        if caption_text:
            zf.writestr("captions.txt", caption_text)

        # 3. Image URL (since we can't download the actual image due to redirect)
        image_url = image_data.get("image_url", "")
        if image_url:
            zf.writestr("image_url.txt", f"Image URL:\n{image_url}\n\nOpen this URL in a browser to download the image.")

        # 4. Metadata JSON
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "title": content_data.get("title", ""),
            "platform": content_data.get("platform", ""),
            "category": content_data.get("category", ""),
            "ai_provider": content_data.get("ai_provider", ""),
            "hashtags": content_data.get("hashtags", []),
            "sections": len(content_data.get("sections", [])),
            "image_url": image_url,
            "image_provider": image_data.get("provider", ""),
            "post_length": len(post_text),
        }
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        # 5. Full content sections for reference
        sections = content_data.get("sections", [])
        if sections:
            sections_text = ""
            for s in sections:
                heading = s.get("heading", "Section")
                content = s.get("content", "")
                sections_text += f"## {heading}\n{content}\n\n"
            zf.writestr("full_content.md", sections_text)

    zip_buffer.seek(0)

    title = content_data.get("title", "pipeline_output")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)[:40]
    filename = f"{safe_name.strip().replace(' ', '_')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================================
# DATA SOURCE STATUS
# ============================================================================

@router.get("/status")
async def get_status():
    """Get status of all data sources and caches.
    Shows which sources have data, when they were last refreshed,
    and how many items each source has.
    """
    status = {
        "server_time": datetime.now().isoformat(),
        "sources": {},
    }

    # PostFetcher cache status
    if post_fetcher and hasattr(post_fetcher, "_cache"):
        for key, entry in post_fetcher._cache.items():
            age = int(time.time() - entry["timestamp"])
            status["sources"][key] = {
                "count": len(entry["data"]),
                "last_refresh": datetime.fromtimestamp(entry["timestamp"]).isoformat(),
                "age_seconds": age,
                "age_human": f"{age // 60}m {age % 60}s ago",
                "fresh": age < 3600,
            }

    # What sources are expected
    expected = ["linkedin", "twitter", "devto", "reddit", "hashnode", "hackernews"]
    for src in expected:
        if src not in status["sources"]:
            status["sources"][src] = {
                "count": 0,
                "last_refresh": None,
                "age_seconds": None,
                "age_human": "not fetched yet",
                "fresh": False,
            }

    return status
