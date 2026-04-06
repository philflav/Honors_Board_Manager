import json
from PIL import Image, ImageDraw, ImageFont
import os

# 1. Setup
font_path = "C:/Windows/Fonts/times.ttf"
background_template = Image.open("./Board_backround_images/background_2.png")
json_data = "honors_boards_cache.json" # Your attached file

# Define colors and positions
gold_color = (195, 163, 102) # Conceptual color
shadow_color = (40, 20, 10)    # Dark brown/black for the depth
highlight_color = (255, 230, 180, 150) # Light cream for the top edge
#Data positioning over background image
board_name_font_size = 30
board_name_x = 300
board_name_start_y = 286
max_title_width = 750
image_width = background_template.width
font_size_list = 24
text_start_x = 315
text_start_y = 370
text_start_y2 = 375
row_height = 24.9
max_rows=22

def draw_centered_titled(draw, title, y_pos, board_width, max_title_width, base_font_path, initial_size, color):
    current_size = initial_size
    font = ImageFont.truetype(base_font_path, current_size)
    
    # 1. Scale down font size if title is too wide
    # getbbox returns (left, top, right, bottom)
    text_width = draw.textbbox((0, 0), title, font=font)[2]
    
    while text_width > max_title_width and current_size > 10:
        current_size -= 1
        font = ImageFont.truetype(base_font_path, current_size)
        text_width = draw.textbbox((0, 0), title, font=font)[2]

    # 2. Calculate X position for center justification
    # Formula: (Total Image Width / 2) - (Text Width / 2)
    x_pos = (board_width - text_width) // 2
    
    # 3. Draw using the embossed function from before
    draw_embossed_text(draw, (x_pos, y_pos), title, font, color)

def draw_embossed_text(draw, position, text, font, base_color):
    x, y = position
    
    # Draw the shadow (shifted down and right by 2 pixels)
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
    
    # Draw a subtle highlight (shifted up and left by 1 pixel)
    draw.text((x - 1, y - 1), text, font=font, fill=highlight_color)
    
    # Draw the main gold text on top
    draw.text((x, y), text, font=font, fill=base_color)

def automate_boards():
    # Create the directory if it doesn't already exist
    if not os.path.exists("automated_images"):
        os.makedirs("automated_images")

    with open(json_data, 'r') as f:
        data = json.load(f)

    for board in data:
        current_board_id = board["board_id"]
        # Make a copy of the background template
        final_image = background_template.copy()
        draw = ImageDraw.Draw(final_image)

        # Draw the board name
        board_name = board["title"]
        board_name_font = ImageFont.truetype(font_path, board_name_font_size)
        #draw_embossed_text(draw, (board_name_x, board_name_start_y), board_name, board_name_font, gold_color)
        draw_centered_titled(draw, board_name, board_name_start_y, image_width, max_title_width, font_path, board_name_font_size, gold_color)

        # Draw the list of winners
        y_offset = text_start_y
        count=0
        for winner_entry in board["winners"]:
            if count ==0:
                y_offset = text_start_y2
            else:
                y_offset = text_start_y2 + count*row_height
            count+=1
            if count>max_rows:
                break   
            year = winner_entry["year"]
            winner_name = winner_entry["winner"]

            # Set text (programmatic positioning)
            list_font = ImageFont.truetype(font_path, font_size_list)
            text_string = f"{year}  {winner_name}"

            # Optional score logic if required
            # score = winner_entry.get("score", "")

            # Draw the text on the board copy
            draw_embossed_text(draw, (text_start_x, y_offset), text_string, list_font, gold_color)


        # Save unique board image
        final_image.save(f"automated_images/board_{current_board_id}.png")

automate_boards()