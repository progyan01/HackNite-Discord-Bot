from io import BytesIO
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
