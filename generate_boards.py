import json
from PIL import Image, ImageDraw, ImageFont
import os
import argparse
import sys

# 1. Setup - Cross-platform font path
if os.name == 'nt': # Windows
    font_path = "C:/Windows/Fonts/times.ttf"
else: # Linux (Docker/Render)
    font_path = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"

CONFIG_FILE = "board_configs.json"
CACHE_FILE = "honors_boards_cache.json"

# Colors
gold_color = (195, 163, 102)
shadow_color = (40, 20, 10)
highlight_color = (255, 230, 180, 150)

def load_config(columns):
    """Loads settings for a specific column count from JSON."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r') as f:
        configs = json.load(f)
    
    col_str = str(columns)
    if col_str not in configs:
        print(f"Warning: Configuration for {columns} columns not found. Defaulting to 1.")
        col_str = "1"
    
    return configs[col_str]

def draw_centered_titled(draw, title, y_pos, board_width, max_title_width, base_font_path, initial_size, color):
    current_size = initial_size
    font = ImageFont.truetype(base_font_path, current_size)
    
    text_width = draw.textbbox((0, 0), title, font=font)[2]
    
    while text_width > max_title_width and current_size > 10:
        current_size -= 1
        font = ImageFont.truetype(base_font_path, current_size)
        text_width = draw.textbbox((0, 0), title, font=font)[2]

    x_pos = (board_width - text_width) // 2
    draw_embossed_text(draw, (x_pos, y_pos), title, font, color)

def draw_embossed_text(draw, position, text, font, base_color):
    x, y = position
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
    draw.text((x - 1, y - 1), text, font=font, fill=highlight_color)
    draw.text((x, y), text, font=font, fill=base_color)

def split_winners(winners, num_cols, capacities):
    """Splits winners into columns based on relative capacities."""
    total_cap = sum(capacities)
    if total_cap == 0: return [[] for _ in range(num_cols)]
    
    # Calculate how many winners per column based on proportion of total capacity
    num_winners = len(winners)
    counts = []
    remaining = num_winners
    for i in range(num_cols):
        count = int((capacities[i] / total_cap) * num_winners)
        counts.append(count)
        remaining -= count
    
    # Distribute remainders to columns that have space
    for i in range(remaining):
        counts[i % num_cols] += 1
        
    # Split the list
    result = []
    start = 0
    for count in counts:
        result.append(winners[start:start+count])
        start += count
    return result

def automate_boards(columns, limit_ids=None):
    # Load configuration
    config = load_config(columns)
    bg_path = os.path.join("Board_background_images", config["background_image"])
    
    if not os.path.exists(bg_path):
        print(f"Warning: Background image {bg_path} not found! Skipping generation.")
        return

    background_template = Image.open(bg_path)
    image_width = background_template.width

    if not os.path.exists("automated_images"):
        os.makedirs("automated_images")
    if not os.path.exists("tmp_images"):
        os.makedirs("tmp_images")

    with open(CACHE_FILE, 'r') as f:
        data = json.load(f)

    first_image_path = None

    for board in data:
        current_board_id = board["board_id"]
        if limit_ids and current_board_id not in limit_ids:
            continue
            
        final_image = background_template.copy()
        draw = ImageDraw.Draw(final_image)

        # Draw the board name
        board_name = board["title"]
        draw_centered_titled(draw, board_name, config["board_name_start_y"], image_width, 
                             config["max_title_width"], font_path, config["board_name_font_size"], gold_color)

        # Prepare capacities for balancing
        max_rows = config["max_rows"]
        # Middle columns get one less slot if num_cols >= 3
        capacities = []
        for i in range(columns):
            if columns >= 3 and 0 < i < columns - 1:
                capacities.append(max_rows - 1)
            else:
                capacities.append(max_rows)

        # Split and draw winners
        winner_columns = split_winners(board["winners"], columns, capacities)
        
        for col_idx, col_winners in enumerate(winner_columns):
            if col_idx >= len(config["column_x_positions"]):
                break
                
            x_pos = config["column_x_positions"][col_idx]
            is_middle = (columns >= 3 and 0 < col_idx < columns - 1)
            
            for row_idx, winner_entry in enumerate(col_winners):
                if row_idx >= capacities[col_idx]:
                    break
                    
                # If middle column, skip the first row
                effective_row_idx = row_idx + 1 if is_middle else row_idx
                
                if effective_row_idx == 0:
                    y_pos = config["text_start_y2"]
                else:
                    y_pos = config["text_start_y2"] + effective_row_idx * config["row_height"]
                
                year = winner_entry["year"]
                winner_name = winner_entry["winner"]
                text_string = f"{year}  {winner_name}"
                list_font = ImageFont.truetype(font_path, config["font_size_list"])
                
                draw_embossed_text(draw, (x_pos, y_pos), text_string, list_font, gold_color)

        output_path = f"automated_images/board_{current_board_id}_col{columns}.png"
        final_image.save(output_path, optimize=True, compress_level=9)
        print(f"Generated {output_path}")
        
        if first_image_path is None:
            first_image_path = output_path

    # Store test image if requested
    if first_image_path and os.path.exists(first_image_path):
        import shutil
        test_path = "tmp_images/test_board.png"
        shutil.copy(first_image_path, test_path)
        print(f"Stored test image in {test_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Honors Boards")
    parser.add_argument("ids", nargs="*", type=int, help="Optional board IDs to generate")
    parser.add_argument("--columns", "-c", type=int, default=1, choices=[1, 2, 3, 4], help="Number of columns (1-4)")
    
    args = parser.parse_args()
    
    automate_boards(args.columns, limit_ids=args.ids if args.ids else None)