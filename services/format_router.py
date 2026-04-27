"""
Zone G — Format Router (Step 7)
=================================
Resizes and re-encodes output files per platform.
Creates per-platform output folder + captions.txt + final ZIP.

Platform specs:
  linkedin:  PNG 1200x1500, MP4 1080x1350
  instagram: PNG 1080x1080, GIF 1080x1080
  twitter:   PNG 1200x675, MP4 1280x720
  medium:    PNG 1600x840 (cover)
  devto:     PNG 1600x840 (cover), Markdown
  hashnode:  PNG 1600x840 (cover), Markdown
"""

import os
import shutil
import logging
import subprocess
import zipfile
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

PLATFORM_SPECS = {
    "linkedin": {"png": (1200, 1500), "mp4": (1080, 1350)},
    "instagram": {"png": (1080, 1080), "gif": (1080, 1080)},
    "twitter": {"png": (1200, 675), "mp4": (1280, 720)},
    "medium": {"png": (1600, 840)},
    "devto": {"png": (1600, 840)},
    "hashnode": {"png": (1600, 840)},
}


def _get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


class FormatRouter:
    """Resizes output to platform-specific formats and creates final ZIP."""

    def __init__(self):
        self._ffmpeg = _get_ffmpeg_path()
        logger.info("FormatRouter initialized")

    async def route_formats(
        self,
        input_files: Dict[str, str],
        platforms: List[str],
        content: Dict[str, Any],
    ) -> str:
        """Resize and export for each platform.

        Args:
            input_files: {'png': path, 'mp4': path, 'gif': path}
            platforms: ['linkedin', 'instagram', 'twitter', ...]
            content: Content data with captions and hashtags

        Returns:
            Path to final ZIP file
        """
        # Clean output directory
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        for platform in platforms:
            specs = PLATFORM_SPECS.get(platform, {})
            plat_dir = os.path.join(OUTPUT_DIR, platform)
            os.makedirs(plat_dir, exist_ok=True)

            # Resize PNG
            if "png" in specs and "png" in input_files and os.path.exists(input_files["png"]):
                w, h = specs["png"]
                out_png = os.path.join(plat_dir, f"{platform}_image.png")
                self._resize_image(input_files["png"], out_png, w, h)

            # Resize MP4
            if "mp4" in specs and "mp4" in input_files and os.path.exists(input_files.get("mp4", "")):
                w, h = specs["mp4"]
                out_mp4 = os.path.join(plat_dir, f"{platform}_video.mp4")
                self._resize_video(input_files["mp4"], out_mp4, w, h)

            # Resize GIF
            if "gif" in specs and "gif" in input_files and os.path.exists(input_files.get("gif", "")):
                w, h = specs["gif"]
                out_gif = os.path.join(plat_dir, f"{platform}_anim.gif")
                self._resize_image(input_files["gif"], out_gif, w, h)

        # Create captions.txt
        self._write_captions(content, platforms)

        # Create markdown for dev.to/hashnode/medium
        self._write_markdown(content, platforms)

        # ZIP everything
        zip_path = os.path.join(OUTPUT_DIR, "final_package.zip")
        self._create_zip(zip_path)

        logger.info(f"Final ZIP: {zip_path} ({os.path.getsize(zip_path)} bytes)")
        return zip_path

    def _resize_image(self, src: str, dst: str, width: int, height: int):
        """Resize image using FFmpeg."""
        cmd = [
            self._ffmpeg, "-y",
            "-i", src,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            dst,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info(f"Resized: {dst} ({width}x{height})")
            else:
                # Fallback: just copy
                shutil.copy2(src, dst)
                logger.warning(f"Resize failed, copied original: {dst}")
        except Exception as e:
            shutil.copy2(src, dst)
            logger.warning(f"Resize error, copied original: {e}")

    def _resize_video(self, src: str, dst: str, width: int, height: int):
        """Resize video using FFmpeg."""
        cmd = [
            self._ffmpeg, "-y",
            "-i", src,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-crf", "23",
            dst,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                shutil.copy2(src, dst)
        except Exception:
            shutil.copy2(src, dst)

    def _write_captions(self, content: Dict, platforms: List[str]):
        """Write captions.txt with platform-specific captions and hashtags."""
        captions = content.get("captions", {})
        hashtags = content.get("hashtags", {})
        title = content.get("title", "")

        lines = [f"# Post: {title}", f"# Generated: {__import__('datetime').datetime.now().isoformat()}", ""]

        for platform in platforms:
            lines.append(f"{'='*60}")
            lines.append(f"PLATFORM: {platform.upper()}")
            lines.append(f"{'='*60}")

            # Caption
            if isinstance(captions, dict):
                cap = captions.get(platform, captions.get("linkedin", ""))
            else:
                cap = str(captions) if captions else ""
            lines.append(f"\nCaption:\n{cap}")

            # Hashtags
            if isinstance(hashtags, dict):
                tags = hashtags.get(platform, hashtags.get("linkedin", []))
            elif isinstance(hashtags, list):
                tags = hashtags
            else:
                tags = []
            if tags:
                lines.append(f"\nHashtags: {' '.join(tags)}")

            lines.append("")

        captions_path = os.path.join(OUTPUT_DIR, "captions.txt")
        with open(captions_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"Captions saved: {captions_path}")

    def _write_markdown(self, content: Dict, platforms: List[str]):
        """Write Markdown files for medium/devto/hashnode."""
        md_platforms = [p for p in platforms if p in ("medium", "devto", "hashnode")]
        if not md_platforms:
            return

        title = content.get("title", "Post")
        sections = content.get("sections", [])
        hashtags = content.get("hashtags", [])

        md = f"# {title}\n\n"
        for sec in sections:
            heading = sec.get("heading", "")
            body = sec.get("content", "")
            points = sec.get("points", [])
            md += f"## {heading}\n\n"
            if points:
                md += "\n".join(f"- {p}" for p in points) + "\n\n"
            elif body:
                md += body + "\n\n"

        if isinstance(hashtags, list):
            md += "\n---\n" + " ".join(hashtags) + "\n"

        for platform in md_platforms:
            plat_dir = os.path.join(OUTPUT_DIR, platform)
            os.makedirs(plat_dir, exist_ok=True)
            md_path = os.path.join(plat_dir, f"{platform}_article.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)

    def _create_zip(self, zip_path: str):
        """ZIP the entire output/ directory."""
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(OUTPUT_DIR):
                # Skip the ZIP file itself
                for file in files:
                    if file == "final_package.zip":
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, OUTPUT_DIR)
                    zf.write(file_path, arcname)
