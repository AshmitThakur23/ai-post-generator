"""Image Generator Service
Generates infographic images using Cloudflare Workers AI FLUX models.
"""

import logging
import os
import uuid
import base64
import hashlib
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

CLOUDFLARE_TIMEOUT = 150.0
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
GENERATED_IMAGES_DIR = os.path.join(BASE_DIR, "generated_images")

PLATFORM_SIZES = {
    "linkedin": {"width": 1200, "height": 1500},
    "instagram": {"width": 1080, "height": 1080},
    "twitter": {"width": 1200, "height": 675},
}


class ImageGenerationOutput:
    """Generated image output"""

    def __init__(self, id, image_url, prompt_used, platform, provider="cloudflare"):
        self.id = id
        self.image_url = image_url
        self.prompt_used = prompt_used
        self.platform = platform
        self.provider = provider

    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "prompt_used": self.prompt_used,
            "platform": self.platform,
            "provider": self.provider,
        }


class ImageGenerator:
    """Generate infographic images using Cloudflare Workers AI FLUX models."""

    def __init__(
        self,
        cloudflare_api_token: Optional[str] = None,
        cloudflare_account_id: Optional[str] = None,
        cloudflare_image_model: Optional[str] = None,
    ):
        self.cloudflare_api_token = cloudflare_api_token
        self.cloudflare_account_id = cloudflare_account_id
        self.cloudflare_image_model = (
            cloudflare_image_model
            or os.getenv("CLOUDFLARE_IMAGE_MODEL", "").strip()
            or "@cf/black-forest-labs/flux-2-klein-4b"
        )
        self.last_cloudflare_model = ""
        self.max_saved_images = 40

        # Output directory for saved images
        self.output_dir = GENERATED_IMAGES_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        if self.cloudflare_api_token and self.cloudflare_account_id:
            logger.info(
                "ImageGenerator initialized (Cloudflare model: %s)",
                self.cloudflare_image_model,
            )
        else:
            logger.warning("ImageGenerator initialized without Cloudflare credentials")

    async def generate(self, content_data: Dict[str, Any]) -> ImageGenerationOutput:
        """Generate infographic image"""
        logger.info(f"🖼️ Generating image for: {content_data.get('title', 'Unknown')}")

        content_id = content_data.get("id", "unknown")
        title = content_data.get("title", "Untitled")
        sections = content_data.get("sections", [])
        style_hint = content_data.get("style_hint", "professional minimal design")
        platform = content_data.get("platform", "linkedin")
        category = content_data.get("category", "General")
        template_style = content_data.get("template_style", "")
        template_layout = content_data.get("template_layout", "")
        key_points = content_data.get("key_points", [])
        model_override = str(content_data.get("cloudflare_model", "") or "").strip() or None

        prompt = self._build_prompt(
            title,
            sections,
            style_hint,
            platform,
            category,
            template_style,
            template_layout,
            key_points,
        )

        if self.cloudflare_api_token and self.cloudflare_account_id:
            result = await self._generate_with_cloudflare(
                prompt=prompt,
                platform=platform,
                model_override=model_override,
            )
            if result:
                logger.info("✅ Image generated with Cloudflare Workers AI")
                return ImageGenerationOutput(
                    id=content_id, image_url=result, prompt_used=prompt,
                    platform=platform, provider=f"cloudflare:{self.last_cloudflare_model or 'unknown'}",
                )
        else:
            logger.warning("Cloudflare image generation skipped: missing API token/account id")

        # Final fallback: placeholder
        logger.warning("🚨 Cloudflare image generation failed — using placeholder")
        return ImageGenerationOutput(
            id=content_id,
            image_url=self._get_fallback_url(platform),
            prompt_used=prompt, platform=platform, provider="cloudflare_unavailable",
        )

    def _build_prompt(
        self,
        title,
        sections,
        style_hint,
        platform,
        category,
        template_style="",
        template_layout="",
        key_points=None,
    ) -> str:
        """Build infographic image prompt"""
        section_names = []
        for s in (sections or [])[:4]:
            if isinstance(s, dict):
                section_names.append(s.get("heading", "section"))
            else:
                section_names.append(str(s))
        section_text = ", ".join(section_names) if section_names else "key concepts"

        key_points_list = []
        for kp in (key_points or [])[:4]:
            if kp:
                key_points_list.append(str(kp))
        key_points_text = ", ".join(key_points_list)

        size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["linkedin"])

        normalized_layout = str(template_layout or "").strip().lower()
        if normalized_layout in {"flow", "timeline", "process"}:
            layout_focus = "left-to-right workflow map with connected stages"
        elif normalized_layout in {"grid", "matrix"}:
            layout_focus = "modular architecture board with grouped system blocks"
        else:
            layout_focus = "centered architecture diagram with clear connectors"

        composition_brief, palette_brief, motif_brief = self._topic_visual_brief(
            title=title,
            category=category,
            key_points=key_points,
        )

        prompt = (
            f"Design one premium {platform} technology infographic in workflow-diagram style for '{title}'. "
            f"Category: {category}. Main concepts: {section_text}. "
            f"Core takeaways: {key_points_text or 'practical engineering insights'}. "
            f"Visual direction: {style_hint}. "
            f"Template style: {template_style or 'clean-professional'}. "
            f"Template layout intent: {template_layout or 'flow'} ({layout_focus}). "
            f"Composition variant: {composition_brief}. "
            f"Color direction: {palette_brief}. "
            f"Topic motifs: {motif_brief}. "
            f"Canvas size: {size['width']}x{size['height']} pixels. "
            "Composition requirements: top title band, central architecture/workflow panel, bottom quick insight badges. "
            "Include 6 to 9 rounded modules connected by arrows or curved signal lines with clear directional flow. "
            "Use clean vector design, enterprise UI card language, subtle gradients, and crisp icon-like glyphs. "
            "Prioritize readability and spacing: strong hierarchy, large labels, generous margins, no visual clutter. "
            "Avoid long paragraphs inside the image. If labels appear, keep them short and meaningful. "
            "Allowed short labels: Ingest, API, Queue, Workers, DB, Cache, Analytics, Guardrails, Output. "
            "Absolutely avoid gibberish text, random letters, corrupted words, or tiny unreadable typography. "
            "Do not render paragraphs, sentences, or decorative fake words inside the illustration. "
            "No photo-real people, no logos, no watermarks, no screenshots. "
            "Final result must look like a polished software architecture infographic suitable for LinkedIn and technical audiences."
        )
        return prompt

    async def _generate_with_cloudflare(
        self,
        prompt: str,
        platform: str,
        model_override: Optional[str] = None,
    ) -> Optional[str]:
        """Generate image via Cloudflare Workers AI REST endpoint."""
        try:
            size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["linkedin"])
            width = size["width"]
            height = size["height"]

            model_name = model_override or self.cloudflare_image_model
            self.last_cloudflare_model = model_name

            endpoint = (
                f"https://api.cloudflare.com/client/v4/accounts/"
                f"{self.cloudflare_account_id}/ai/run/{model_name}"
            )

            headers = {
                "Authorization": f"Bearer {self.cloudflare_api_token}",
                "Accept": "application/json",
            }

            payload = {
                "prompt": prompt,
                "width": width,
                "height": height,
            }

            form_fields = {
                "prompt": (None, prompt),
                "width": (None, str(width)),
                "height": (None, str(height)),
            }

            prefers_multipart = self._model_prefers_multipart(model_name)

            async with httpx.AsyncClient(timeout=CLOUDFLARE_TIMEOUT) as client:
                if prefers_multipart:
                    # FLUX klein models require multipart form-data input.
                    resp = await client.post(endpoint, headers=headers, files=form_fields)
                    if resp.status_code >= 400:
                        resp = await client.post(
                            endpoint,
                            headers={**headers, "Content-Type": "application/json"},
                            json=payload,
                        )
                else:
                    # JSON is supported by many models; keep multipart as fallback.
                    resp = await client.post(
                        endpoint,
                        headers={**headers, "Content-Type": "application/json"},
                        json=payload,
                    )
                    if resp.status_code >= 400:
                        resp = await client.post(endpoint, headers=headers, files=form_fields)

                if resp.status_code != 200:
                    logger.error(
                        "Cloudflare image API (%s): %s - %s",
                        model_name,
                        resp.status_code,
                        resp.text[:350],
                    )
                    return None

                data = resp.json()
                if data.get("success") is False:
                    logger.error("Cloudflare image API error payload: %s", str(data.get("errors", []))[:350])
                    return None

                image_b64 = self._extract_cloudflare_image(data.get("result"))
                if not image_b64:
                    logger.error("Cloudflare image API (%s): no image found in result", model_name)
                    return None

                img_bytes = base64.b64decode(image_b64)
                filename = f"cloudflare_infographic_{uuid.uuid4().hex[:8]}.png"
                filepath = os.path.join(self.output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                self._cleanup_saved_images()

                logger.info(
                    "✅ Cloudflare image saved (%s): %s (%d bytes)",
                    model_name,
                    filepath,
                    len(img_bytes),
                )
                return f"/api/v1/serve-image/{filename}"

        except Exception as e:
            logger.error(f"Cloudflare image error: {e}")
            return None

    def _model_prefers_multipart(self, model_name: str) -> bool:
        """Return True for model families that require multipart form-data input."""
        normalized = (model_name or "").strip().lower()
        return "flux-2-klein" in normalized

    def _topic_visual_brief(self, title: str, category: str, key_points=None):
        """Generate deterministic composition cues so each topic gets a distinct visual direction."""
        seed_input = f"{title}|{category}|{'|'.join(str(k) for k in (key_points or []))}"
        digest = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16)

        compositions = [
            "hub-and-spoke orchestration board",
            "left-to-right pipeline with checkpoints",
            "layered enterprise stack with guardrails",
            "control-plane and data-plane split diagram",
            "modular system map with service boundaries",
        ]
        palettes = [
            "deep navy with cyan accents",
            "charcoal with teal and steel blue",
            "slate with electric blue highlights",
            "midnight with emerald-cyan accents",
            "dark graphite with cool azure glow",
        ]
        motifs = [
            "API gateways, queues, policy shields",
            "agent nodes, observability, event streams",
            "service mesh links, data stores, audit trail",
            "workflow states, validation gates, output channels",
            "orchestrator core, compute workers, telemetry lines",
        ]

        return (
            compositions[index % len(compositions)],
            palettes[(index // 3) % len(palettes)],
            motifs[(index // 7) % len(motifs)],
        )

    def _cleanup_saved_images(self):
        """Keep only recent generated images and remove legacy temp Cloudflare PNG files."""
        try:
            files = []
            for name in os.listdir(self.output_dir):
                if not name.startswith("cloudflare_infographic_") or not name.lower().endswith(".png"):
                    continue
                path = os.path.join(self.output_dir, name)
                if os.path.isfile(path):
                    files.append(path)

            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for stale in files[self.max_saved_images:]:
                try:
                    os.remove(stale)
                except Exception:
                    pass

            # Cleanup older location used by previous versions.
            if os.path.isdir(TEMP_DIR):
                for name in os.listdir(TEMP_DIR):
                    if not name.startswith("cloudflare_infographic_") or not name.lower().endswith(".png"):
                        continue
                    legacy_path = os.path.join(TEMP_DIR, name)
                    if os.path.isfile(legacy_path):
                        try:
                            os.remove(legacy_path)
                        except Exception:
                            pass
        except Exception:
            pass

    def _extract_cloudflare_image(self, result: Any) -> Optional[str]:
        """Extract base64 image payload from Cloudflare result object."""
        if isinstance(result, dict):
            # Common Workers AI image payload
            if isinstance(result.get("image"), str) and result.get("image"):
                return result.get("image")

            # Some model responses can nest output objects
            nested = result.get("output")
            if isinstance(nested, dict) and isinstance(nested.get("image"), str):
                return nested.get("image")

        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and isinstance(item.get("image"), str):
                    return item.get("image")

        return None

    def _get_fallback_url(self, platform: str) -> str:
        if platform == "instagram":
            return "https://placehold.co/1080x1080/1a1a2e/4fc3f7?text=Infographic"
        if platform == "twitter":
            return "https://placehold.co/1200x675/1a1a2e/4fc3f7?text=Infographic"
        return "https://placehold.co/1200x1500/1a1a2e/4fc3f7?text=Infographic"

    async def close(self):
        pass
