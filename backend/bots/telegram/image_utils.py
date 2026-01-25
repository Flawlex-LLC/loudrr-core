"""
Image generation utilities for Telegram bot.
Premium glossy black card with golden accents, halftone texture, and shine effect.
"""
import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
import os


def get_font(size: int, bold: bool = False):
    """Get Space Grotesk font for premium look, with fallbacks."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(script_dir, "fonts")

    if bold:
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

    # Loudrr brand on right (with paper plane icon)
    font_brand = get_font(36, bold=True)
    brand_text = "loudrr"

    # Get brand text dimensions
    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_text_w = brand_bbox[2] - brand_bbox[0]
    brand_text_h = brand_bbox[3] - brand_bbox[1]

    # Icon size matches text height
    icon_size = brand_text_h + 16
    icon_gap = 12

    # Calculate total brand width (icon + gap + text)
    total_brand_w = icon_size + icon_gap + brand_text_w

    # Position brand block on right
    brand_x = right_edge - total_brand_w
    brand_y = row1_y - 4

    # Load and paste paper plane icon with gradient
    plane_icon = load_icon("paper-plane", size=icon_size, color=(255, 255, 255))
    plane_icon = apply_gradient_to_icon(plane_icon)
    icon_y = brand_y - (icon_size - brand_text_h) // 2  # Center icon vertically with text
    img.paste(plane_icon, (brand_x, icon_y), plane_icon)
    draw = ImageDraw.Draw(img)  # Refresh draw after paste

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
    img = draw_gradient_text(img, (left_x, footer_y), "/feed to earn  •  /post to spend", font_hint, draw)
    draw = ImageDraw.Draw(img)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)

    return output


def create_waitlist_card(x_username: str) -> io.BytesIO:
    """
    Create waitlist confirmation card.

    Simple, clean design with Loudrr branding.
    Orange (#FF6B00) accents on dark background.
    """
    width, height = 800, 450
    margin = 40
    corner_radius = 24

    # Colors - Orange theme matching app
    orange = (255, 107, 0)  # #FF6B00
    orange_dark = (200, 85, 0)
    white = (255, 255, 255)
    gray = (150, 150, 150)
    card_bg = (18, 18, 20)
    bg_dark = (10, 10, 12)

    # Create image with dark background
    img = Image.new('RGBA', (width, height), bg_dark)
    draw = ImageDraw.Draw(img)

    # Card with rounded corners
    card_rect = (margin, margin, width - margin, height - margin)
    draw.rounded_rectangle(card_rect, radius=corner_radius, fill=card_bg)

    # Subtle orange border
    draw.rounded_rectangle(card_rect, radius=corner_radius, outline=orange_dark, width=1)

    # === CONTENT ===
    left_x = margin + 48
    center_x = width // 2

    # Fonts
    font_brand = get_font(28, bold=True)
    font_title = get_font(36, bold=True)
    font_username = get_font(28)
    font_note = get_font(18)

    # Loudrr brand at top
    brand_text = "LOUDRR"
    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text((center_x - brand_w // 2, margin + 50), brand_text, fill=orange, font=font_brand)

    # Main message
    title_text = "You're on the Waitlist!"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text((center_x - title_w // 2, margin + 120), title_text, fill=white, font=font_title)

    # X username with @ icon
    username_text = f"@{x_username}"
    username_bbox = draw.textbbox((0, 0), username_text, font=font_username)
    username_w = username_bbox[2] - username_bbox[0]

    # Orange pill background for username
    pill_padding = 20
    pill_left = center_x - username_w // 2 - pill_padding
    pill_right = center_x + username_w // 2 + pill_padding
    pill_top = margin + 190
    pill_bottom = pill_top + 50

    draw.rounded_rectangle(
        [pill_left, pill_top, pill_right, pill_bottom],
        radius=25, fill=(40, 25, 15), outline=orange, width=1
    )

    draw.text(
        (center_x - username_w // 2, pill_top + 10),
        username_text, fill=orange, font=font_username
    )

    # Note at bottom
    note_text = "We'll notify you when you're in"
    note_bbox = draw.textbbox((0, 0), note_text, font=font_note)
    note_w = note_bbox[2] - note_bbox[0]
    draw.text((center_x - note_w // 2, height - margin - 70), note_text, fill=gray, font=font_note)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)
    return output


def create_approval_card(x_username: str) -> io.BytesIO:
    """
    Create approval notification card.

    Celebratory design for approved waitlist entries.
    """
    width, height = 800, 500
    margin = 40
    corner_radius = 24

    # Colors
    orange = (255, 107, 0)  # #FF6B00
    orange_bright = (255, 140, 50)
    white = (255, 255, 255)
    gray = (150, 150, 150)
    card_bg = (18, 18, 20)
    bg_dark = (10, 10, 12)

    # Create image
    img = Image.new('RGBA', (width, height), bg_dark)
    draw = ImageDraw.Draw(img)

    # Orange glow effect
    glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for i in range(20, 0, -1):
        alpha = int(15 * (1 - i / 20))
        expand = i * 3
        glow_draw.rounded_rectangle(
            [margin - expand, margin - expand,
             width - margin + expand, height - margin + expand],
            radius=corner_radius + i,
            fill=(255, 107, 0, alpha)
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=15))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Card background
    card_rect = (margin, margin, width - margin, height - margin)
    draw.rounded_rectangle(card_rect, radius=corner_radius, fill=card_bg)
    draw.rounded_rectangle(card_rect, radius=corner_radius, outline=orange, width=2)

    # === CONTENT ===
    center_x = width // 2

    # Fonts
    font_brand = get_font(28, bold=True)
    font_title = get_font(42, bold=True)
    font_subtitle = get_font(24)
    font_username = get_font(28)
    font_note = get_font(18)

    # Loudrr brand
    brand_text = "LOUDRR"
    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text((center_x - brand_w // 2, margin + 50), brand_text, fill=orange, font=font_brand)

    # Main message
    title_text = "Welcome!"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text((center_x - title_w // 2, margin + 110), title_text, fill=white, font=font_title)

    subtitle_text = "You've been approved"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=font_subtitle)
    subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
    draw.text((center_x - subtitle_w // 2, margin + 165), subtitle_text, fill=orange_bright, font=font_subtitle)

    # X username
    username_text = f"@{x_username}"
    username_bbox = draw.textbbox((0, 0), username_text, font=font_username)
    username_w = username_bbox[2] - username_bbox[0]

    # Orange pill background
    pill_padding = 20
    pill_left = center_x - username_w // 2 - pill_padding
    pill_right = center_x + username_w // 2 + pill_padding
    pill_top = margin + 220
    pill_bottom = pill_top + 50

    draw.rounded_rectangle(
        [pill_left, pill_top, pill_right, pill_bottom],
        radius=25, fill=(40, 25, 15), outline=orange, width=1
    )
    draw.text(
        (center_x - username_w // 2, pill_top + 10),
        username_text, fill=orange, font=font_username
    )

    # Tagline
    tagline_text = "Earn karma by engaging. Spend karma to grow."
    tagline_bbox = draw.textbbox((0, 0), tagline_text, font=font_note)
    tagline_w = tagline_bbox[2] - tagline_bbox[0]
    draw.text((center_x - tagline_w // 2, height - margin - 90), tagline_text, fill=gray, font=font_note)

    # CTA hint
    cta_text = "Tap below to start"
    cta_bbox = draw.textbbox((0, 0), cta_text, font=font_note)
    cta_w = cta_bbox[2] - cta_bbox[0]
    draw.text((center_x - cta_w // 2, height - margin - 55), cta_text, fill=white, font=font_note)

    # Save
    output = io.BytesIO()
    img.save(output, format='PNG', quality=95)
    output.seek(0)
    return output
