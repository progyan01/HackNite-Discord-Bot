from io import BytesIO
import math
from PIL import Image, ImageDraw, ImageFont

def get_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

def draw_card(card_str):
    """Draw a single standard card"""
    # Card surface
    width, height = 70, 100
    card_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card_img)
    
    # White rounded rectangle
    draw.rounded_rectangle([0, 0, width-1, height-1], radius=8, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
    
    # Text parsing
    rank = card_str[:-1]
    suit = card_str[-1]
    
    # Set colors
    color = (200, 0, 0, 255) if suit in ['♥', '♦'] else (0, 0, 0, 255)
    
    font_small = get_font(18)
    font_large = get_font(32)
    
    # Top left rank
    draw.text((8, 5), rank, fill=color, font=font_small)
    # Center Suit
    suit_w = draw.textlength(suit, font=font_large)
    # Roughly vertical center
    draw.text(((width - suit_w) / 2, 30), suit, fill=color, font=font_large)
    
    return card_img

def draw_card_back():
    """Draw a face-down hidden card"""
    width, height = 70, 100
    card_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card_img)
    
    # Blue patterned rect
    draw.rounded_rectangle([0, 0, width-1, height-1], radius=8, fill=(30, 60, 150, 255), outline=(0, 0, 0, 255), width=2)
    draw.rounded_rectangle([5, 5, width-6, height-6], radius=4, fill=(40, 80, 200, 255), outline=(255, 255, 255, 100), width=1)
    
    font = get_font(30)
    w = draw.textlength("?", font=font)
    draw.text(((width - w) / 2, 28), "?", fill=(255, 255, 255, 255), font=font)
    
    return card_img

def render_blackjack_table(player_hand, dealer_hand, game_over):
    """
    Renders the whole table into a BytesIO buffer returning a PNG image.
    """
    # Create Table Image
    table_w = 600
    table_h = 350
    table_img = Image.new("RGB", (table_w, table_h), (34, 139, 34)) # Forest Green Felt
    draw = ImageDraw.Draw(table_img)
    
    # Outline felt effect
    draw.rectangle([10, 10, table_w-10, table_h-10], outline=(20, 100, 20), width=4)
    
    # Titles
    font_title = get_font(24)
    draw.text((20, 20), "Dealer's Hand", fill=(255, 255, 255), font=font_title)
    draw.text((20, 180), "Your Hand", fill=(255, 255, 255), font=font_title)
    
    # Spacing logic
    card_spacing = 80
    
    # Render Dealer Cards
    for i, card_str in enumerate(dealer_hand):
        x = 20 + (i * card_spacing)
        y = 60
        if not game_over and i == 1:
            # Second card hidden
            card_surface = draw_card_back()
        else:
            card_surface = draw_card(card_str)
            
        table_img.paste(card_surface, (x, y), card_surface)
        
    # Render Player Cards
    for i, card_str in enumerate(player_hand):
        x = 20 + (i * card_spacing)
        y = 220
        card_surface = draw_card(card_str)
        table_img.paste(card_surface, (x, y), card_surface)
        
    buffer = BytesIO()
    table_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────────────
# Slot Machine Image Renderer
# ─────────────────────────────────────────────────────

# Symbol key → drawing function dispatched below
SLOT_SYMBOL_MAP = {
    "🍒": "cherry",
    "🍋": "lemon",
    "🍇": "grapes",
    "🔔": "bell",
    "💎": "diamond",
    "7️⃣": "seven",
}

def _draw_cherry(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """Two red cherries with a green stem."""
    cr = int(r * 0.32)
    # Left cherry
    lx, ly = cx - cr - 2, cy + cr // 2
    draw.ellipse([lx - cr, ly - cr, lx + cr, ly + cr], fill=(220, 20, 30), outline=(160, 10, 10), width=2)
    # highlight
    draw.ellipse([lx - cr // 3, ly - cr // 2, lx + cr // 6, ly - cr // 5], fill=(255, 100, 100))
    # Right cherry
    rx, ry = cx + cr + 2, cy + cr // 2
    draw.ellipse([rx - cr, ry - cr, rx + cr, ry + cr], fill=(220, 20, 30), outline=(160, 10, 10), width=2)
    draw.ellipse([rx - cr // 3, ry - cr // 2, rx + cr // 6, ry - cr // 5], fill=(255, 100, 100))
    # Stems
    draw.line([(lx, ly - cr), (cx, cy - r + 4)], fill=(30, 130, 30), width=3)
    draw.line([(rx, ry - cr), (cx, cy - r + 4)], fill=(30, 130, 30), width=3)
    # Leaf
    draw.ellipse([cx - 6, cy - r, cx + 10, cy - r + 12], fill=(50, 170, 50))


def _draw_lemon(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """A bright yellow lemon with a nub and highlight."""
    rx, ry = int(r * 0.7), int(r * 0.55)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(255, 225, 50), outline=(200, 170, 0), width=2)
    # Highlight
    draw.ellipse([cx - rx // 2, cy - ry + 4, cx - rx // 5, cy - ry // 3], fill=(255, 245, 140))
    # Nub on the end
    draw.ellipse([cx + rx - 4, cy - 5, cx + rx + 8, cy + 5], fill=(80, 160, 30))


def _draw_grapes(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """A cluster of purple grapes with a stem."""
    gr = int(r * 0.18)
    color = (120, 40, 160)
    hi = (170, 100, 210)
    # Grape positions (pyramid)
    positions = [
        (cx, cy - gr * 2),
        (cx - gr - 1, cy - gr // 2),
        (cx + gr + 1, cy - gr // 2),
        (cx - gr * 2, cy + gr),
        (cx, cy + gr),
        (cx + gr * 2, cy + gr),
        (cx - gr - 1, cy + gr * 2 + 2),
        (cx + gr + 1, cy + gr * 2 + 2),
    ]
    for gx, gy in positions:
        draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=color, outline=(80, 20, 110), width=1)
        draw.ellipse([gx - gr // 3, gy - gr // 2, gx + gr // 6, gy - gr // 4], fill=hi)
    # Stem
    draw.line([(cx, cy - gr * 2 - gr), (cx, cy - r + 2)], fill=(60, 120, 40), width=3)
    draw.ellipse([cx - 5, cy - r - 2, cx + 10, cy - r + 9], fill=(50, 150, 50))


def _draw_bell(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """A gold bell with a clapper."""
    bw = int(r * 0.65)
    bh = int(r * 0.7)
    # Bell body (arc + rectangle combo)
    draw.pieslice([cx - bw, cy - bh, cx + bw, cy + bh // 3], start=180, end=360, fill=(255, 200, 50), outline=(190, 140, 20), width=2)
    draw.rectangle([cx - bw, cy - 2, cx + bw, cy + bh // 3], fill=(255, 200, 50), outline=(190, 140, 20), width=2)
    # Flared bottom
    draw.rounded_rectangle([cx - bw - 6, cy + bh // 3 - 4, cx + bw + 6, cy + bh // 3 + 8], radius=4, fill=(255, 210, 60), outline=(190, 140, 20), width=2)
    # Clapper
    draw.ellipse([cx - 5, cy + bh // 3 + 3, cx + 5, cy + bh // 3 + 13], fill=(180, 130, 20))
    # Top nub
    draw.ellipse([cx - 4, cy - bh - 2, cx + 4, cy - bh + 6], fill=(190, 140, 20))
    # Highlight
    draw.ellipse([cx - bw // 2, cy - bh + 8, cx - bw // 5, cy - bh // 2], fill=(255, 235, 140))


def _draw_diamond(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """A sparkling cyan diamond."""
    w = int(r * 0.6)
    h = int(r * 0.8)
    top = cy - h
    mid = cy - h // 3
    bottom = cy + h
    points = [(cx, top), (cx + w, mid), (cx, bottom), (cx - w, mid)]
    draw.polygon(points, fill=(80, 220, 240), outline=(40, 160, 200), width=2)
    # Facets
    draw.line([(cx - w, mid), (cx, top)], fill=(130, 240, 255), width=2)
    draw.line([(cx, top), (cx + w, mid)], fill=(60, 190, 220), width=1)
    draw.polygon([(cx, top), (cx - w // 3, mid), (cx + w // 3, mid)], fill=(120, 235, 255))
    # Sparkle dots
    for sx, sy in [(cx - w // 2, mid - 4), (cx + w // 3, mid + h // 3)]:
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(255, 255, 255))


def _draw_seven(draw: ImageDraw.Draw, cx: int, cy: int, r: int):
    """A bold, stylized lucky 7 in gold."""
    font = get_font(int(r * 1.6))
    text = "7"
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw // 2
    ty = cy - th // 2 - bbox[1]
    # Shadow
    draw.text((tx + 2, ty + 2), text, fill=(120, 80, 0), font=font)
    # Main
    draw.text((tx, ty), text, fill=(255, 215, 0), font=font)
    # Inner highlight
    draw.text((tx - 1, ty - 1), text, fill=(255, 240, 120), font=font)
    draw.text((tx, ty), text, fill=(255, 215, 0), font=font)


_SYMBOL_DRAWERS = {
    "cherry": _draw_cherry,
    "lemon": _draw_lemon,
    "grapes": _draw_grapes,
    "bell": _draw_bell,
    "diamond": _draw_diamond,
    "seven": _draw_seven,
}


def _draw_slot_symbol(draw: ImageDraw.Draw, emoji: str, cx: int, cy: int, cell_size: int):
    """Dispatch to the correct symbol drawer based on the emoji key."""
    key = SLOT_SYMBOL_MAP.get(emoji)
    if key and key in _SYMBOL_DRAWERS:
        _SYMBOL_DRAWERS[key](draw, cx, cy, cell_size // 2 - 6)
    else:
        # Fallback: render the emoji as text
        font = get_font(int(cell_size * 0.5))
        bbox = font.getbbox(emoji)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cy - th // 2 - bbox[1]), emoji, fill=(255, 255, 255), font=font)


def render_slots_machine(grid, spinning=False, win_rows=None):
    """
    Renders a premium 3x3 slot machine image.
    
    Args:
        grid: 3x3 list of (emoji, multiplier) tuples
        spinning: If True, show blur placeholder cells instead of symbols
        win_rows: Optional set/list of row indices that are winners (for highlighting)
    
    Returns:
        BytesIO buffer with the PNG image.
    """
    if win_rows is None:
        win_rows = set()

    # ── Canvas dimensions ──
    W, H = 520, 480
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Background: rich red gradient ──
    for y in range(H):
        t = y / H
        r = int(110 + 30 * t)
        g = int(15 + 10 * t)
        b = int(15 + 10 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Outer gold frame ──
    frame_pad = 12
    draw.rounded_rectangle(
        [frame_pad, frame_pad, W - frame_pad, H - frame_pad],
        radius=18, fill=None, outline=(218, 165, 32), width=5
    )
    draw.rounded_rectangle(
        [frame_pad + 4, frame_pad + 4, W - frame_pad - 4, H - frame_pad - 4],
        radius=15, fill=None, outline=(255, 215, 0, 120), width=2
    )

    # ── Title banner ──
    banner_h = 55
    banner_y = 22
    # Dark banner bg
    draw.rounded_rectangle(
        [30, banner_y, W - 30, banner_y + banner_h],
        radius=10, fill=(30, 10, 10, 220), outline=(255, 200, 50), width=2
    )
    # Title text
    title_font = get_font(30)
    title = "★  SUPER  SLOTS  ★"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, banner_y + 10), title, fill=(255, 215, 0), font=title_font)

    # ── Decorative corner stars ──
    star_font = get_font(22)
    draw.text((40, banner_y + 14), "♦", fill=(255, 200, 50), font=star_font)
    draw.text((W - 58, banner_y + 14), "♦", fill=(255, 200, 50), font=star_font)

    # ── Reel area ──
    cell_size = 110
    grid_w = cell_size * 3
    grid_h = cell_size * 3
    grid_x = (W - grid_w) // 2
    grid_y = banner_y + banner_h + 22

    # Reel backing (dark panel)
    draw.rounded_rectangle(
        [grid_x - 10, grid_y - 10, grid_x + grid_w + 10, grid_y + grid_h + 10],
        radius=12, fill=(20, 8, 8), outline=(180, 140, 30), width=3
    )

    # ── Draw each cell ──
    for row_i in range(3):
        for col_i in range(3):
            x0 = grid_x + col_i * cell_size
            y0 = grid_y + row_i * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size

            # Cell colour – highlight winning rows with warm gold tint
            is_winner = row_i in win_rows
            if spinning:
                cell_fill = (50, 25, 25)
            elif is_winner:
                cell_fill = (60, 50, 15)
            else:
                cell_fill = (35, 12, 12)

            draw.rounded_rectangle(
                [x0 + 3, y0 + 3, x1 - 3, y1 - 3],
                radius=8, fill=cell_fill, outline=(140, 110, 30) if is_winner else (80, 60, 20), width=2
            )

            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2

            if spinning:
                # Draw spinning blur lines
                for offset in range(-20, 25, 10):
                    alpha = max(40, 160 - abs(offset) * 6)
                    draw.line(
                        [(x0 + 15, cy + offset), (x1 - 15, cy + offset)],
                        fill=(200, 180, 80, alpha), width=3
                    )
            else:
                emoji = grid[row_i][col_i][0]
                _draw_slot_symbol(draw, emoji, cx, cy, cell_size)

    # ── Win-row arrow markers ──
    if win_rows and not spinning:
        arrow_font = get_font(26)
        for ri in win_rows:
            arrow_y = grid_y + ri * cell_size + cell_size // 2 - 13
            draw.text((grid_x - 30, arrow_y), "▶", fill=(255, 215, 0), font=arrow_font)
            draw.text((grid_x + grid_w + 12, arrow_y), "◀", fill=(255, 215, 0), font=arrow_font)

    # ── Bottom strip with decorative dots ──
    strip_y = grid_y + grid_h + 18
    draw.rounded_rectangle(
        [30, strip_y, W - 30, strip_y + 28],
        radius=6, fill=(30, 10, 10, 200), outline=(180, 140, 30), width=2
    )
    dot_font = get_font(14)
    dots = "●  ●  ●  ●  ●  ●  ●  ●  ●"
    dbbox = dot_font.getbbox(dots)
    dw = dbbox[2] - dbbox[0]
    draw.text(((W - dw) // 2, strip_y + 5), dots, fill=(255, 200, 50, 180), font=dot_font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
