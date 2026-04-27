"""
Zone D — FFmpeg Exporter (Step 6, Part 2)
===========================================
Stitches frames into GIF and static PNG using imageio-ffmpeg.

Optionally exports: temp/output_static.png (copy of frame_0001)
If live mode:
    - temp/output.gif (palette-optimized)

Optional:
    - temp/output_video.mp4 (15fps, h264) when include_video=True
"""

import os
import shutil
import logging
import subprocess
from typing import List

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FRAMES_DIR = os.path.join(TEMP_DIR, "frames")


def _get_ffmpeg_path() -> str:
    """Get FFmpeg binary path from imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # Fall back to system ffmpeg


class FFmpegExporter:
    """Exports frames to PNG/GIF and optionally MP4 using FFmpeg."""

    def __init__(self):
        self._ffmpeg = _get_ffmpeg_path()
        logger.info(f"FFmpegExporter initialized (binary: {self._ffmpeg})")

    async def export_files(
        self,
        frame_count: int,
        output_mode: str = "simple",
        include_video: bool = False,
        include_static: bool = True,
    ) -> List[str]:
        """Export frames to final files.

        Args:
            frame_count: Number of frames in temp/frames/
            output_mode: 'simple' or 'live'
            include_video: Whether to generate MP4 in live mode
            include_static: Whether to generate output_static.png from first frame

        Returns:
            List of output file paths
        """
        output_files = []

        # Optional: static PNG from first frame
        static_png = os.path.join(TEMP_DIR, "output_static.png")
        first_frame = os.path.join(FRAMES_DIR, "frame_0001.png")
        if include_static and os.path.exists(first_frame):
            shutil.copy2(first_frame, static_png)
            output_files.append(static_png)
            logger.info(f"Static PNG: {static_png}")

        if output_mode == "live" and frame_count > 1:
            if include_video:
                # MP4 from frames
                mp4_path = os.path.join(TEMP_DIR, "output_video.mp4")
                try:
                    self._frames_to_mp4(mp4_path)
                    if os.path.exists(mp4_path):
                        output_files.append(mp4_path)
                        logger.info(f"MP4 video: {mp4_path} ({os.path.getsize(mp4_path)} bytes)")
                except Exception as e:
                    logger.error(f"MP4 export failed: {e}")

            # GIF from frames
            gif_path = os.path.join(TEMP_DIR, "output.gif")
            try:
                self._frames_to_gif(gif_path)
                if os.path.exists(gif_path):
                    output_files.append(gif_path)
                    logger.info(f"GIF: {gif_path} ({os.path.getsize(gif_path)} bytes)")
            except Exception as e:
                logger.error(f"GIF export failed: {e}")

        elif output_mode == "simple":
            # Still GIF from single frame (1 second)
            gif_path = os.path.join(TEMP_DIR, "output.gif")
            try:
                self._single_frame_gif(first_frame, gif_path)
                if os.path.exists(gif_path):
                    output_files.append(gif_path)
                    logger.info(f"Still GIF: {gif_path}")
            except Exception as e:
                logger.error(f"GIF export failed: {e}")

        return output_files

    def _frames_to_mp4(self, output_path: str):
        """Stitch frames into MP4 at 15fps."""
        input_pattern = os.path.join(FRAMES_DIR, "frame_%04d.png")
        cmd = [
            self._ffmpeg, "-y",
            "-framerate", "15",
            "-i", input_pattern,
            "-c:v", "libx264",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        logger.info(f"FFmpeg MP4: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"FFmpeg MP4 stderr: {result.stderr[:500]}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr[:200]}")

    def _frames_to_gif(self, output_path: str):
        """Generate optimized GIF from frames using palette generation."""
        input_pattern = os.path.join(FRAMES_DIR, "frame_%04d.png")
        palette_path = os.path.join(TEMP_DIR, "palette.png")
        gif_width = 960

        # Step 1: Generate palette
        cmd1 = [
            self._ffmpeg, "-y",
            "-framerate", "15",
            "-i", input_pattern,
            "-vf", f"fps=12,scale={gif_width}:-1:flags=lanczos,palettegen=max_colors=128",
            palette_path,
        ]
        subprocess.run(cmd1, capture_output=True, text=True, timeout=60)

        # Step 2: Use palette to create GIF
        cmd2 = [
            self._ffmpeg, "-y",
            "-framerate", "15",
            "-i", input_pattern,
            "-i", palette_path,
            "-lavfi", f"fps=12,scale={gif_width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a",
            output_path,
        ]
        result = subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"FFmpeg GIF stderr: {result.stderr[:500]}")

        # Cleanup palette
        if os.path.exists(palette_path):
            os.remove(palette_path)

    def _single_frame_gif(self, frame_path: str, output_path: str):
        """Create a 1-second still GIF from a single frame."""
        gif_width = 960
        cmd = [
            self._ffmpeg, "-y",
            "-loop", "1",
            "-i", frame_path,
            "-t", "1",
            "-vf", f"scale={gif_width}:-1:flags=lanczos",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"FFmpeg still GIF stderr: {result.stderr[:500]}")
