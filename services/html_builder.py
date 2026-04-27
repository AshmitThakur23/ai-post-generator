"""
Zone D — AI-Powered Animated HTML Builder
==========================================
Generates high-quality infographic HTML with deterministic local templates.
Gemini HTML generation is optional and disabled by default for better text reliability.
"""

import base64
import hashlib
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
GENERATED_IMAGES_DIR = os.path.join(BASE_DIR, "generated_images")
os.makedirs(TEMP_DIR, exist_ok=True)

PLATFORM_SIZES = {
    "linkedin": {"width": 1200, "height": 1500},
    "instagram": {"width": 1080, "height": 1080},
    "twitter": {"width": 1200, "height": 675},
    "default": {"width": 1200, "height": 1500},
}

GEMINI_TIMEOUT = 75.0


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _strip_code_fences(text: str) -> str:
    """Strip markdown fences from AI HTML output."""
    value = (text or "").strip()
    pattern = r"```(?:html)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, value, re.DOTALL)
    if match:
        return match.group(1).strip()
    return value


class HTMLBuilder:
    """Builds animated HTML infographics."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key
        self.gemini_model = "gemini-3.1-flash-lite-preview"
        if gemini_api_key:
            logger.info("HTMLBuilder initialized with Gemini support (local templates are default)")
        else:
            logger.info("HTMLBuilder initialized (local template mode)")

    async def build_animated_html(
        self,
        content: Dict[str, Any],
        image_path: str = "",
        template: Optional[Dict] = None,
        tweaks: Optional[Dict] = None,
        platform: str = "linkedin",
    ) -> str:
        """Build animated HTML for preview/render and return temp/output.html path."""
        tweaks = tweaks or {}
        template = template or {}
        size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["default"])

        title = tweaks.get("title") or content.get("title", "Infographic")
        sections = tweaks.get("sections") or content.get("sections", [])
        hashtags = content.get("hashtags", [])
        category = content.get("category", "Tech")
        caption = content.get("caption", "")
        resolved_image_src = self._resolve_image_source(image_path)

        use_gemini_template = bool(tweaks.get("useGeminiTemplate", False))

        html = None
        if self.gemini_api_key and use_gemini_template:
            try:
                html = await self._generate_with_gemini(
                    title=title,
                    sections=sections,
                    hashtags=hashtags,
                    category=category,
                    caption=caption,
                    image_url=image_path,
                    has_hero_image=bool(resolved_image_src),
                    platform=platform,
                    width=size["width"],
                    height=size["height"],
                    template=template,
                    tweaks=tweaks,
                )
                if html and resolved_image_src:
                    html = self._inject_hero_image_source(html, resolved_image_src)
                if html and "<html" in html.lower():
                    logger.info("Gemini generated HTML (%d bytes)", len(html))
                else:
                    html = None
            except Exception as error:
                logger.warning("Gemini HTML generation failed: %s", str(error))
                html = None

        if not html:
            html = self._build_local_html(
                title=title,
                sections=sections,
                hashtags=hashtags,
                category=category,
                caption=caption,
                image_src=resolved_image_src,
                platform=platform,
                size=size,
                tweaks=tweaks,
                template=template,
            )
            logger.info("Local pro template generated (%d bytes)", len(html))

        output_path = os.path.join(TEMP_DIR, "output.html")
        with open(output_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(html)

        logger.info("HTML saved: %s (%sx%s)", output_path, size["width"], size["height"])
        return output_path

    async def _generate_with_gemini(
        self,
        title,
        sections,
        hashtags,
        category,
        caption,
        image_url,
        has_hero_image,
        platform,
        width,
        height,
        template,
        tweaks,
    ) -> Optional[str]:
        """Generate complete HTML with Gemini when explicitly requested."""
        sections_text = ""
        for index, sec in enumerate(sections):
            heading = sec.get("heading", f"Section {index + 1}") if isinstance(sec, dict) else str(sec)
            content = sec.get("content", "") if isinstance(sec, dict) else ""
            sections_text += f"\n  Section {index + 1}: \"{heading}\"\n    Content: \"{content[:200]}\"\n"

        hashtag_str = " ".join(hashtags[:8])
        template_style = (template or {}).get("style", "clean")
        template_layout = (template or {}).get("layout", "flow")

        prompt = f"""You are an expert frontend developer. Generate a COMPLETE, self-contained HTML file for a {platform} infographic post.

REQUIREMENTS:
- Exact dimensions: {width}px wide, {height}px tall
- Topic: "{title}"
- Category: {category}
- Caption: "{caption[:150]}"
- Template style hint: {template_style}
- Template layout hint: {template_layout}
- The infographic MUST include these sections:{sections_text}
- Hashtags: {hashtag_str}
- Image URL for hero section: {image_url or 'none'}

DESIGN RULES:
1. Use Google Fonts only.
2. Premium architecture/agentic workflow visual language.
3. Strong spacing and hierarchy, no clipping, no overlap.
4. Keep all visible text correctly spelled and meaningful.
5. Never output gibberish labels or random characters.
6. Include 5+ connected process steps and section cards.
7. Include subtle CSS animation for connectors/cards.
8. Use CSS variables: --bg-color, --text-color, --accent-color, --accent2-color.
9. Body must have exact size and overflow hidden.
10. No JavaScript, no markdown fences, HTML only.

HERO IMAGE RULE:
- If image exists ({'yes' if has_hero_image else 'no'}), include one hero image area.
- Use exact placeholder __HERO_IMAGE__ for src.

{"CUSTOM COLORS: bg=" + tweaks.get("bgColor", "") + " accent=" + tweaks.get("accentColor", "") + " text=" + tweaks.get("textColor", "") if any(tweaks.get(k) for k in ["bgColor", "accentColor", "textColor"]) else ""}

Return ONLY full HTML starting with <!DOCTYPE html>."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.45,
                "maxOutputTokens": 8192,
            },
        }

        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return None

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return None

        html = _strip_code_fences(text)
        if "<!DOCTYPE" not in html.upper() and "<html" not in html.lower():
            return None

        return html

    def _build_local_html(
        self,
        title,
        sections,
        hashtags,
        category,
        caption,
        image_src,
        platform,
        size,
        tweaks,
        template,
    ) -> str:
        """Build deterministic local templates for high-quality readable output."""
        bg_color = tweaks.get("bgColor", "#0a0f1f")
        text_color = tweaks.get("textColor", "#e9f0ff")
        accent_color = tweaks.get("accentColor", "#4fc3f7")
        accent2_color = tweaks.get("accent2Color", "#45d0a4")
        card_bg = tweaks.get("cardBg", "#121a2f")

        width, height = size["width"], size["height"]
        compact = height < 1000
        max_sections = 4 if compact else 6
        grid_cols = 2 if compact else 3
        pattern_cols = 4 if compact else 5
        split_hub_width = 130 if compact else 180
        title_size = 30 if compact else 42
        subtitle_size = 12 if compact else 15
        layout_padding = 12 if compact else 22

        prepared_sections = self._prepare_sections(sections, max_sections=max_sections)
        layout_hint = str((template or {}).get("layout", "") or "").lower()
        style_hint = str((template or {}).get("style", "") or "").lower()
        variant = self._pick_local_variant(title, layout_hint, style_hint)

        if variant == "levels-grid":
            body_layout = self._build_levels_grid_layout(prepared_sections)
        elif variant == "split-architecture":
            body_layout = self._build_split_architecture_layout(prepared_sections)
        else:
            body_layout = self._build_pattern_columns_layout(prepared_sections, target_columns=pattern_cols)
        bottom_matrix = self._build_bottom_matrix(prepared_sections, compact=compact)

        workflow_lane = self._build_workflow_lane(prepared_sections)
        mesh_svg = self._build_mesh_svg(width, height, accent_color, accent2_color)
        tags_html = " ".join(f'<span class="tag">{_esc(tag)}</span>' for tag in hashtags[:8])

        title_clean = self._normalize_heading(title, max_len=78)
        caption_clean = self._normalize_sentence(caption, max_len=210)
        category_clean = self._normalize_heading(category, max_len=24)

        backdrop_block = ""
        if image_src:
            backdrop_block = f"""
  <div class=\"backdrop-image\" aria-hidden=\"true\">
    <img src=\"{_esc(image_src)}\" alt=\"\" />
  </div>"""

        return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

  :root {{
    --bg-color: {bg_color};
    --text-color: {text_color};
    --accent-color: {accent_color};
    --accent2-color: {accent2_color};
    --card-bg: {card_bg};
    --muted-text: #9fb0cf;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    width: {width}px;
    height: {height}px;
    background: var(--bg-color);
    color: var(--text-color);
    font-family: 'Manrope', sans-serif;
    overflow: hidden;
    position: relative;
  }}

  .bg-gradient {{
    position: absolute;
    inset: 0;
    background:
      radial-gradient(1200px 600px at 80% -5%, rgba(79, 195, 247, 0.2), transparent 60%),
      radial-gradient(900px 520px at 15% 98%, rgba(69, 208, 164, 0.18), transparent 62%),
      linear-gradient(165deg, #060b17 0%, #0a1225 52%, #070c1a 100%);
    z-index: 0;
  }}

  .backdrop-image {{
    position: absolute;
    inset: 0;
    z-index: 0;
    opacity: 0.12;
    pointer-events: none;
  }}

  .backdrop-image img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: blur(18px) contrast(1.08) saturate(0.8);
    transform: scale(1.06);
  }}

  .backdrop-vignette {{
    position: absolute;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    background:
      radial-gradient(circle at center, transparent 35%, rgba(2, 6, 14, 0.38) 80%),
      linear-gradient(180deg, rgba(5, 10, 20, 0.1), rgba(5, 10, 20, 0.48));
  }}

  .mesh-svg {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 2;
    pointer-events: none;
    opacity: 0.72;
  }}

  @keyframes flowPath {{
    to {{ stroke-dashoffset: -64; }}
  }}

  .mesh-line {{
    fill: none;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-dasharray: 9 6;
    animation: flowPath 3.2s linear infinite;
  }}

  .mesh-node {{
    filter: drop-shadow(0 0 5px rgba(79, 195, 247, 0.8));
  }}

  .canvas {{
    position: relative;
    z-index: 3;
    width: 100%;
    height: 100%;
    padding: {34 if compact else 46}px {26 if compact else 44}px {22 if compact else 34}px;
    display: grid;
    grid-template-rows: auto auto 1fr auto;
    gap: {12 if compact else 18}px;
  }}

  .kicker {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #e6f7ff;
    background: linear-gradient(120deg, rgba(79, 195, 247, 0.24), rgba(69, 208, 164, 0.22));
    border: 1px solid rgba(133, 188, 255, 0.26);
    margin-bottom: 10px;
  }}

  .title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: {title_size}px;
    line-height: 1.08;
    letter-spacing: -0.02em;
    margin-bottom: 8px;
    max-width: 94%;
  }}

  .subtitle {{
    font-size: {subtitle_size}px;
    color: var(--muted-text);
    max-width: 92%;
    line-height: 1.45;
  }}

  .workflow-lane {{
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
  }}

  .wf-step {{
    background: rgba(17, 27, 47, 0.88);
    border: 1px solid rgba(122, 161, 238, 0.3);
    color: #deebff;
    padding: 8px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    max-width: {130 if compact else 170}px;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .wf-arrow {{
    color: rgba(157, 207, 255, 0.8);
    font-size: 14px;
  }}

  .layout-wrap {{
    position: relative;
    border-radius: 18px;
    border: 1px solid rgba(122, 157, 227, 0.22);
    background: linear-gradient(180deg, rgba(10, 18, 35, 0.78), rgba(8, 15, 28, 0.86));
    box-shadow: 0 12px 32px rgba(2, 8, 20, 0.45);
    padding: {layout_padding}px;
    overflow: hidden;
    height: 100%;
    min-height: 0;
    display: grid;
    grid-template-rows: minmax(0, 1fr) auto;
    gap: {8 if compact else 12}px;
  }}

  .layout-top {{
    display: flex;
    min-height: 0;
  }}

  .layout-top > * {{
    flex: 1 1 auto;
    min-height: 0;
  }}

  .layout-bottom {{
    display: grid;
    grid-template-columns: repeat({2 if compact else 3}, minmax(0, 1fr));
    gap: 8px;
  }}

  .insight-card {{
    border: 1px solid rgba(109, 152, 228, 0.24);
    background: rgba(11, 20, 36, 0.72);
    border-radius: 10px;
    padding: 8px 9px;
    display: grid;
    gap: 4px;
  }}

  .insight-card .label {{
    font-size: 10px;
    font-weight: 700;
    color: #9ec6ff;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .insight-card .value {{
    font-size: {10 if compact else 11}px;
    line-height: 1.3;
    color: #c7dbff;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}

  .layout-wrap::after {{
    content: "";
    position: absolute;
    left: 12px;
    right: 12px;
    top: 10px;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(130, 175, 255, 0.42), transparent);
  }}

  .pattern-columns {{
    display: grid;
    grid-template-columns: repeat({pattern_cols}, minmax(0, 1fr));
    gap: 10px;
    align-items: stretch;
    height: 100%;
  }}

  .pattern-col,
  .level-card,
  .split-card {{
    border-radius: 12px;
    background: rgba(16, 26, 44, 0.82);
    border: 1px solid rgba(116, 158, 240, 0.26);
    padding: {9 if compact else 12}px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    animation: lift 4.2s ease-in-out infinite;
  }}

  .pattern-col {{
    height: 100%;
  }}

  .pattern-col:nth-child(odd),
  .level-card:nth-child(odd),
  .split-card:nth-child(odd) {{
    border-color: rgba(79, 195, 247, 0.34);
  }}

  .pattern-col:nth-child(even),
  .level-card:nth-child(even),
  .split-card:nth-child(even) {{
    border-color: rgba(69, 208, 164, 0.32);
  }}

  .col-head {{
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 28px;
  }}

  .col-num {{
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 800;
    color: #031426;
    background: linear-gradient(135deg, var(--accent-color), var(--accent2-color));
    flex-shrink: 0;
  }}

  .col-title,
  .level-title,
  .split-title {{
    font-size: {11 if compact else 12}px;
    font-weight: 800;
    line-height: 1.2;
    color: #ecf4ff;
  }}

  .point-list {{
    display: grid;
    gap: 6px;
  }}

  .mid-track {{
    margin-top: 4px;
    flex: 1;
    min-height: {120 if compact else 180}px;
    display: grid;
    align-content: center;
    gap: 6px;
  }}

  .mid-node {{
    font-size: {10 if compact else 11}px;
    line-height: 1.2;
    color: #d1e5ff;
    border: 1px solid rgba(115, 170, 245, 0.24);
    border-radius: 8px;
    padding: 6px 7px;
    background: linear-gradient(135deg, rgba(22, 33, 58, 0.88), rgba(13, 24, 44, 0.82));
    text-align: center;
  }}

  .mid-link {{
    width: 2px;
    height: {10 if compact else 12}px;
    margin: 0 auto;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(79, 195, 247, 0.85), rgba(69, 208, 164, 0.4));
  }}

  .mini-stack {{
    margin-top: 4px;
    display: grid;
    gap: 6px;
    margin-top: auto;
  }}

  .mini-node {{
    font-size: {10 if compact else 11}px;
    line-height: 1.2;
    color: #c9dcff;
    border: 1px dashed rgba(123, 170, 247, 0.28);
    border-radius: 8px;
    padding: 6px 7px;
    background: rgba(12, 21, 38, 0.52);
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .mini-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent-color), var(--accent2-color));
    flex-shrink: 0;
  }}

  .point-item,
  .split-point {{
    font-size: {10 if compact else 11}px;
    line-height: 1.34;
    color: #afc4e7;
    background: rgba(11, 19, 34, 0.78);
    border: 1px solid rgba(110, 144, 211, 0.2);
    border-radius: 8px;
    padding: 6px 7px;
    display: -webkit-box;
    -webkit-line-clamp: {2 if compact else 3};
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}

  .levels-grid {{
    display: grid;
    grid-template-columns: repeat({grid_cols}, minmax(0, 1fr));
    gap: 10px;
    height: 100%;
  }}

  .level-chip {{
    justify-self: start;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.03em;
    color: #052035;
    background: linear-gradient(135deg, rgba(79, 195, 247, 0.95), rgba(69, 208, 164, 0.95));
    border-radius: 999px;
    padding: 3px 9px;
  }}

  .split-layout {{
    display: grid;
    grid-template-columns: 1fr {split_hub_width}px 1fr;
    gap: 10px;
    height: 100%;
  }}

  .split-col {{
    display: grid;
    gap: 8px;
  }}

  .split-hub {{
    border-radius: 14px;
    border: 1px solid rgba(142, 187, 255, 0.34);
    background: radial-gradient(circle at center, rgba(79, 195, 247, 0.16), rgba(9, 17, 32, 0.88) 72%);
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 10px;
    font-size: {11 if compact else 13}px;
    font-weight: 800;
    color: #dff1ff;
    letter-spacing: 0.01em;
  }}

  .footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    border-top: 1px solid rgba(120, 160, 240, 0.2);
    padding-top: 10px;
  }}

  .tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}

  .tag {{
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 700;
    color: #d8e8ff;
    background: rgba(15, 27, 48, 0.84);
    border: 1px solid rgba(118, 154, 225, 0.24);
  }}

  .credit {{
    font-size: 11px;
    color: #95a8c7;
    white-space: nowrap;
  }}

  @keyframes lift {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-3px); }}
  }}

  .pattern-col:nth-child(2),
  .level-card:nth-child(2),
  .split-card:nth-child(2) {{ animation-delay: 0.25s; }}

  .pattern-col:nth-child(3),
  .level-card:nth-child(3),
  .split-card:nth-child(3) {{ animation-delay: 0.5s; }}

  .pattern-col:nth-child(4),
  .level-card:nth-child(4),
  .split-card:nth-child(4) {{ animation-delay: 0.75s; }}

  .pattern-col:nth-child(5),
  .level-card:nth-child(5),
  .split-card:nth-child(5) {{ animation-delay: 1s; }}
</style>
</head>
<body>
  <div class=\"bg-gradient\"></div>
  {backdrop_block}
  <div class=\"backdrop-vignette\"></div>
  {mesh_svg}

  <main class=\"canvas\">
    <header>
      <div class=\"kicker\">{_esc(category_clean)} • Template: {variant}</div>
      <h1 class=\"title\">{_esc(title_clean)}</h1>
      {f'<p class="subtitle">{_esc(caption_clean)}</p>' if caption_clean else ''}
    </header>

    <section class=\"workflow-lane\">{workflow_lane}</section>

    <section class=\"layout-wrap\">
      <div class=\"layout-top\">{body_layout}</div>
      {bottom_matrix}
    </section>

    <footer class=\"footer\">
      <div class=\"tags\">{tags_html}</div>
      <div class=\"credit\">Generated by AI Content Pipeline</div>
    </footer>
  </main>
</body>
</html>"""

    def _pick_local_variant(self, title: str, layout_hint: str, style_hint: str) -> str:
        text = (title or "").lower()
        layout = (layout_hint or "").lower()
        style = (style_hint or "").lower()

        if any(word in text for word in ["vs", "versus", "compare", "comparison"]):
            return "split-architecture"
        if layout in {"grid", "matrix", "list"}:
            return "levels-grid"
        if layout in {"thread", "carousel", "flow"}:
            return "pattern-columns"
        if style in {"minimal", "light"}:
            return "levels-grid"

        digest = hashlib.sha256(f"{title}|{layout_hint}|{style_hint}".encode("utf-8")).hexdigest()
        return ["pattern-columns", "levels-grid", "split-architecture"][int(digest[:2], 16) % 3]

    def _prepare_sections(self, sections: List[Dict[str, Any]], max_sections: int = 5) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []

        for idx, section in enumerate((sections or [])[:max_sections]):
            heading_raw = section.get("heading", f"Section {idx + 1}") if isinstance(section, dict) else str(section)
            content_raw = section.get("content", "") if isinstance(section, dict) else ""
            points_raw = section.get("points", []) if isinstance(section, dict) else []

            heading = self._normalize_heading(heading_raw, max_len=34)
            content = self._normalize_sentence(content_raw, max_len=320)

            points: List[str] = []
            for item in (points_raw or [])[:4]:
                cleaned = self._normalize_sentence(item, max_len=82)
                if cleaned:
                    points.append(cleaned)

            if not points and content:
                sentences = re.split(r"(?<=[.!?])\s+", content)
                for sentence in sentences[:4]:
                    cleaned = self._normalize_sentence(sentence, max_len=84)
                    if cleaned:
                        points.append(cleaned)

            if not points:
                points = ["Actionable insight", "Clear workflow", "Measurable outcome"]

            prepared.append(
                {
                    "heading": heading or f"Section {idx + 1}",
                    "content": content,
                    "points": points[:3],
                }
            )

        if not prepared:
            prepared = [
                {
                    "heading": "Context",
                    "content": "Define the problem and constraints.",
                    "points": ["Problem scope", "Success metric", "Primary risks"],
                },
                {
                    "heading": "Approach",
                    "content": "Design the architecture and key workflow.",
                    "points": ["Data flow", "Control logic", "Validation step"],
                },
                {
                    "heading": "Execution",
                    "content": "Deliver with observability and iteration.",
                    "points": ["Deploy safely", "Track performance", "Improve continuously"],
                },
            ]

        return prepared

    def _build_workflow_lane(self, sections: List[Dict[str, Any]]) -> str:
        labels: List[str] = []
        for section in (sections or [])[:6]:
            heading = self._normalize_heading(section.get("heading", "Step"), max_len=20)
            labels.append(heading or "Step")

        if not labels:
            labels = ["Ingest", "Plan", "Build", "Validate", "Deliver"]

        parts: List[str] = []
        for index, label in enumerate(labels):
            parts.append(f'<span class="wf-step">{_esc(label)}</span>')
            if index < len(labels) - 1:
                parts.append('<span class="wf-arrow">→</span>')
        return "".join(parts)

    def _build_pattern_columns_layout(self, sections: List[Dict[str, Any]], target_columns: int = 5) -> str:
        columns = sections[:target_columns]
        while len(columns) < target_columns:
            columns.append({"heading": f"Stage {len(columns) + 1}", "points": ["Plan", "Build", "Measure"]})

        blocks: List[str] = []
        for idx, section in enumerate(columns, start=1):
            point_html = "".join(
                f'<div class="point-item">{_esc(point)}</div>'
                for point in section.get("points", [])[:3]
            )
            mid_steps = self._section_mid_nodes(section, idx)
            mid_track_parts: List[str] = []
            for mid_index, step in enumerate(mid_steps):
                mid_track_parts.append(f'<div class="mid-node">{_esc(step)}</div>')
                if mid_index < len(mid_steps) - 1:
                    mid_track_parts.append('<div class="mid-link"></div>')
            mid_track = "".join(mid_track_parts)

            micro_steps = self._section_micro_steps(section, idx)
            mini_stack = "".join(
                f'<div class="mini-node"><span class="mini-dot"></span>{_esc(step)}</div>'
                for step in micro_steps
            )
            blocks.append(
                f'''<article class="pattern-col">
  <div class="col-head"><span class="col-num">{idx}</span><div class="col-title">{_esc(section.get("heading", f"Stage {idx}"))}</div></div>
  <div class="point-list">{point_html}</div>
  <div class="mid-track">{mid_track}</div>
  <div class="mini-stack">{mini_stack}</div>
</article>'''
            )
        return f'<div class="pattern-columns">{"".join(blocks)}</div>'

    def _section_mid_nodes(self, section: Dict[str, Any], index: int) -> List[str]:
        """Create central ladder nodes to visually fill the poster body."""
        heading = self._normalize_heading(section.get("heading", "Stage"), max_len=24)

        presets = [
            ["Intent", "Routing", "Execution", "Validation"],
            ["Input", "Tool Match", "Run", "Review"],
            ["Scope", "Plan", "Build", "Verify"],
            ["Signals", "Reason", "Act", "Feedback"],
            ["Collect", "Process", "Ship", "Optimize"],
        ]

        if heading:
            stem = heading.split(" ")[0]
            if len(stem) >= 4:
                return [
                    f"{stem} Plan",
                    f"{stem} Execute",
                    f"{stem} Validate",
                    f"{stem} Optimize",
                ]

        return presets[(index - 1) % len(presets)]

    def _section_micro_steps(self, section: Dict[str, Any], index: int) -> List[str]:
        """Create short deterministic micro-flow labels for dense design-pattern visuals."""
        heading = self._normalize_heading(section.get("heading", "Stage"), max_len=24)

        presets = [
            ["Intent Intake", "Context Parse", "Policy Check", "Action Output", "Feedback Merge", "Metrics Log"],
            ["Task Routing", "Tool Match", "Execution", "Quality Gate", "Fallback Path", "Result Trace"],
            ["Plan Draft", "Dependency Check", "Step Dispatch", "Status Sync", "Risk Review", "Outcome Confirm"],
            ["Reasoning Loop", "Action Trigger", "Evidence Log", "Result Review", "Guardrail Scan", "Iteration Lock"],
            ["Signal Collect", "Anomaly Scan", "Feedback Merge", "Continuous Improve", "Alert Routing", "Audit Trail"],
        ]

        if heading:
            first = heading.split(" ")[0]
            custom = [
                f"{first} Input",
                f"{first} Validation",
                f"{first} Execution",
                f"{first} Outcome",
                f"{first} Feedback",
                f"{first} Metrics",
            ]
            if len(first) >= 4:
                return custom

        return presets[(index - 1) % len(presets)]

    def _build_levels_grid_layout(self, sections: List[Dict[str, Any]]) -> str:
        cards = sections[:6]
        blocks: List[str] = []
        for idx, section in enumerate(cards, start=1):
            point_html = "".join(
                f'<div class="point-item">{_esc(point)}</div>'
                for point in section.get("points", [])[:2]
            )
            blocks.append(
                f'''<article class="level-card">
  <span class="level-chip">Level {idx}</span>
  <div class="level-title">{_esc(section.get("heading", f"Level {idx}"))}</div>
  <div class="point-list">{point_html}</div>
</article>'''
            )
        return f'<div class="levels-grid">{"".join(blocks)}</div>'

    def _build_bottom_matrix(self, sections: List[Dict[str, Any]], compact: bool) -> str:
        cards: List[str] = []
        max_cards = 4 if compact else 6

        for section in sections[:max_cards]:
            heading = self._normalize_heading(section.get("heading", "Insight"), max_len=18)
            points = section.get("points", [])
            value = points[1] if len(points) > 1 else (points[0] if points else "Actionable recommendation")
            value = self._normalize_sentence(value, max_len=84)
            cards.append(
                f'''<article class="insight-card">
  <div class="label">{_esc(heading)}</div>
  <div class="value">{_esc(value)}</div>
</article>'''
            )

        if not cards:
            return ""

        return f'<div class="layout-bottom">{"".join(cards)}</div>'

    def _build_split_architecture_layout(self, sections: List[Dict[str, Any]]) -> str:
        left = sections[::2][:3]
        right = sections[1::2][:3]

        def col_html(entries: List[Dict[str, Any]], start_num: int) -> str:
            cards: List[str] = []
            for index, section in enumerate(entries, start=start_num):
                first_point = section.get("points", ["Actionable recommendation"])[0]
                cards.append(
                    f'''<article class="split-card">
  <div class="col-head"><span class="col-num">{index}</span><div class="split-title">{_esc(section.get("heading", f"Module {index}"))}</div></div>
  <div class="split-point">{_esc(first_point)}</div>
</article>'''
                )
            return "".join(cards)

        left_html = col_html(left, 1)
        right_html = col_html(right, len(left) + 1)

        return f'''<div class="split-layout">
  <div class="split-col">{left_html}</div>
  <div class="split-hub">Unified<br/>Agentic Workflow<br/>Control Plane</div>
  <div class="split-col">{right_html}</div>
</div>'''

    def _build_mesh_svg(self, width: int, height: int, accent: str, accent2: str) -> str:
        y1 = int(height * 0.33)
        y2 = int(height * 0.58)
        y3 = int(height * 0.79)
        return f'''<svg class="mesh-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">
  <path class="mesh-line" d="M 70 {y1} C {int(width*0.32)} {int(y1-90)}, {int(width*0.68)} {int(y1+90)}, {width-70} {y1}" stroke="{accent}" />
  <path class="mesh-line" d="M 80 {y2} C {int(width*0.31)} {int(y2+110)}, {int(width*0.69)} {int(y2-110)}, {width-80} {y2}" stroke="{accent2}" style="animation-duration:3.8s" />
  <path class="mesh-line" d="M 110 {y3} C {int(width*0.35)} {int(y3-80)}, {int(width*0.65)} {int(y3+80)}, {width-110} {y3}" stroke="{accent}" style="animation-duration:4.4s" />
  <circle class="mesh-node" cx="{int(width*0.22)}" cy="{y1}" r="4" fill="{accent}" />
  <circle class="mesh-node" cx="{int(width*0.5)}" cy="{y2}" r="5" fill="{accent2}" />
  <circle class="mesh-node" cx="{int(width*0.78)}" cy="{y1}" r="4" fill="{accent}" />
</svg>'''

    def _normalize_heading(self, value: Any, max_len: int = 40) -> str:
        text = " ".join(str(value or "").split())
        text = re.sub(r"[^A-Za-z0-9\s\-:/&+()]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        if len(text) > max_len:
            text = text[:max_len].rstrip() + "..."
        return text

    def _normalize_sentence(self, value: Any, max_len: int = 160) -> str:
        text = " ".join(str(value or "").split())
        text = re.sub(r"[^A-Za-z0-9\s\-:/&+(),.%!?]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        if len(text) > max_len:
            text = text[:max_len].rstrip() + "..."
        return text

    def _resolve_image_source(self, image_path: str) -> str:
        """Resolve image input to a browser-safe source string."""
        value = (image_path or "").strip()
        if not value:
            return ""

        if value.startswith("data:image/"):
            return value

        if value.startswith("http://") or value.startswith("https://"):
            return value

        candidates: List[str] = []

        if value.startswith("/api/v1/serve-image/") or value.startswith("/api/v1/serve-file/"):
            filename = value.rsplit("/", 1)[-1]
            candidates.append(os.path.join(GENERATED_IMAGES_DIR, filename))
            candidates.append(os.path.join(TEMP_DIR, filename))

        if os.path.isabs(value):
            candidates.append(value)
        else:
            candidates.append(os.path.join(BASE_DIR, value.lstrip("/\\")))
            candidates.append(os.path.join(TEMP_DIR, os.path.basename(value)))
            candidates.append(os.path.join(GENERATED_IMAGES_DIR, os.path.basename(value)))

        mime_by_ext = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }

        for candidate in candidates:
            if not candidate or not os.path.isfile(candidate):
                continue
            ext = os.path.splitext(candidate)[1].lower()
            mime = mime_by_ext.get(ext, "image/png")
            with open(candidate, "rb") as file_handle:
                encoded = base64.b64encode(file_handle.read()).decode("ascii")
            return f"data:{mime};base64,{encoded}"

        return value

    def _inject_hero_image_source(self, html: str, image_src: str) -> str:
        """Inject resolved hero image source into generated HTML output."""
        if not html or not image_src:
            return html

        safe_src = _esc(image_src)

        if "__HERO_IMAGE__" in html:
            return html.replace("__HERO_IMAGE__", safe_src)

        def _replace_first_img(match: re.Match) -> str:
            return f"{match.group(1)}{safe_src}{match.group(3)}"

        updated = re.sub(
            r'(<img[^>]*\bsrc=["\'])([^"\']*)(["\'])',
            _replace_first_img,
            html,
            count=1,
            flags=re.IGNORECASE,
        )
        if updated != html:
            return updated

        hero_markup = (
            f'<div class="hero-image" style="width:100%;height:36%;overflow:hidden;position:relative;">'
            f'<img src="{safe_src}" alt="Infographic" '
            f'style="width:100%;height:100%;object-fit:cover;display:block;" />'
            f'<div style="position:absolute;inset:auto 0 0 0;height:96px;'
            f'background:linear-gradient(transparent, rgba(0,0,0,0.65));"></div></div>'
        )
        return re.sub(r"(<body[^>]*>)", rf"\1\n{hero_markup}", html, count=1, flags=re.IGNORECASE)


def apply_tweaks(html_content: str, tweaks: Dict[str, Any]) -> str:
    """Apply tweak values by replacing CSS variable values and title text."""
    replacements = {
        "bgColor": "--bg-color",
        "textColor": "--text-color",
        "accentColor": "--accent-color",
        "accent2Color": "--accent2-color",
        "cardBg": "--card-bg",
    }

    result = html_content
    for tweak_key, css_var in replacements.items():
        if tweak_key in tweaks:
            pattern = rf"({css_var}:\s*)([^;]+)(;)"
            replacement = rf"\g<1>{tweaks[tweak_key]}\3"
            result = re.sub(pattern, replacement, result)

    if "title" in tweaks:
        result = re.sub(
            r'(<h1 class="title">)(.*?)(</h1>)',
            rf"\1{_esc(tweaks['title'])}\3",
            result,
        )

    return result
