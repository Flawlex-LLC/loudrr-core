"""
Image generation utilities for Telegram bot.
Premium glossy black card with golden accents, halftone texture, and shine effect.
"""
import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
import os


def get_font(size: int, bold: bool = False, syne: bool = False):
    """Get font for cards. Syne for brand text, Space Grotesk for content."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(script_dir, "fonts")

    if syne:
        # Syne Bold for brand text (matches landing page)
        font_paths = [
            os.path.join(fonts_dir, "Syne-Bold.ttf"),
            os.path.join(fonts_dir, "SpaceGrotesk-Bold.ttf"),  # Fallback
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    elif bold:
        font_paths = [
            os.path.join(fonts_dir, "SpaceGrotesk-Bold.ttf"),
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        font_paths = [
            os.path.join(fonts_dir, "SpaceGrotesk-Regular.ttf"),
            os.path.join(fonts_dir, "SpaceGrotesk-Bold.ttf"),  # Fallback to bold if no regular
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


# Font Awesome 6 icon SVG paths (for reference) and rendering
FA_ICONS = {
    # X-Twitter (brands) - viewBox 0 0 512 512
    "x-logo": {
        "viewBox": (0, 0, 512, 512),
        "path": "M389.2 48h70.6L305.6 224.2 487 464H345L233.7 318.6 106.5 464H35.8L200.7 275.5 26.8 48H172.4L272.9 180.9 389.2 48zM364.4 421.8h39.1L151.1 88h-42L364.4 421.8z"
    },
    # Bolt (solid) - viewBox 0 0 448 512
    "lightning-bolt": {
        "viewBox": (0, 0, 448, 512),
        "path": "M349.4 44.6c5.9-13.7 1.5-29.7-10.6-38.5s-28.6-8-39.9 1.8l-256 224c-10 8.8-13.6 22.9-8.9 35.3S50.7 288 64 288H175.5L98.6 467.4c-5.9 13.7-1.5 29.7 10.6 38.5s28.6 8 39.9-1.8l256-224c10-8.8 13.6-22.9 8.9-35.3s-16.6-20.7-30-20.7H272.5L349.4 44.6z"
    }
}


def load_icon(name: str, size: int = 20, color: tuple = None, rounded: bool = False, radius: int = 4) -> Image:
    """Load icon from assets folder, resize, tint, and optionally round corners."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "assets", "icons", f"{name}.png")

    if not os.path.exists(icon_path):
        raise FileNotFoundError(f"Icon not found: {icon_path}")

    icon = Image.open(icon_path).convert("RGBA")
    icon = icon.resize((size, size), Image.LANCZOS)

    if color:
        # Tint the icon to the specified color
        r, g, b = color
        pixels = icon.load()
        for y in range(icon.height):
            for x in range(icon.width):
                pr, pg, pb, pa = pixels[x, y]
                if pa > 0:
                    pixels[x, y] = (r, g, b, pa)

    if rounded:
        # Create rounded corner mask
        mask = Image.new('L', (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
        # Apply mask to alpha channel
        icon.putalpha(ImageChops.multiply(icon.split()[3], mask))

    return icon


def create_halftone_texture(width: int, height: int, dot_spacing: int = 8, max_alpha: int = 25) -> Image:
    """Create a halftone dot pattern texture."""
    texture = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(texture)

    for y in range(0, height, dot_spacing):
        offset = (dot_spacing // 2) if (y // dot_spacing) % 2 else 0
        for x in range(offset, width, dot_spacing):
            dist_from_center = math.sqrt((x - width/2)**2 + (y - height/2)**2)
            max_dist = math.sqrt((width/2)**2 + (height/2)**2)

            size_factor = 1 - (dist_from_center / max_dist) * 0.5
            dot_radius = int(1.5 * size_factor)

            alpha = int(max_alpha * (0.5 + 0.5 * size_factor))

            if dot_radius > 0:
                draw.ellipse(
                    [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                    fill=(255, 255, 255, alpha)
                )

    return texture


def create_glossy_shine(width: int, height: int, card_rect: tuple) -> Image:
    """Create a diagonal glossy shine effect across the card."""
    shine = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shine)

    x1, y1, x2, y2 = card_rect
    card_w = x2 - x1

    shine_width = card_w * 0.4

    for i in range(int(shine_width)):
        progress = i / shine_width
        intensity = math.exp(-((progress - 0.5) ** 2) / 0.08)
        alpha = int(40 * intensity)

        if alpha > 0:
            start_x = x1 + i
            start_y = y1
            end_x = x1 + i - (y2 - y1) * 0.3
            end_y = y2

            draw.line([(start_x, start_y), (end_x, end_y)],
                     fill=(255, 255, 255, alpha), width=2)

    shine = shine.filter(ImageFilter.GaussianBlur(radius=8))
    return shine


def draw_progress_ring(draw: ImageDraw, center: tuple, radius: int, progress: float,
                       bg_color: tuple, fg_color: tuple, width: int = 8):
    """Draw a circular progress indicator."""
    x, y = center
    bbox = [x - radius, y - radius, x + radius, y + radius]

    draw.arc(bbox, 0, 360, fill=bg_color, width=width)

    if progress > 0:
        end_angle = int(360 * min(progress, 1.0)) - 90
        draw.arc(bbox, -90, end_angle, fill=fg_color, width=width)


def create_rounded_mask(width: int, height: int, radius: int) -> Image:
    """Create a rounded rectangle mask."""
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, width, height], radius=radius, fill=255)
    return mask


def create_gradient_array(height: int, width: int) -> np.ndarray:
    """Create gradient array from white-gold to gold (same as 156)."""
    gradient = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        t = y / height if height > 0 else 0
        # Top: near white (255, 245, 200) -> Bottom: gold (212, 175, 55)
        r = int(255 - t * 43)
        g = int(245 - t * 70)
        b = int(200 - t * 145)
        gradient[y, :] = [r, g, b, 255]
    return gradient


def draw_gradient_text(img: Image, pos: tuple, text: str, font, draw: ImageDraw) -> Image:
    """Draw text with white-gold to gold gradient."""
    x, y = int(pos[0]), int(pos[1])
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3]  # Use full height including descenders
    padding = 10

    # Create text layer with extra space for descenders
    layer_w = text_w + padding * 2
    layer_h = text_h + padding * 2
    text_layer = Image.new('RGBA', (layer_w, layer_h), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text((padding, padding), text, fill=(255, 255, 255, 255), font=font)

    # Create gradient
    gradient = create_gradient_array(layer_h, layer_w)
    grad_img = Image.fromarray(gradient, 'RGBA')
    grad_img.putalpha(text_layer.split()[3])

    # Paste onto image
    img.paste(grad_img, (x - padding, y - padding), grad_img)
    return img


def apply_gradient_to_icon(icon: Image) -> Image:
    """Apply white-gold to gold gradient to an icon."""
    size = icon.size[0]
    gradient = create_gradient_array(size, size)
    grad_img = Image.fromarray(gradient, 'RGBA')
    grad_img.putalpha(icon.split()[3])
    return grad_img


def create_balance_card(
    credits: int,
    daily_earned: int,
    daily_cap: int,
    streak: int,
    tier: str,
    multiplier: float = 1.0,
    telegram_username: str = "",
    x_username: str = ""  # X/Twitter username
) -> io.BytesIO:
    """Create a premium glossy balance card with proper rounded corners."""

    # Credit card aspect ratio at high resolution
    width, height = 1012, 638
    margin = 32
    corner_radius = 32

    # Colors - True gold palette (not yellow)
    gold_bright = (212, 175, 55)      # Classic gold
    gold = (180, 145, 50)             # Medium gold
    gold_dark = (140, 110, 40)        # Dark gold
    gold_dim = (100, 80, 35)          # Very dark gold
    white = (255, 255, 255)
    white_soft = (220, 220, 225)
    card_bg = (12, 12, 14)

    tier_colors = {
        "bronze": (180, 120, 60),
        "silver": (170, 175, 185),
        "gold": gold_bright,
        "platinum": (200, 220, 240),
    }
    tier_color = tier_colors.get(tier.lower(), tier_colors["bronze"])

    # === BACKGROUND: Very dark gold to black gradient ===
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    for y in range(height):
        progress = y / height
        # Even darker gold at top, fading to pure black
        r = int(15 * (1 - progress))
        g = int(10 * (1 - progress))
        b = int(2 * (1 - progress))
        for x in range(width):
            img.putpixel((x, y), (r, g, b, 255))

    # === HALFTONE DOTS ON BACKGROUND ===
    bg_halftone = create_halftone_texture(width, height, dot_spacing=10, max_alpha=12)
    img = Image.alpha_composite(img, bg_halftone)

    # === GOLDEN GLOW around card area ===
    card_rect = (margin, margin, width - margin, height - margin)
    card_w = card_rect[2] - card_rect[0]
    card_h = card_rect[3] - card_rect[1]

    glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for i in range(25, 0, -1):
        alpha = int(20 * (1 - i / 25))
        expand = i * 2
        glow_draw.rounded_rectangle(
            [margin - expand, margin - expand,
             width - margin + expand, height - margin + expand],
            radius=corner_radius + i,
            fill=(255, 160, 30, alpha)
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    img = Image.alpha_composite(img, glow)

    # === CREATE CARD WITH PROPER ROUNDED CORNERS ===
    # Create card content on separate image - pure black base
    card_img = Image.new('RGBA', (card_w, card_h), (12, 12, 14, 255))
    card_draw = ImageDraw.Draw(card_img)

    # === SUBTLE GOLD GRADIENT OVERLAY ===
    glossy_layer = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    glossy_draw = ImageDraw.Draw(glossy_layer)

    # Create subtle gold tint gradient - darker gold at edges, slight gold highlight
    for y in range(card_h):
        for x in range(card_w):
            # Distance from center for vignette effect
            cx, cy = card_w / 2, card_h / 2
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            max_dist = math.sqrt(cx**2 + cy**2)
            vignette = dist / max_dist

            # Subtle gold tint that's stronger at edges (vignette)
            gold_r = int(35 * vignette)
            gold_g = int(25 * vignette)
            gold_b = int(5 * vignette)
            glossy_layer.putpixel((x, y), (gold_r, gold_g, gold_b, int(80 * vignette)))

    # Blur for smooth blend
    glossy_layer = glossy_layer.filter(ImageFilter.GaussianBlur(radius=40))

    # Composite onto card
    card_img = Image.alpha_composite(card_img, glossy_layer)

    # === HALFTONE TEXTURE ===
    halftone = create_halftone_texture(card_w, card_h, dot_spacing=6, max_alpha=15)
    card_img = Image.alpha_composite(card_img, halftone)

    # === GLOSSY SHINE (gold tinted) ===
    shine = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)

    shine_width = card_w * 0.35
    for i in range(int(shine_width)):
        progress = i / shine_width
        intensity = math.exp(-((progress - 0.5) ** 2) / 0.06)
        alpha = int(45 * intensity)
        if alpha > 0:
            # Gold-tinted shine
            shine_draw.line([(i, 0), (i - card_h * 0.25, card_h)],
                           fill=(255, 220, 150, alpha), width=2)

    shine = shine.filter(ImageFilter.GaussianBlur(radius=10))
    card_img = Image.alpha_composite(card_img, shine)

    # === APPLY ROUNDED MASK TO CARD ===
    card_mask = create_rounded_mask(card_w, card_h, corner_radius)
    card_img.putalpha(card_mask)

    # === PASTE CARD ONTO MAIN IMAGE ===
    img.paste(card_img, (margin, margin), card_img)

    # === DRAW CONTENT ===
    draw = ImageDraw.Draw(img)

    # Sleek dark gold border - 1px thin, very subtle
    draw.rounded_rectangle(card_rect, radius=corner_radius, outline=(70, 55, 20), width=1)

    # === FONTS ===
    font_brand = get_font(32, bold=True)
    font_user = get_font(28)
    font_amount = get_font(96, bold=True)
    font_currency = get_font(32)
    font_stat_value = get_font(36, bold=True)
    font_stat_label = get_font(20)
    font_hint = get_font(18)

    # === CONTENT AREA ===
    left_x = margin + 48
    right_edge = width - margin - 48

    # Row 1: Profile + Username on LEFT, ECHO brand on RIGHT
    row1_y = margin + 40


    # Profile and usernames section
    if telegram_username:
        # Profile circle (on left) - sized to match height of social lines
        profile_size = 72
        profile_x = left_x
        profile_y = row1_y - 10

        # Draw gold ring for profile
        draw.ellipse(
            [profile_x, profile_y, profile_x + profile_size, profile_y + profile_size],
            outline=gold_bright, width=2
        )
        # Inner circle (darker)
        draw.ellipse(
            [profile_x + 4, profile_y + 4, profile_x + profile_size - 4, profile_y + profile_size - 4],
            fill=gold_dim
        )
        # User initial (from telegram username) with gradient
        display_name = telegram_username
        initial = display_name[0].upper()
        init_font = get_font(32, bold=True)
        init_bbox = draw.textbbox((0, 0), initial, font=init_font)
        init_w = init_bbox[2] - init_bbox[0]
        init_h = init_bbox[3] - init_bbox[1]
        init_top_offset = init_bbox[1]  # Font's top padding

        # Center horizontally and vertically (accounting for font offset)
        init_x = profile_x + profile_size // 2 - init_w // 2
        init_y = profile_y + profile_size // 2 - init_h // 2 - init_top_offset
        img = draw_gradient_text(img, (init_x, init_y), initial, init_font, draw)
        draw = ImageDraw.Draw(img)

        # Usernames text positioning
        text_x = profile_x + profile_size + 16
        font_social = get_font(16)  # Same size for all platforms
        icon_size = 20              # Bigger icons, equal for all
        line_gap = 4

        # Calculate total height for centering
        lines = []
        if telegram_username:
            lines.append(("tg", f"@{telegram_username}"))
        if x_username:
            lines.append(("x", f"@{x_username}"))

        # Calculate line height (icon or text, whichever is taller)
        text_h = draw.textbbox((0, 0), "@test", font=font_social)[3]
        line_h = max(icon_size, text_h)

        total_h = line_h * len(lines) + line_gap * (len(lines) - 1) if lines else 0

        # Start position to center all lines with profile
        current_y = profile_y + (profile_size - total_h) // 2

        for platform, text in lines:
            # Vertically center icon and text within line
            icon_y = current_y + (line_h - icon_size) // 2
            text_y = current_y + (line_h - text_h) // 2

            if platform == "tg":
                tg_icon = load_icon("telegram", size=icon_size, color=(255, 255, 255), rounded=True, radius=4)
                tg_icon = apply_gradient_to_icon(tg_icon)
                img.paste(tg_icon, (text_x, icon_y), tg_icon)
                img = draw_gradient_text(img, (text_x + icon_size + 8, text_y), text, font_social, draw)
                draw = ImageDraw.Draw(img)
            elif platform == "x":
                x_icon = load_icon("x-logo", size=icon_size, color=(255, 255, 255), rounded=True, radius=4)
                x_icon = apply_gradient_to_icon(x_icon)
                img.paste(x_icon, (text_x, icon_y), x_icon)
                img = draw_gradient_text(img, (text_x + icon_size + 8, text_y), text, font_social, draw)
                draw = ImageDraw.Draw(img)

            current_y += line_h + line_gap

    # Loudrr brand on right (with actual logo icon + Syne font)
    font_brand = get_font(36, bold=True, syne=True)
    brand_text = "Loudrr"

    # Get brand text dimensions
    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_text_w = brand_bbox[2] - brand_bbox[0]
    brand_text_h = brand_bbox[3] - brand_bbox[1]

    # Icon size matches landing page proportions
    icon_size = 44
    icon_gap = 10

    # Calculate total brand width (icon + gap + text)
    total_brand_w = icon_size + icon_gap + brand_text_w

    # Position brand block on right
    brand_x = right_edge - total_brand_w
    brand_y = row1_y - 4

    # Load and paste Loudrr logo icon with gradient
    try:
        loudrr_icon = load_icon("loudrr-icon", size=icon_size)
        icon_y = brand_y - (icon_size - brand_text_h) // 2 + 4
        img.paste(loudrr_icon, (brand_x, icon_y), loudrr_icon)
        draw = ImageDraw.Draw(img)
    except Exception:
        pass

    # Draw loudrr text with gradient
    text_x = brand_x + icon_size + icon_gap
    img = draw_gradient_text(img, (text_x, brand_y), brand_text, font_brand, draw)
    draw = ImageDraw.Draw(img)

    # Row 2: Main balance with golden glow blend effect
    row2_y = row1_y + 80
    amount_text = f"{credits:,}"

    # Create golden glow layer for amount
    glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    # Multiple glow layers for rich golden glow
    for i in range(12, 0, -2):
        alpha = int(25 * (1 - i / 12))
        glow_draw.text((left_x, row2_y), amount_text,
                       fill=(180, 140, 50, alpha), font=font_amount)

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=15))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # Create gradient text for 156 - white-gold at top to gold at bottom
    # Get text dimensions relative to origin for accurate sizing
    amount_bbox = draw.textbbox((0, 0), amount_text, font=font_amount)
    text_w = amount_bbox[2] - amount_bbox[0]
    text_h = amount_bbox[3]  # Full height from top to bottom baseline
    padding = 20

    # Create text layer for masking - extra padding to ensure full coverage
    layer_w = text_w + padding * 2
    layer_h = text_h + padding * 2
    text_layer = Image.new('RGBA', (layer_w, layer_h), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text((padding, padding), amount_text, fill=(255, 255, 255, 255), font=font_amount)

    # Create smooth vertical gradient using numpy
    gradient_array = np.zeros((layer_h, layer_w, 4), dtype=np.uint8)

    for y in range(layer_h):
        t = y / layer_h  # 0.0 at top, 1.0 at bottom
        # Top: near white (255, 245, 200) -> Bottom: gold (212, 175, 55)
        r = int(255 - t * 43)    # 255 -> 212
        g = int(245 - t * 70)    # 245 -> 175
        b = int(200 - t * 145)   # 200 -> 55
        gradient_array[y, :] = [r, g, b, 255]

    gradient = Image.fromarray(gradient_array, 'RGBA')

    # Apply text as mask to gradient
    gradient.putalpha(text_layer.split()[3])

    # Paste onto main image
    img.paste(gradient, (left_x - padding, row2_y - padding), gradient)
    draw = ImageDraw.Draw(img)

    # "karma" tag below 156 with icon - using gradient colors
    amount_bbox = draw.textbbox((0, 0), amount_text, font=font_amount)
    amount_w = amount_bbox[2] - amount_bbox[0]

    # Use actual visual bottom of the text (not just height)
    karma_y = row2_y + amount_bbox[3] + 10  # Reduced gap between 156 and KARMA
    karma_font = get_font(22, bold=True)
    karma_text = "KARMA"

    # Tag background
    bolt_icon_size = 20
    tag_padding_x = 12
    tag_padding_y = 10
    tag_radius = 12  # Increased radius for smoother corners

    # Get text metrics for proper centering
    karma_bbox = draw.textbbox((0, 0), karma_text, font=karma_font)
    karma_text_w = karma_bbox[2] - karma_bbox[0]
    karma_text_h = karma_bbox[3] - karma_bbox[1]
    karma_text_top = karma_bbox[1]  # Font's top padding offset

    # Use the taller of icon or text as inner height
    tag_inner_h = max(bolt_icon_size, karma_text_h)

    tag_left = left_x
    tag_top = karma_y
    tag_right = left_x + bolt_icon_size + 8 + karma_text_w + tag_padding_x * 2
    tag_bottom = karma_y + tag_inner_h + tag_padding_y * 2
    tag_w = tag_right - tag_left
    tag_h = tag_bottom - tag_top

    # Draw tag background with outline matching lightest gradient color
    gradient_light = (255, 245, 200)  # Top of gradient (near white-gold)
    draw.rounded_rectangle(
        [tag_left, tag_top, tag_right, tag_bottom],
        radius=tag_radius, fill=(35, 30, 18), outline=gradient_light, width=1
    )

    # Calculate center line of the tag content area
    tag_center_y = tag_top + tag_padding_y + (tag_inner_h // 2)

    # Lightning bolt icon with gradient (same as 156)
    bolt_icon = load_icon("lightning-bolt", size=bolt_icon_size, color=(255, 255, 255))
    icon_x = tag_left + tag_padding_x
    icon_y = tag_center_y - (bolt_icon_size // 2)

    # Create gradient for bolt icon - white-gold to gold (same as 156)
    bolt_gradient = np.zeros((bolt_icon_size, bolt_icon_size, 4), dtype=np.uint8)
    for y in range(bolt_icon_size):
        t = y / bolt_icon_size
        # Top: near white (255, 245, 200) -> Bottom: gold (212, 175, 55)
        r = int(255 - t * 43)
        g = int(245 - t * 70)
        b = int(200 - t * 145)
        bolt_gradient[y, :] = [r, g, b, 255]

    bolt_grad_img = Image.fromarray(bolt_gradient, 'RGBA')
    bolt_grad_img.putalpha(bolt_icon.split()[3])
    img.paste(bolt_grad_img, (icon_x, icon_y), bolt_grad_img)
    draw = ImageDraw.Draw(img)

    # KARMA text with gradient (same as 156)
    text_y = tag_center_y - (karma_text_h // 2) - karma_text_top
    karma_x = icon_x + bolt_icon_size + 8

    # Create text layer for KARMA
    karma_layer = Image.new('RGBA', (karma_text_w + 10, karma_text_h + 10), (0, 0, 0, 0))
    karma_draw = ImageDraw.Draw(karma_layer)
    karma_draw.text((0, 0), karma_text, fill=(255, 255, 255, 255), font=karma_font)

    # Create gradient for KARMA text - white-gold to gold (same as 156)
    karma_gradient = np.zeros((karma_text_h + 10, karma_text_w + 10, 4), dtype=np.uint8)
    for y in range(karma_text_h + 10):
        t = y / (karma_text_h + 10)
        # Top: near white (255, 245, 200) -> Bottom: gold (212, 175, 55)
        r = int(255 - t * 43)
        g = int(245 - t * 70)
        b = int(200 - t * 145)
        karma_gradient[y, :] = [r, g, b, 255]

    karma_grad_img = Image.fromarray(karma_gradient, 'RGBA')
    karma_grad_img.putalpha(karma_layer.split()[3])
    img.paste(karma_grad_img, (karma_x, text_y), karma_grad_img)
    draw = ImageDraw.Draw(img)

    # === CIRCULAR PROGRESS (true gold) ===
    ring_x = right_edge - 80
    ring_y = row2_y + 55
    ring_radius = 58
    progress = min(daily_earned / daily_cap, 1.0) if daily_cap > 0 else 0

    # True gold progress ring (not yellow)
    draw_progress_ring(draw, (ring_x, ring_y), ring_radius, progress,
                       bg_color=(50, 42, 25), fg_color=gold_bright, width=10)

    # Percentage in gold - properly centered
    pct_text = f"{int(progress * 100)}%"
    pct_font = get_font(26, bold=True)

    # Use textbbox with anchor for proper centering
    pct_bbox = draw.textbbox((0, 0), pct_text, font=pct_font)
    pct_w = pct_bbox[2] - pct_bbox[0]
    pct_h = pct_bbox[3] - pct_bbox[1]

    # Calculate true center position - percentage with gradient
    pct_x = ring_x - pct_w // 2
    pct_y = ring_y - pct_h // 2 - (pct_bbox[1])  # Adjust for font ascent
    img = draw_gradient_text(img, (pct_x, pct_y), pct_text, pct_font, draw)
    draw = ImageDraw.Draw(img)

    # "Daily" label with gradient
    daily_bbox = draw.textbbox((0, 0), "Daily", font=font_hint)
    daily_w = daily_bbox[2] - daily_bbox[0]
    img = draw_gradient_text(img, (ring_x - daily_w // 2, ring_y + ring_radius + 14), "Daily", font_hint, draw)
    draw = ImageDraw.Draw(img)

    # === DIVIDER (gradient light color) ===
    divider_y = height - margin - 140
    gradient_light = (255, 245, 200)  # Top of gradient
    draw.line([(left_x, divider_y), (right_edge, divider_y)], fill=gradient_light, width=2)

    # === STATS ROW ===
    stats_y = divider_y + 24
    stat_spacing = (right_edge - left_x) // 3

    # Streak with gradient
    img = draw_gradient_text(img, (left_x, stats_y), "STREAK", font_stat_label, draw)
    draw = ImageDraw.Draw(img)
    streak_val = f"{streak}d" if streak > 0 else "0d"
    img = draw_gradient_text(img, (left_x, stats_y + 28), streak_val, font_stat_value, draw)
    draw = ImageDraw.Draw(img)

    # Tier with gradient
    tier_x = left_x + stat_spacing
    img = draw_gradient_text(img, (tier_x, stats_y), "TIER", font_stat_label, draw)
    draw = ImageDraw.Draw(img)
    img = draw_gradient_text(img, (tier_x, stats_y + 28), tier.upper(), font_stat_value, draw)
    draw = ImageDraw.Draw(img)

    # Today with gradient
    today_x = left_x + stat_spacing * 2
    img = draw_gradient_text(img, (today_x, stats_y), "TODAY", font_stat_label, draw)
    draw = ImageDraw.Draw(img)
    img = draw_gradient_text(img, (today_x, stats_y + 28), f"+{daily_earned}", font_stat_value, draw)
    draw = ImageDraw.Draw(img)

    # === FOOTER with gradient ===
    footer_y = height - margin - 36
    img = draw_gradient_text(img, (left_x, footer_y), "Engage to earn  •  Promote to grow", font_hint, draw)
    draw = ImageDraw.Draw(img)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)

    return output


def create_orange_gradient_array(height: int, width: int) -> np.ndarray:
    """Create gradient array for orange brand color: light orange -> orange -> dark orange."""
    gradient = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        t = y / height if height > 0 else 0
        # Top: light orange (255, 149, 0) -> Bottom: dark orange (204, 85, 0)
        r = int(255 - t * 51)   # 255 -> 204
        g = int(149 - t * 64)   # 149 -> 85
        b = int(0)              # stays 0
        gradient[y, :] = [r, g, b, 255]
    return gradient


def draw_orange_gradient_text(img: Image, pos: tuple, text: str, font, draw: ImageDraw) -> Image:
    """Draw text with orange gradient (light orange to dark orange)."""
    x, y = int(pos[0]), int(pos[1])
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3]
    padding = 10

    # Create text layer
    layer_w = text_w + padding * 2
    layer_h = text_h + padding * 2
    text_layer = Image.new('RGBA', (layer_w, layer_h), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text((padding, padding), text, fill=(255, 255, 255, 255), font=font)

    # Create gradient
    gradient = create_orange_gradient_array(layer_h, layer_w)
    grad_img = Image.fromarray(gradient, 'RGBA')
    grad_img.putalpha(text_layer.split()[3])

    # Paste onto image
    img.paste(grad_img, (x - padding, y - padding), grad_img)
    return img


def apply_orange_gradient_to_icon(icon: Image) -> Image:
    """Apply orange gradient to an icon."""
    size = icon.size[0]
    gradient = create_orange_gradient_array(size, size)
    grad_img = Image.fromarray(gradient, 'RGBA')
    grad_img.putalpha(icon.split()[3])
    return grad_img


def format_followers(count: int) -> str:
    """Format follower count for display (e.g., 12.5K, 1.2M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def download_avatar(url: str, size: int = 80) -> Image:
    """Download and process avatar from URL, return circular masked image."""
    import httpx

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()

            avatar = Image.open(io.BytesIO(response.content)).convert("RGBA")
            avatar = avatar.resize((size, size), Image.LANCZOS)

            # Create circular mask
            mask = Image.new('L', (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, size, size], fill=255)
            avatar.putalpha(mask)

            return avatar
    except Exception:
        return None


def create_waitlist_card(
    x_username: str,
    display_name: str = None,
    followers_count: int = None,
    avatar_url: str = None,
    is_verified: bool = False,
    telegram_username: str = None,
) -> io.BytesIO:
    """
    Create waitlist confirmation card with glassmorphism design.

    Premium design matching the mini app's Magic UI style.
    Orange brand color (#f95400) with glass effects.
    Shows personalized X profile data and Telegram username.
    """
    # Credit card aspect ratio at high resolution (same as balance card)
    width, height = 1012, 638
    margin = 32
    corner_radius = 32

    # Colors - Brand orange palette (matching mini app)
    orange = (249, 84, 0)           # #f95400 - brand primary
    white = (255, 255, 255)
    gray = (120, 120, 125)
    twitter_blue = (29, 161, 242)   # Twitter/X verified blue

    # === BACKGROUND: Very dark with subtle orange tint ===
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    for y in range(height):
        progress = y / height
        r = int(12 * (1 - progress))
        g = int(6 * (1 - progress))
        b = int(2 * (1 - progress))
        for x in range(width):
            img.putpixel((x, y), (r, g, b, 255))

    # === HALFTONE DOTS ON BACKGROUND ===
    bg_halftone = create_halftone_texture(width, height, dot_spacing=10, max_alpha=10)
    img = Image.alpha_composite(img, bg_halftone)

    # === ORANGE GLOW around card area ===
    card_rect = (margin, margin, width - margin, height - margin)
    card_w = card_rect[2] - card_rect[0]
    card_h = card_rect[3] - card_rect[1]

    glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for i in range(25, 0, -1):
        alpha = int(18 * (1 - i / 25))
        expand = i * 2
        glow_draw.rounded_rectangle(
            [margin - expand, margin - expand,
             width - margin + expand, height - margin + expand],
            radius=corner_radius + i,
            fill=(249, 84, 0, alpha)
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    img = Image.alpha_composite(img, glow)

    # === CREATE CARD WITH GLASSMORPHISM ===
    card_img = Image.new('RGBA', (card_w, card_h), (12, 12, 14, 255))

    # === SUBTLE ORANGE GRADIENT OVERLAY (glassmorphism tint) ===
    glossy_layer = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    for y in range(card_h):
        for x in range(card_w):
            cx, cy = card_w / 2, card_h / 2
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            max_dist = math.sqrt(cx**2 + cy**2)
            vignette = dist / max_dist
            orange_r = int(30 * vignette)
            orange_g = int(12 * vignette)
            orange_b = int(2 * vignette)
            glossy_layer.putpixel((x, y), (orange_r, orange_g, orange_b, int(70 * vignette)))

    glossy_layer = glossy_layer.filter(ImageFilter.GaussianBlur(radius=40))
    card_img = Image.alpha_composite(card_img, glossy_layer)

    # === HALFTONE TEXTURE ===
    halftone = create_halftone_texture(card_w, card_h, dot_spacing=6, max_alpha=12)
    card_img = Image.alpha_composite(card_img, halftone)

    # === GLOSSY SHINE (orange tinted) ===
    shine = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)
    shine_width = card_w * 0.35
    for i in range(int(shine_width)):
        progress = i / shine_width
        intensity = math.exp(-((progress - 0.5) ** 2) / 0.06)
        alpha = int(40 * intensity)
        if alpha > 0:
            shine_draw.line([(i, 0), (i - card_h * 0.25, card_h)],
                           fill=(255, 180, 100, alpha), width=2)
    shine = shine.filter(ImageFilter.GaussianBlur(radius=10))
    card_img = Image.alpha_composite(card_img, shine)

    # === APPLY ROUNDED MASK TO CARD ===
    card_mask = create_rounded_mask(card_w, card_h, corner_radius)
    card_img.putalpha(card_mask)

    # === PASTE CARD ONTO MAIN IMAGE ===
    img.paste(card_img, (margin, margin), card_img)

    # === DRAW CONTENT ===
    draw = ImageDraw.Draw(img)

    # Subtle orange border
    draw.rounded_rectangle(card_rect, radius=corner_radius, outline=(80, 35, 10), width=1)

    # === FONTS ===
    font_brand = get_font(36, bold=True, syne=True)  # Syne for brand
    font_title = get_font(48, bold=True)
    font_display_name = get_font(32, bold=True)
    font_username = get_font(28, bold=True)
    font_followers = get_font(24)
    font_note = get_font(22)

    center_x = width // 2

    # === LOUDRR BRAND with actual logo icon ===
    brand_y = margin + 50
    brand_text = "Loudrr"

    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_text_w = brand_bbox[2] - brand_bbox[0]
    brand_text_h = brand_bbox[3] - brand_bbox[1]

    icon_size = 44  # Matches landing page proportions
    icon_gap = 10

    total_brand_w = icon_size + icon_gap + brand_text_w
    brand_x = center_x - total_brand_w // 2

    # Load Loudrr icon (the actual logo)
    try:
        loudrr_icon = load_icon("loudrr-icon", size=icon_size)
        icon_y = brand_y - (icon_size - brand_text_h) // 2 + 4
        img.paste(loudrr_icon, (brand_x, icon_y), loudrr_icon)
        draw = ImageDraw.Draw(img)
    except Exception:
        pass

    # Draw brand text with orange gradient
    text_x = brand_x + icon_size + icon_gap
    img = draw_orange_gradient_text(img, (text_x, brand_y), brand_text, font_brand, draw)
    draw = ImageDraw.Draw(img)

    # === MAIN TITLE: "You're on the Waitlist!" ===
    title_y = margin + 120
    title_text = "You're on the Waitlist!"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = center_x - title_w // 2

    # White text with subtle orange glow
    glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for i in range(8, 0, -2):
        alpha = int(20 * (1 - i / 8))
        glow_draw.text((title_x, title_y), title_text, fill=(249, 84, 0, alpha), font=font_title)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=10))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)
    draw.text((title_x, title_y), title_text, fill=white, font=font_title)

    # === PROFILE SECTION (avatar + name + username + followers) ===
    profile_y = margin + 200
    avatar_size = 80

    # Try to download avatar
    avatar_img = None
    if avatar_url:
        avatar_img = download_avatar(avatar_url, avatar_size)

    # If no avatar, create placeholder with initial
    if avatar_img is None:
        avatar_img = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
        avatar_draw = ImageDraw.Draw(avatar_img)
        # Orange circle background
        avatar_draw.ellipse([0, 0, avatar_size, avatar_size], fill=(60, 30, 15))
        avatar_draw.ellipse([2, 2, avatar_size-2, avatar_size-2], fill=(40, 20, 10))
        # Initial letter
        initial = (display_name or x_username)[0].upper()
        init_font = get_font(36, bold=True)
        init_bbox = avatar_draw.textbbox((0, 0), initial, font=init_font)
        init_w = init_bbox[2] - init_bbox[0]
        init_h = init_bbox[3] - init_bbox[1]
        init_x = (avatar_size - init_w) // 2
        init_y = (avatar_size - init_h) // 2 - init_bbox[1]
        avatar_draw.text((init_x, init_y), initial, fill=orange, font=init_font)

    # Calculate profile content layout
    profile_content = []
    if display_name:
        profile_content.append(("name", display_name))
    profile_content.append(("username", f"@{x_username}"))
    if followers_count is not None:
        profile_content.append(("followers", f"{format_followers(followers_count)} followers"))

    # Calculate total width for centering
    name_w = 0
    username_w = 0
    followers_w = 0

    if display_name:
        name_bbox = draw.textbbox((0, 0), display_name, font=font_display_name)
        name_w = name_bbox[2] - name_bbox[0]

    username_bbox = draw.textbbox((0, 0), f"@{x_username}", font=font_username)
    username_w = username_bbox[2] - username_bbox[0]

    if followers_count is not None:
        followers_bbox = draw.textbbox((0, 0), f"{format_followers(followers_count)} followers", font=font_followers)
        followers_w = followers_bbox[2] - followers_bbox[0]

    # Profile section: avatar on left, text on right
    text_gap = 20
    max_text_w = max(name_w, username_w, followers_w)
    total_profile_w = avatar_size + text_gap + max_text_w
    profile_x = center_x - total_profile_w // 2

    # Draw orange ring around avatar
    avatar_ring_size = avatar_size + 6
    ring_x = profile_x - 3
    ring_y = profile_y - 3
    draw.ellipse([ring_x, ring_y, ring_x + avatar_ring_size, ring_y + avatar_ring_size],
                 outline=orange, width=3)

    # Paste avatar
    img.paste(avatar_img, (profile_x, profile_y), avatar_img)
    draw = ImageDraw.Draw(img)

    # Draw text content
    text_x = profile_x + avatar_size + text_gap
    current_y = profile_y + 5

    if display_name:
        # Display name + verified badge
        draw.text((text_x, current_y), display_name, fill=white, font=font_display_name)
        if is_verified:
            name_bbox = draw.textbbox((0, 0), display_name, font=font_display_name)
            badge_x = text_x + name_bbox[2] - name_bbox[0] + 8
            badge_y = current_y + 4
            # Blue checkmark
            draw.ellipse([badge_x, badge_y, badge_x + 20, badge_y + 20], fill=twitter_blue)
            draw.text((badge_x + 5, badge_y + 1), "✓", fill=white, font=get_font(14, bold=True))
        current_y += 32

    # X Username with icon and orange gradient
    x_icon_size = 20
    try:
        x_icon = load_icon("x-logo", size=x_icon_size, color=white, rounded=True, radius=4)
        img.paste(x_icon, (text_x, current_y + 4), x_icon)
        draw = ImageDraw.Draw(img)
    except Exception:
        pass
    img = draw_orange_gradient_text(img, (text_x + x_icon_size + 8, current_y), f"@{x_username}", font_username, draw)
    draw = ImageDraw.Draw(img)
    current_y += 32

    # Telegram Username with icon
    if telegram_username:
        font_tg = get_font(24, bold=True)
        tg_icon_size = 20
        try:
            tg_icon = load_icon("telegram", size=tg_icon_size, color=(100, 180, 255))
            img.paste(tg_icon, (text_x, current_y + 2), tg_icon)
            draw = ImageDraw.Draw(img)
        except Exception:
            pass
        tg_text = f"@{telegram_username}" if not telegram_username.startswith('@') else telegram_username
        draw.text((text_x + tg_icon_size + 8, current_y), tg_text, fill=(100, 180, 255), font=font_tg)
        current_y += 28

    if followers_count is not None:
        draw.text((text_x, current_y), f"{format_followers(followers_count)} followers", fill=gray, font=font_followers)

    # === DIVIDER ===
    divider_y = height - margin - 130
    draw.line(
        [(margin + 80, divider_y), (width - margin - 80, divider_y)],
        fill=(60, 40, 25), width=2
    )

    # === NOTE AT BOTTOM ===
    note_text = "We'll notify you here when you get access"
    note_bbox = draw.textbbox((0, 0), note_text, font=font_note)
    note_w = note_bbox[2] - note_bbox[0]
    note_x = center_x - note_w // 2
    note_y = height - margin - 85
    draw.text((note_x, note_y), note_text, fill=gray, font=font_note)

    # === CTA HINT with orange gradient ===
    cta_text = "Stay tuned"
    cta_bbox = draw.textbbox((0, 0), cta_text, font=font_note)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = center_x - cta_w // 2
    cta_y = height - margin - 50
    img = draw_orange_gradient_text(img, (cta_x, cta_y), cta_text, font_note, draw)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)
    return output


def create_approval_card(x_username: str) -> io.BytesIO:
    """
    Create approval notification card with glassmorphism design.

    Premium celebratory design matching the mini app's Magic UI style.
    """
    # Credit card aspect ratio at high resolution
    width, height = 1012, 638
    margin = 32
    corner_radius = 32

    # Colors - Brand orange palette
    orange_light = (255, 149, 0)    # #FF9500
    orange = (249, 84, 0)           # #f95400
    orange_dark = (204, 85, 0)      # #CC5500
    white = (255, 255, 255)
    gray = (120, 120, 125)

    # === BACKGROUND: Very dark with subtle orange tint ===
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    for y in range(height):
        progress = y / height
        r = int(15 * (1 - progress))
        g = int(8 * (1 - progress))
        b = int(2 * (1 - progress))
        for x in range(width):
            img.putpixel((x, y), (r, g, b, 255))

    # === HALFTONE DOTS ON BACKGROUND ===
    bg_halftone = create_halftone_texture(width, height, dot_spacing=10, max_alpha=10)
    img = Image.alpha_composite(img, bg_halftone)

    # === STRONGER ORANGE GLOW for celebration ===
    card_rect = (margin, margin, width - margin, height - margin)
    card_w = card_rect[2] - card_rect[0]
    card_h = card_rect[3] - card_rect[1]

    glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for i in range(30, 0, -1):
        alpha = int(25 * (1 - i / 30))
        expand = i * 2
        glow_draw.rounded_rectangle(
            [margin - expand, margin - expand,
             width - margin + expand, height - margin + expand],
            radius=corner_radius + i,
            fill=(249, 84, 0, alpha)
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=20))
    img = Image.alpha_composite(img, glow)

    # === CREATE CARD WITH GLASSMORPHISM ===
    card_img = Image.new('RGBA', (card_w, card_h), (12, 12, 14, 255))

    # === SUBTLE ORANGE GRADIENT OVERLAY ===
    glossy_layer = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))

    for y in range(card_h):
        for x in range(card_w):
            cx, cy = card_w / 2, card_h / 2
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            max_dist = math.sqrt(cx**2 + cy**2)
            vignette = dist / max_dist

            orange_r = int(35 * vignette)
            orange_g = int(15 * vignette)
            orange_b = int(3 * vignette)
            glossy_layer.putpixel((x, y), (orange_r, orange_g, orange_b, int(80 * vignette)))

    glossy_layer = glossy_layer.filter(ImageFilter.GaussianBlur(radius=40))
    card_img = Image.alpha_composite(card_img, glossy_layer)

    # === HALFTONE TEXTURE ===
    halftone = create_halftone_texture(card_w, card_h, dot_spacing=6, max_alpha=12)
    card_img = Image.alpha_composite(card_img, halftone)

    # === GLOSSY SHINE ===
    shine = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)

    shine_width = card_w * 0.35
    for i in range(int(shine_width)):
        progress = i / shine_width
        intensity = math.exp(-((progress - 0.5) ** 2) / 0.06)
        alpha = int(45 * intensity)
        if alpha > 0:
            shine_draw.line([(i, 0), (i - card_h * 0.25, card_h)],
                           fill=(255, 180, 100, alpha), width=2)

    shine = shine.filter(ImageFilter.GaussianBlur(radius=10))
    card_img = Image.alpha_composite(card_img, shine)

    # === APPLY ROUNDED MASK ===
    card_mask = create_rounded_mask(card_w, card_h, corner_radius)
    card_img.putalpha(card_mask)

    # === PASTE CARD ===
    img.paste(card_img, (margin, margin), card_img)

    # === DRAW CONTENT ===
    draw = ImageDraw.Draw(img)

    # Orange border (brighter for celebration)
    draw.rounded_rectangle(card_rect, radius=corner_radius, outline=orange, width=2)

    # === FONTS ===
    font_brand = get_font(36, bold=True, syne=True)  # Syne for brand
    font_title = get_font(72, bold=True)
    font_subtitle = get_font(32)
    font_username = get_font(36, bold=True)
    font_note = get_font(22)

    center_x = width // 2

    # === LOUDRR BRAND with actual logo icon ===
    brand_y = margin + 50
    brand_text = "Loudrr"

    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_text_w = brand_bbox[2] - brand_bbox[0]
    brand_text_h = brand_bbox[3] - brand_bbox[1]

    icon_size = 44  # Matches landing page proportions
    icon_gap = 10
    total_brand_w = icon_size + icon_gap + brand_text_w
    brand_x = center_x - total_brand_w // 2

    # Load Loudrr icon (the actual logo)
    try:
        loudrr_icon = load_icon("loudrr-icon", size=icon_size)
        icon_y = brand_y - (icon_size - brand_text_h) // 2 + 4
        img.paste(loudrr_icon, (brand_x, icon_y), loudrr_icon)
        draw = ImageDraw.Draw(img)
    except Exception:
        pass

    text_x = brand_x + icon_size + icon_gap
    img = draw_orange_gradient_text(img, (text_x, brand_y), brand_text, font_brand, draw)
    draw = ImageDraw.Draw(img)

    # === MAIN TITLE: "Welcome!" with glow ===
    title_y = margin + 140
    title_text = "Welcome!"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = center_x - title_w // 2

    # Strong orange glow for celebration
    glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for i in range(12, 0, -2):
        alpha = int(30 * (1 - i / 12))
        glow_draw.text((title_x, title_y), title_text, fill=(249, 84, 0, alpha), font=font_title)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    draw.text((title_x, title_y), title_text, fill=white, font=font_title)

    # === SUBTITLE ===
    subtitle_y = margin + 230
    subtitle_text = "You've been approved"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=font_subtitle)
    subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = center_x - subtitle_w // 2
    img = draw_orange_gradient_text(img, (subtitle_x, subtitle_y), subtitle_text, font_subtitle, draw)
    draw = ImageDraw.Draw(img)

    # === X USERNAME PILL ===
    username_text = f"@{x_username}"
    username_bbox = draw.textbbox((0, 0), username_text, font=font_username)
    username_w = username_bbox[2] - username_bbox[0]
    username_h = username_bbox[3] - username_bbox[1]

    x_icon_size = 28
    icon_text_gap = 12
    pill_padding_x = 28
    pill_padding_y = 18
    pill_content_w = x_icon_size + icon_text_gap + username_w
    pill_left = center_x - pill_content_w // 2 - pill_padding_x
    pill_right = center_x + pill_content_w // 2 + pill_padding_x
    pill_top = margin + 310
    pill_bottom = pill_top + username_h + pill_padding_y * 2

    draw.rounded_rectangle(
        [pill_left, pill_top, pill_right, pill_bottom],
        radius=28, fill=(35, 20, 12), outline=orange, width=2
    )

    try:
        x_icon = load_icon("x-logo", size=x_icon_size, color=(255, 255, 255))
        x_icon = apply_orange_gradient_to_icon(x_icon)
        icon_x = center_x - pill_content_w // 2
        icon_y = pill_top + pill_padding_y + (username_h - x_icon_size) // 2
        img.paste(x_icon, (icon_x, icon_y), x_icon)
        draw = ImageDraw.Draw(img)
    except:
        pass

    text_x = center_x - pill_content_w // 2 + x_icon_size + icon_text_gap
    text_y = pill_top + pill_padding_y
    img = draw_orange_gradient_text(img, (text_x, text_y), username_text, font_username, draw)
    draw = ImageDraw.Draw(img)

    # === DIVIDER ===
    divider_y = height - margin - 130
    draw.line(
        [(margin + 80, divider_y), (width - margin - 80, divider_y)],
        fill=(70, 45, 25), width=2
    )

    # === TAGLINE ===
    tagline_text = "Earn karma by engaging. Spend karma to grow."
    tagline_bbox = draw.textbbox((0, 0), tagline_text, font=font_note)
    tagline_w = tagline_bbox[2] - tagline_bbox[0]
    tagline_x = center_x - tagline_w // 2
    tagline_y = height - margin - 90
    draw.text((tagline_x, tagline_y), tagline_text, fill=gray, font=font_note)

    # === CTA with orange gradient ===
    cta_text = "Tap below to start"
    cta_bbox = draw.textbbox((0, 0), cta_text, font=font_note)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = center_x - cta_w // 2
    cta_y = height - margin - 55
    img = draw_orange_gradient_text(img, (cta_x, cta_y), cta_text, font_note, draw)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)
    return output
