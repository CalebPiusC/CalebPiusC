#!/usr/bin/env python3
"""
Build all SVG assets for the CalebPiusC profile README.

Change ACCENT below and re-run to update every image:

    python3 scripts/build-assets.py            # reuse downloaded icons
    python3 scripts/build-assets.py --refresh  # re-download icons first

Icons are downloaded from Simple Icons (via api.github.com, falling back to
raw.githubusercontent.com) into assets/icons/ and recoloured to their brand hex.
Nothing is fetched at view time: every generated SVG is self-contained.
"""

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# Single source of truth for the accent colour. Everything else is derived.
# ---------------------------------------------------------------------------
ACCENT = "#C87533"  # copper

# Monochrome palettes (greys only, plus ACCENT used sparingly).
PALETTES = {
    "dark": {
        "bg": "#0D0D0D",
        "fg": "#FFFFFF",
        "muted": "#A8A8A8",
        "faint": "#8C8C8C",
        "border": "#2E2E2E",
        "tile": "#3A3A3A",
    },
    "light": {
        "bg": "#FFFFFF",
        "fg": "#0D0D0D",
        "muted": "#555555",
        "faint": "#6E6E6E",
        "border": "#E3E3E3",
        "tile": "#CFCFCF",
    },
}

# ---------------------------------------------------------------------------
# Brand colours, one entry per technology (Simple Icons brand hex, taken from
# simple-icons data/simple-icons.json). None = no Simple Icons mark exists, so
# the icon row draws a monogram tile instead of borrowing an unrelated logo.
# ---------------------------------------------------------------------------
BRAND = {
    "TypeScript": "#3178C6",
    "Python": "#3776AB",
    "SQL": None,
    "Kotlin": "#7F52FF",
    "JavaScript": "#F7DF1E",
    "HTML": "#E34F26",
    "CSS": "#663399",
    "Next.js": "#000000",
    "React": "#61DAFB",
    "Tailwind CSS": "#06B6D4",
    "shadcn/ui": "#000000",
    "FastAPI": "#009688",
    "Pydantic": "#E92063",
    "asyncpg": None,
    "Redis": "#FF4438",
    "PostgreSQL": "#4169E1",
    "Supabase": "#3FCF8E",
    "Firebase": "#DD2C00",
    "Vitest": "#00FF74",
    "pytest": "#0A9EDC",
    "Playwright": None,
    "Ruff": "#D7FF64",
    "mypy": None,
    "Docker": "#2496ED",
    "GitHub Actions": "#2088FF",
    "Netlify": "#00C7B7",
}

# Monogram text for technologies with no Simple Icons mark.
MONOGRAM = {"SQL": "SQL", "asyncpg": "asyncpg", "Playwright": "PW", "mypy": "mypy"}

# Contact row: X uses the Simple Icons mark, Email is drawn here (not a brand).
CONTACT = [
    ("x", "X profile", "x", "https://x.com/Venom404X", "#000000"),
    ("email", "Email Caleb", None, "mailto:calebpius101@gmail.com", "#000000"),
]

SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS_DIR = ASSETS / "icons"

WIDTH = 880

# ---------------------------------------------------------------------------
# Tech-stack row metrics. These are the knobs for row height and density:
# the row image keeps its 880px width, so the viewBox height alone decides
# how tall the image sits in the README.
# ---------------------------------------------------------------------------
ICON_SIZE = 44        # icon box, in viewBox units (1 unit = 1px at full width)
LABEL_GAP = 8         # vertical gap between the icon box and its text label
ROW_PADDING = 7       # space above each icon box and below each label
LABEL_FONT = 12       # monospace label size; 11-12 keeps 9px+ on tablets
GRID_COLUMNS = 7      # fixed track count so icons align vertically across rows
LABEL_X = 40          # category label
ICONS_X0, ICONS_X1 = 196, 840

# Derived: label baseline, then total row height.
LABEL_BASELINE = ROW_PADDING + ICON_SIZE + LABEL_GAP + round(LABEL_FONT * 0.78)
ROW_HEIGHT = LABEL_BASELINE + 3 + ROW_PADDING

# ---------------------------------------------------------------------------
# Tech stack. slug=None means "no Simple Icons entry" -> text-only tile.
# Verified against simple-icons/simple-icons: sql, asyncpg, playwright and
# mypy have no icon (mysql/sqlite are different products and are NOT used
# as substitutes for SQL). css lives under slug "css" (not "css3").
# ---------------------------------------------------------------------------
STACK = [
    ("LANGUAGES", [
        ("TypeScript", "typescript"),
        ("Python", "python"),
        ("SQL", None),
        ("Kotlin", "kotlin"),
        ("JavaScript", "javascript"),
        ("HTML", "html5"),
        ("CSS", "css"),
    ]),
    ("FRONTEND", [
        ("Next.js", "nextdotjs"),
        ("React", "react"),
        ("Tailwind CSS", "tailwindcss"),
        ("shadcn/ui", "shadcnui"),
    ]),
    ("BACKEND", [
        ("FastAPI", "fastapi"),
        ("Pydantic", "pydantic"),
        ("asyncpg", None),
        ("Redis", "redis"),
    ]),
    ("DATA", [
        ("PostgreSQL", "postgresql"),
        ("Supabase", "supabase"),
        ("Firebase", "firebase"),
    ]),
    ("TESTING", [
        ("Vitest", "vitest"),
        ("pytest", "pytest"),
        ("Playwright", None),
        ("Ruff", "ruff"),
        ("mypy", None),
    ]),
    ("DEVOPS", [
        ("Docker", "docker"),
        ("GitHub Actions", "githubactions"),
        ("Netlify", "netlify"),
    ]),
]

HEADER_LINES = [
    "Hi, I'm Caleb.",
    "Building as VENOM.",
    "Building ORBIT.",
    "Software Engineering @ OAU.",
    "Building toward AI engineering.",
]


def esc(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def write_svg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    size = path.stat().st_size
    status = "OK " if size < 100_000 else "OVER 100KB!"
    print(f"  [{status}] {path.relative_to(ROOT)} ({size} bytes)")
    if size >= 100_000:
        raise SystemExit(f"{path} exceeds 100 KB")


# ---------------------------------------------------------------------------
# Contrast: keep brand colours only where they stay legible against the theme
# background, otherwise fall back to white (dark) / black (light).
# ---------------------------------------------------------------------------

MIN_CONTRAST = 3.0


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(hex_colour: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def themed(brand_hex: str, mode: str) -> str:
    """Brand colour if it clears MIN_CONTRAST on this theme, else white/black."""
    fallback = "#FFFFFF" if mode == "dark" else "#000000"
    if contrast_ratio(brand_hex, PALETTES[mode]["bg"]) >= MIN_CONTRAST:
        return brand_hex
    return fallback


# ---------------------------------------------------------------------------
# Icon download + parsing
# ---------------------------------------------------------------------------

def download_icon(slug: str) -> str:
    """Fetch the original Simple Icons SVG for `slug`."""
    urls = [
        f"https://api.github.com/repos/simple-icons/simple-icons/contents/icons/{slug}.svg",
        f"https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{slug}.svg",
    ]
    last_err = None
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.raw",
                    "User-Agent": "build-assets (profile README)",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - try next mirror
            last_err = exc
    raise RuntimeError(f"could not download icon '{slug}': {last_err}")


def icon_paths(svg_text: str, slug: str) -> list[str]:
    """Extract every <path d="..."> from a Simple Icons SVG."""
    paths = re.findall(r'<path[^>]*\bd="([^"]+)"', svg_text)
    if not paths:
        raise RuntimeError(f"icon '{slug}' has no <path d=...> data")
    # Simple Icons are path-only; fail loudly if that ever changes.
    for tag in ("<circle", "<rect", "<polygon", "<ellipse"):
        if tag in svg_text:
            raise RuntimeError(f"icon '{slug}' uses {tag}, unsupported by builder")
    return paths


def ensure_icons(refresh: bool) -> dict[str, list[str]]:
    """Download originals into assets/icons/ and return {slug: [path d, ...]}."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    cache: dict[str, list[str]] = {}
    for _category, items in STACK:
        for _label, slug in items:
            if slug is None:
                continue
            original = ICONS_DIR / f"{slug}.svg"
            if refresh or not original.exists():
                print(f"  downloading {slug} ...")
                original.write_text(download_icon(slug), encoding="utf-8")
            cache[slug] = icon_paths(original.read_text(encoding="utf-8"), slug)
    # Contact marks that come from Simple Icons.
    for _name, _alt, slug, _href, _hex in CONTACT:
        if slug is None or slug in cache:
            continue
        original = ICONS_DIR / f"{slug}.svg"
        if refresh or not original.exists():
            print(f"  downloading {slug} ...")
            original.write_text(download_icon(slug), encoding="utf-8")
        cache[slug] = icon_paths(original.read_text(encoding="utf-8"), slug)
    return cache


def write_icon_variants(cache: dict[str, list[str]]) -> None:
    """Standalone brand-coloured icons (sources for the row images)."""
    slug_to_label = {slug: label for _c, items in STACK for label, slug in items}
    for slug, paths in cache.items():
        label = slug_to_label.get(slug)
        if label is None:
            continue
        for mode in PALETTES:
            fill = themed(BRAND[label] or "#000000", mode)
            body = "".join(
                f'<path d="{esc(d)}" fill="{fill}"/>' for d in paths
            )
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                f'role="img"><title>{esc(label)}</title>{body}</svg>\n'
            )
            write_svg(ICONS_DIR / f"{slug}-{mode}.svg", svg)


# --- contact icons ---------------------------------------------------------

def email_paths() -> list[str]:
    """A neutral envelope drawn in the same 24x24 box as the brand marks."""
    return [
        "M3 5.75h18a.75.75 0 0 1 .75.75v11a.75.75 0 0 1-.75.75H3a.75.75 0 "
        "0 1-.75-.75v-11A.75.75 0 0 1 3 5.75Z",
        "M3.4 6.6 12 13.1l8.6-6.5",
    ]


def write_contact_icons(cache: dict[str, list[str]]) -> None:
    """28px-ready contact marks; X is the Simple Icons glyph, Email is drawn."""
    for name, _alt, slug, _href, base_hex in CONTACT:
        for mode, pal in PALETTES.items():
            fill = themed(base_hex, mode)
            if slug is not None:
                body = "".join(
                    f'<path d="{esc(d)}" fill="{fill}"/>' for d in cache[slug]
                )
                svg = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                    f'role="img"><title>{esc(name)}</title>{body}</svg>\n'
                )
            else:
                # Outline mark: no fill, stroke only.
                body = "".join(
                    f'<path d="{esc(d)}" fill="none" stroke="{fill}" '
                    f'stroke-width="1.7" stroke-linecap="round" '
                    f'stroke-linejoin="round"/>'
                    for d in email_paths()
                )
                svg = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                    f'role="img"><title>{esc(name)}</title>{body}</svg>\n'
                )
            write_svg(ICONS_DIR / f"{name}-{mode}.svg", svg)


# ---------------------------------------------------------------------------
# 1. Header: animated typing (SMIL) with blinking accent cursor.
#    Fallback: if SMIL is blocked, line 1 is shown as static text.
# ---------------------------------------------------------------------------

def _norm(pairs: list[tuple[float, float]], total: float) -> tuple[str, str]:
    """Turn [(absolute_seconds, value), ...] into (values, keyTimes) strings.

    keyTimes must sit in [0, 1] and increase strictly, so absolute times are
    divided by the total duration, de-duplicated and clamped.
    """
    out_t: list[float] = []
    out_v: list[float] = []
    for t, v in pairs:
        k = min(1.0, max(0.0, round(t / total, 4)))
        if out_t and k <= out_t[-1]:
            if k == out_t[-1]:
                out_v[-1] = v          # same instant: latest value wins
                continue
            k = round(out_t[-1] + 0.0001, 4)
        out_t.append(k)
        out_v.append(v)
    return (";".join(f"{v:g}" for v in out_v),
            ";".join(f"{t:g}" for t in out_t))


def build_header(mode: str, pal: dict) -> str:
    font_size = 32
    char_w = round(font_size * 0.6, 2)   # monospace advance
    x0, y_text = 48, 118
    total = 20.0
    slot = total / len(HEADER_LINES)     # 4.0s per line
    hold = 1.4                           # seconds fully typed before clearing

    clips, texts, cursors = [], [], []
    for i, line in enumerate(HEADER_LINES):
        n = len(line)
        text_w = round(n * char_w, 2)
        type_dur = round(min(n * 0.075, slot - hold - 0.2), 3)
        begin = round(i * slot, 3)

        # --- clip width: one discrete step per character ----------------
        w_pairs: list[tuple[float, float]] = [(0.0, 0.0)]
        for k in range(1, n + 1):
            w_pairs.append((type_dur * k / n, round(k * char_w, 2)))
        w_pairs.append((type_dur + hold, text_w))   # fully typed
        w_pairs.append((slot, 0.0))                 # cleared
        w_pairs.append((total, 0.0))
        width_values, width_times = _norm(w_pairs, total)
        base_width = text_w if i == 0 else 0.0      # static fallback: line 1

        clips.append(
            f'<clipPath id="clip-{i}">'
            f'<rect x="{x0}" y="52" width="{base_width:g}" height="92">'
            f'<animate attributeName="width" values="{width_values}" '
            f'keyTimes="{width_times}" calcMode="discrete" dur="{total:g}s" '
            f'begin="{begin:g}s" repeatCount="indefinite"/>'
            f"</rect></clipPath>"
        )
        texts.append(
            f'<text x="{x0}" y="{y_text}" font-family="{MONO}" '
            f'font-size="{font_size}" fill="{pal["fg"]}" '
            f'textLength="{text_w:g}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#clip-{i})">{esc(line)}</text>'
        )

        # --- cursor: advances with each character, blinks, then hides ---
        end_x = round(x0 + text_w + 4, 2)
        x_pairs: list[tuple[float, float]] = [(0.0, x0)]
        for k in range(1, n + 1):
            x_pairs.append((type_dur * k / n, round(x0 + k * char_w + 4, 2)))
        x_pairs.append((type_dur + hold, end_x))
        x_pairs.append((slot, x0))
        x_pairs.append((total, x0))
        x_values, x_times = _norm(x_pairs, total)

        # Keep the cursor alive (blinking) for the whole hold, until the
        # line is cleared at the end of its slot.
        blink_until = slot - 0.25
        o_pairs: list[tuple[float, float]] = [(0.0, 1.0), (type_dur, 1.0)]
        t, on = type_dur, False
        while t + 0.5 < blink_until:
            t = round(t + 0.5, 3)
            o_pairs.append((t, 1.0 if on else 0.0))
            on = not on
        o_pairs.append((blink_until, 1.0))
        o_pairs.append((slot, 0.0))
        o_pairs.append((total, 0.0))
        o_values, o_times = _norm(o_pairs, total)

        base_opacity = 1.0 if i == 0 else 0.0
        base_x = end_x if i == 0 else x0
        cursors.append(
            f'<rect x="{base_x:g}" y="84" width="3" height="40" fill="{ACCENT}" '
            f'opacity="{base_opacity:g}">'
            f'<animate attributeName="x" values="{x_values}" keyTimes="{x_times}" '
            f'calcMode="discrete" dur="{total:g}s" begin="{begin:g}s" '
            f'repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="{o_values}" '
            f'keyTimes="{o_times}" calcMode="discrete" dur="{total:g}s" '
            f'begin="{begin:g}s" repeatCount="indefinite"/>'
            f"</rect>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} 200" '
        f'width="{WIDTH}" height="200" role="img">'
        f"<title>{esc(' '.join(HEADER_LINES))}</title>"
        # No background: the SVG sits on the viewer's page colour, so there
        # is no visible plate edge in either GitHub theme.
        + "".join(clips)
        + "".join(texts)
        + "".join(cursors)
        # Thin accent rule (one of the few accent uses).
        + f'<rect x="48" y="152" width="64" height="2" fill="{ACCENT}"/>'
        + "</svg>\n"
    )


# ---------------------------------------------------------------------------
# 2. ORBIT card
# ---------------------------------------------------------------------------

def build_orbit_card(mode: str, pal: dict) -> str:
    # (number, name, tag, current, note) — note is set inline after the name so
    # no text measurement is needed (font metrics differ across platforms).
    steps = [
        ("1", "CLI core", "← current", True, ""),
        ("2", "Newcomer track", "", False,
         "(one-line install, doctor command, guided first run)"),
        ("3", "Graphical frontend", "", False, ""),
        ("4", "Figma and other integrations", "", False, ""),
    ]
    step_rows = []
    y = 262
    for num, name, tag, current, note in steps:
        color = pal["fg"] if current else pal["muted"]
        weight = "600" if current else "400"
        tspans = ""
        if tag:
            tspans += (
                f'<tspan font-family="{MONO}" font-size="13" dx="14" '
                f'fill="{pal["fg"]}">{esc(tag)}</tspan>'
            )
        if note:
            tspans += (
                f'<tspan font-family="{SANS}" font-size="14" dx="10" '
                f'fill="{pal["faint"]}">{esc(note)}</tspan>'
            )
        step_rows.append(
            f'<text x="40" y="{y}" font-family="{MONO}" font-size="14" '
            f'fill="{color}">{num}</text>'
            f'<text x="72" y="{y}" font-family="{SANS}" font-size="16" '
            f'font-weight="{weight}" fill="{color}">{esc(name)}{tspans}</text>'
        )
        y += 30

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} 392" '
        f'width="{WIDTH}" height="392" role="img">'
        "<title>ORBIT — open-source, cloud-based coding agent. Status: in progress.</title>"
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="391" rx="16" '
        f'fill="{pal["bg"]}" stroke="{pal["border"]}" stroke-width="1"/>'
        # Title + status (accent dot).
        f'<text x="40" y="66" font-family="{SANS}" font-size="36" '
        f'font-weight="700" letter-spacing="2" fill="{pal["fg"]}">ORBIT</text>'
        f'<circle cx="716" cy="58" r="5" fill="{ACCENT}"/>'
        f'<text x="730" y="63" font-family="{MONO}" font-size="13" '
        f'letter-spacing="2" fill="{pal["fg"]}">IN PROGRESS</text>'
        # Thin accent rule under the title.
        f'<rect x="40" y="84" width="64" height="2" fill="{ACCENT}"/>'
        # Description; the single highlighted word is "command".
        f'<text x="40" y="124" font-family="{SANS}" font-size="17" '
        f'fill="{pal["fg"]}">Open-source, cloud-based coding agent for people '
        f"moving to the</text>"
        f'<text x="40" y="150" font-family="{SANS}" font-size="17" '
        f'fill="{pal["fg"]}"><tspan fill="{ACCENT}">command</tspan> line.</text>'
        # Meta line.
        f'<text x="40" y="186" font-family="{MONO}" font-size="13" '
        f'fill="{pal["muted"]}">Forked from opencode  |  Base model: Gemini  |  '
        f"CLI first</text>"
        f'<line x1="40" y1="210" x2="840" y2="210" stroke="{pal["border"]}" '
        f'stroke-width="1"/>'
        f'<text x="40" y="238" font-family="{MONO}" font-size="12" '
        f'letter-spacing="3" fill="{pal["faint"]}">ROADMAP</text>'
        + "".join(step_rows)
        + "</svg>\n"
    )


# ---------------------------------------------------------------------------
# 3. Tech-stack rows (icons embedded as paths; text-only tiles where needed)
# ---------------------------------------------------------------------------

def build_stack_row(category: str, items: list, mode: str, pal: dict,
                    cache: dict[str, list[str]]) -> str:
    """One category row on a fixed GRID_COLUMNS track, so columns line up."""
    cell_w = (ICONS_X1 - ICONS_X0) / GRID_COLUMNS
    label_y = LABEL_BASELINE
    cells = []
    for idx, (label, slug) in enumerate(items):
        center = ICONS_X0 + (idx + 0.5) * cell_w
        caption = (
            f'<text x="{center:g}" y="{label_y}" text-anchor="middle" '
            f'font-family="{MONO}" font-size="{LABEL_FONT}" '
            f'fill="{pal["muted"]}">{esc(label)}</text>'
        )
        if slug is not None:
            fill = themed(BRAND[label], mode)
            paths = "".join(f'<path d="{esc(d)}" fill="{fill}"/>'
                            for d in cache[slug])
            scale = ICON_SIZE / 24
            tx = center - ICON_SIZE / 2
            cells.append(
                f'<g transform="translate({tx:g} {ROW_PADDING}) scale({scale:g})">'
                f"{paths}</g>" + caption
            )
        else:
            # No Simple Icons mark exists: a monogram tile in the same box and
            # weight as the real icons. Never an empty tile, never a stand-in.
            text = MONOGRAM[label]
            tile_w = max(ICON_SIZE, round(len(text) * 7.8 + 18))
            cells.append(
                f'<rect x="{center - tile_w / 2:g}" y="{ROW_PADDING}" '
                f'width="{tile_w}" height="{ICON_SIZE}" rx="10" '
                f'fill="none" stroke="{pal["tile"]}" stroke-width="1.2"/>'
                f'<text x="{center:g}" '
                f'y="{ROW_PADDING + ICON_SIZE / 2 + 4.5:g}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="13" '
                f'fill="{pal["fg"]}">{esc(text)}</text>' + caption
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {ROW_HEIGHT}" '
        f'width="{WIDTH}" height="{ROW_HEIGHT}" role="img">'
        f"<title>{esc(category.title())}: "
        f"{esc(', '.join(label for label, _ in items))}</title>"
        # Accent rule + category label, vertically centred on the icon band.
        f'<rect x="{LABEL_X}" y="{round(ROW_HEIGHT / 2 - 13)}" width="20" '
        f'height="2" fill="{ACCENT}"/>'
        f'<text x="{LABEL_X}" y="{round(ROW_HEIGHT / 2 + 5)}" '
        f'font-family="{MONO}" font-size="13" letter-spacing="2" '
        f'fill="{pal["faint"]}">{esc(category)}</text>'
        + "".join(cells)
        + "</svg>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="re-download Simple Icons originals")
    args = parser.parse_args()

    print(f"Accent: {ACCENT}")
    print("Icons:")
    cache = ensure_icons(args.refresh)
    print("Icon variants:")
    write_icon_variants(cache)

    print("Header:")
    for mode, pal in PALETTES.items():
        write_svg(ASSETS / f"header-{mode}.svg", build_header(mode, pal))

    print("ORBIT card:")
    for mode, pal in PALETTES.items():
        write_svg(ASSETS / f"orbit-card-{mode}.svg", build_orbit_card(mode, pal))

    print("Contact icons:")
    write_contact_icons(cache)

    print("Tech-stack rows:")
    for category, items in STACK:
        slug_cat = category.lower()
        for mode, pal in PALETTES.items():
            write_svg(
                ASSETS / f"stack-{slug_cat}-{mode}.svg",
                build_stack_row(category, items, mode, pal, cache),
            )

    print(f"\nRow metrics: height={ROW_HEIGHT} viewBox units "
          f"(was 120), icon={ICON_SIZE}, label={LABEL_FONT}px, "
          f"grid={GRID_COLUMNS} columns")
    print("\nBrand colour check (contrast vs background, 3:1 minimum):")
    for _c, items in STACK:
        for label, slug in items:
            if slug is None:
                continue
            row = []
            for mode in ("dark", "light"):
                brand = BRAND[label]
                ratio = contrast_ratio(brand, PALETTES[mode]["bg"])
                used = themed(brand, mode)
                flag = brand if used == brand else f"{used} (fallback)"
                row.append(f"{mode}: {ratio:.2f}:1 -> {flag}")
            print(f"  {label:15} {brand}  " + "  |  ".join(row))

    text_only = [label for _c, items in STACK for label, slug in items
                 if slug is None]
    print(f"\nDone. Monogram tiles (no Simple Icons mark): {', '.join(text_only)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
