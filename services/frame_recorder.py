"""
Zone D — Frame Recorder (Step 6, Part 1)
==========================================
Uses Playwright to record frames from animated HTML.

Simple mode: 1 screenshot → temp/frames/frame_0001.png
Live mode: 75 frames at 15fps → temp/frames/frame_0001.png to frame_0075.png
"""

import os
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FRAMES_DIR = os.path.join(TEMP_DIR, "frames")


class FrameRecorder:
    """Records frames from animated HTML using Playwright."""

    def __init__(self):
        logger.info("FrameRecorder initialized (Playwright-based)")

    async def record_frames(
        self,
        html_path: str,
        output_mode: str = "simple",
        width: int = 1200,
        height: int = 1500,
    ) -> int:
        """Record frames from HTML file.

        Args:
            html_path: Path to HTML file (temp/output.html)
            output_mode: 'simple' (1 frame) or 'live' (75 frames at 15fps)
            width: Viewport width
            height: Viewport height

        Returns:
            Number of frames captured
        """
        # Clear frames directory
        if os.path.exists(FRAMES_DIR):
            shutil.rmtree(FRAMES_DIR)
        os.makedirs(FRAMES_DIR, exist_ok=True)

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})

            # Load HTML file
            file_url = f"file:///{html_path.replace(os.sep, '/')}"
            await page.goto(file_url, wait_until="networkidle")
            await page.wait_for_timeout(2500)  # Extra settle time for fonts/layout before capture

            if output_mode == "simple":
                # Single screenshot
                frame_path = os.path.join(FRAMES_DIR, "frame_0001.png")
                await page.screenshot(path=frame_path, full_page=True, type="png")
                logger.info(f"Simple mode: 1 frame captured → {frame_path}")
                frame_count = 1

            else:
                # Live mode: 75 frames at 15fps (5 seconds of animation)
                frame_count = 75
                delay_ms = 70

                for i in range(1, frame_count + 1):
                    frame_path = os.path.join(FRAMES_DIR, f"frame_{i:04d}.png")
                    await page.screenshot(path=frame_path, full_page=True, type="png")

                    if i < frame_count:
                        await page.wait_for_timeout(delay_ms)

                    if i % 15 == 0:
                        logger.info(f"Recorded frame {i}/{frame_count}")

                logger.info(f"Live mode: {frame_count} frames captured")

            await browser.close()

        return frame_count
