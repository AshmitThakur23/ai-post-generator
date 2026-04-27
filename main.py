"""
AI Content Pipeline — Main Entry Point
========================================
Zones: A (data) → B (input) → C (AI) → D (HTML/animation) → E (output) → F (tweak) → G (format)

Background auto-fetch every 1 hour.
Template scraping on startup.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config.settings import settings
from services.trend_engine import TrendEngine
from services.template_provider import TemplateProvider
from services.post_fetcher import PostFetcher
from services.template_detector import TemplateDetector
from services.decision_engine import DecisionEngine
from services.content_generator import ContentGenerator
from services.image_generator import ImageGenerator
from services.export_engine import ExportEngine
from services.html_builder import HTMLBuilder
from services.template_scraper import TemplateScraper
from services.frame_recorder import FrameRecorder
from services.ffmpeg_exporter import FFmpegExporter
from services.format_router import FormatRouter
from api import routes

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global services
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

_refresh_task = None
REFRESH_INTERVAL = 3600


async def background_refresh():
    """Background: fetch trends + posts every hour, scrape templates on first run."""
    global template_scraper

    logger.info("=" * 60)
    logger.info("BACKGROUND: Initial data fetch + template scraping...")
    logger.info("=" * 60)

    # Scrape templates on startup
    if template_scraper:
        try:
            templates = await template_scraper.scrape_templates()
            logger.info(f"BACKGROUND: Scraped {len(templates)} templates")
        except Exception as e:
            logger.error(f"BACKGROUND: Template scrape error: {e}")

    await _do_refresh()

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        logger.info("=" * 60)
        logger.info("BACKGROUND: Auto-refreshing data...")
        logger.info("=" * 60)
        await _do_refresh()


async def _do_refresh():
    try:
        if post_fetcher:
            post_fetcher._cache.clear()
            logger.info("BACKGROUND: Cache cleared, fetching fresh posts...")
            posts = await post_fetcher.get_trending_posts(limit=30)
            logger.info(f"BACKGROUND: Fetched {len(posts)} posts")

        if trend_engine:
            topics = await trend_engine.get_trending_topics(limit=20)
            logger.info(f"BACKGROUND: Fetched {len(topics)} trends")
    except Exception as e:
        logger.error(f"BACKGROUND: Refresh error: {type(e).__name__}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global trend_engine, template_provider, post_fetcher, template_detector
    global decision_engine, content_generator, image_generator, export_engine
    global html_builder, template_scraper, frame_recorder, ffmpeg_exporter, format_router
    global _refresh_task

    logger.info("=" * 60)
    logger.info("Starting AI Content Pipeline Server")
    logger.info("=" * 60)

    # Zone A
    trend_engine = TrendEngine()
    template_provider = TemplateProvider()
    post_fetcher = PostFetcher()
    template_scraper = TemplateScraper()

    # Zone B
    template_detector = TemplateDetector()
    decision_engine = DecisionEngine(trend_engine=trend_engine, template_provider=template_provider)

    # Zone C
    content_generator = ContentGenerator(
        groq_api_key=settings.GROQ_API_KEY,
        gemini_api_key=settings.GEMINI_API_KEY,
    )
    image_generator = ImageGenerator(
        cloudflare_api_token=settings.CLOUDFLARE_API_TOKEN,
        cloudflare_account_id=settings.CLOUDFLARE_ACCOUNT_ID,
        cloudflare_image_model=settings.CLOUDFLARE_IMAGE_MODEL,
    )

    # Zone D
    html_builder = HTMLBuilder(gemini_api_key=settings.GEMINI_API_KEY)
    frame_recorder = FrameRecorder()
    ffmpeg_exporter = FFmpegExporter()

    # Zone E + G
    export_engine = ExportEngine()
    format_router = FormatRouter()

    # Pass ALL services to routes
    routes.set_services(
        engine=trend_engine,
        provider=template_provider,
        fetcher=post_fetcher,
        detector=template_detector,
        decision=decision_engine,
        generator=content_generator,
        image_gen=image_generator,
        export_gen=export_engine,
        builder=html_builder,
        scraper=template_scraper,
        recorder=frame_recorder,
        ffmpeg=ffmpeg_exporter,
        router=format_router,
    )

    logger.info("All services initialized (Zones A-G)")
    _refresh_task = asyncio.create_task(background_refresh())

    yield

    logger.info("Shutting down...")
    if _refresh_task:
        _refresh_task.cancel()
        try: await _refresh_task
        except asyncio.CancelledError: pass
    if trend_engine: await trend_engine.close()
    logger.info("Services closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Content Pipeline",
        description="Zone A→G: Trends → Posts → Decision → Content → Image → HTML → Animation → Export",
        version=settings.VERSION,
        docs_url="/api/docs",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(routes.router, prefix="/api/v1")

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")
        @app.get("/")
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_dir, "index.html"))

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
