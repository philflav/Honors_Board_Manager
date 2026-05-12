import json
from PIL import Image, ImageDraw, ImageFont
import os
import argparse
import sys

# 1. Setup - Cross-platform font path with validation
def get_font_path():
    """Find a valid serif font path for the current system."""
    if os.name == 'nt':  # Windows
        possible_paths = [
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/timesbd.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
    else:  # Linux (Docker/Render)
        possible_paths = [
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        ]

    # Try to find any available serif font using fc-list if available
    try:
        import subprocess
        result = subprocess.run(['fc-list', ':family=serif', '--format=%{file}\\n'],
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            fc_paths = [p.strip() for p in result.stdout.strip().split('\\n') if p.strip()]
            possible_paths = fc_paths + possible_paths
    except (FileNotFoundError, Exception):
        pass

    for path in possible_paths:
        if os.path.exists(path):
            print(f"Using font: {path}")
            return path

    print("Warning: No suitable font found. Will use default font.")
    return None  # No font found

font_path = get_font_path()

def load_font(size):
    """Load font with fallback to default if custom font fails."""
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError) as e:
            print(f"Warning: Failed to load font {font_path}: {e}")
    
    # Fallback to default font
    print("Warning: Using default font - text may not appear as expected")
    return ImageFont.load_default()

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

def draw_centered_titled(draw, title, y_pos, board_width, max_title_width, initial_size, color):
    current_size = initial_size
    font = load_font(current_size)
    
    text_width = draw.textbbox((0, 0), title, font=font)[2]
    
    while text_width > max_title_width and current_size > 10:
        current_size -= 1
        font = load_font(current_size)
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
    
    # Cap winners to total capacity to avoid missing years in the middle
    if len(winners) > total_cap:
        winners = winners[:total_cap]
    
    num_winners = len(winners)
    counts = []
    acc_cap = 0
    acc_winners = 0
    
    for i in range(num_cols):
        acc_cap += capacities[i]
        # Proportionally, how many winners should be in columns 0 to i
        target_acc_winners = (acc_cap / total_cap) * num_winners
        current_acc_winners = int(round(target_acc_winners))
        count = current_acc_winners - acc_winners
        counts.append(count)
        acc_winners = current_acc_winners
        
    # Split the list
    result = []
    start = 0
    for count in counts:
        result.append(winners[start:start+count])
        start += count
    return result

def split_winners_progressive(winners, num_cols, capacities):
    """Splits winners into columns sequentially (fill column 1, then 2, etc.)."""
    total_cap = sum(capacities)
    if total_cap == 0: return [[] for _ in range(num_cols)]
    
    # Cap winners to total capacity to avoid missing years in the middle
    if len(winners) > total_cap:
        winners = winners[:total_cap]
    
    result = []
    start = 0
    for cap in capacities:
        count = min(cap, len(winners) - start)
        result.append(winners[start:start+count])
        start += count
    
    # Ensure we return the correct number of columns even if some are empty
    while len(result) < num_cols:
        result.append([])
        
    return result

def automate_boards(global_columns, limit_ids=None, per_board_config=None):
    # Load configuration
    if not os.path.exists("automated_images"):
        os.makedirs("automated_images")
    if not os.path.exists("tmp_images"):
        os.makedirs("tmp_images")

    with open(CACHE_FILE, 'r') as f:
        data = json.load(f)

    first_image_path = None
    first_image_8bit_path = None

    for board in data:
        current_board_id = board["board_id"]
        if limit_ids and current_board_id not in limit_ids:
            continue
            
        # Determine columns and fill method for this board
        board_id_str = str(current_board_id)
        if per_board_config and board_id_str in per_board_config:
            columns = int(per_board_config[board_id_str].get("columns", global_columns))
            fill_method = per_board_config[board_id_str].get("fill", "progressive").lower()
        else:
            columns = global_columns
            fill_method = "progressive"
            
        config = load_config(columns)
        bg_path = os.path.join("Board_background_images", config["background_image"])
        
        if not os.path.exists(bg_path):
            print(f"Warning: Background image {bg_path} not found! Skipping generation.")
            continue

        background_template = Image.open(bg_path)
        image_width = background_template.width
        
        max_rows = config["max_rows"]
        capacities = []
        for i in range(columns):
            if columns >= 3 and 0 < i < columns - 1:
                capacities.append(max_rows - 1)
            else:
                capacities.append(max_rows)

        total_cap = sum(capacities)
        if total_cap == 0: total_cap = 1

        all_winners = board["winners"]
        if not all_winners:
            chunks = [[]]
        else:
            chunks = [all_winners[i:i + total_cap] for i in range(0, len(all_winners), total_cap)]

        board_title_safe = "".join([c for c in board["title"] if c.isalnum() or c in " -_"]).strip().replace(" ", "_")

        for part_idx, chunk_winners in enumerate(chunks):
            final_image = background_template.copy()
            draw = ImageDraw.Draw(final_image)

            # Draw the board name
            board_name = board["title"]
            title_font_size = 30 if len(board_name) > 18 else config["board_name_font_size"]
            draw_centered_titled(draw, board_name, config["board_name_start_y"], image_width, 
                                 config["max_title_width"], title_font_size, gold_color)

            # Split winners based on method
            if fill_method == "balanced":
                winner_columns = split_winners(chunk_winners, columns, capacities)
            else:
                winner_columns = split_winners_progressive(chunk_winners, columns, capacities)
            
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
                    list_font = load_font(config["font_size_list"])
                    
                    draw_embossed_text(draw, (x_pos, y_pos), text_string, list_font, gold_color)

            # Output Paths
            output_path = f"automated_images/{board_title_safe}-{part_idx + 1}.png"
            final_image.save(output_path, optimize=True, compress_level=9)
            print(f"Generated {output_path}")
            
            # 8-bit Quantized save
            quantized_path = f"automated_images/{board_title_safe}-{part_idx + 1}_8bit.png"
            quantized_image = final_image.convert('P', palette=Image.ADAPTIVE, colors=256)
            quantized_image.save(quantized_path, optimize=True)
            print(f"Generated quantized {quantized_path}")
            
            if first_image_path is None:
                first_image_path = output_path
                first_image_8bit_path = quantized_path

    # Store test images
    if first_image_path and os.path.exists(first_image_path):
        import shutil
        test_path = "tmp_images/test_board.png"
        shutil.copy(first_image_path, test_path)
        
        test_8bit_path = "tmp_images/test_board_8bit.png"
        if os.path.exists(first_image_8bit_path):
            shutil.copy(first_image_8bit_path, test_8bit_path)
            print(f"Stored test images in {test_path} and {test_8bit_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Honors Boards")
    parser.add_argument("ids", nargs="*", type=int, help="Optional board IDs to generate")
    parser.add_argument("--columns", "-c", type=int, default=1, choices=[1, 2, 3, 4], help="Global columns fallback")
    parser.add_argument("--config", type=str, help="JSON string with per-board settings")
    
    args = parser.parse_args()
    
    per_board_config = None
    if args.config:
        try:
            per_board_config = json.loads(args.config)
        except json.JSONDecodeError:
            print("Error: Invalid JSON for --config")
            sys.exit(1)
            
    automate_boards(args.columns, limit_ids=args.ids if args.ids else None, per_board_config=per_board_config)