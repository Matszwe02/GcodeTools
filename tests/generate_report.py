import os
# import shutil
from concurrent.futures import as_completed, ProcessPoolExecutor
# from tqdm import tqdm
import time
# import math
# import io
import subprocess

from PIL import Image, ImageDraw, ImageFont

# Adjust import paths for GcodeTools as it will be run from tests/
# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from GcodeTools import Gcode, Tools
from GcodeTools.Thumbnails import gcode_thumbnails

# This will store the data needed for the report
processed_data = []

do_verbose = False # Set to True for verbose output in G-code writing, not strictly needed for this task


def process_gcode(name, id):
    """
    Processes a single G-code file, extracts relevant data, and generates thumbnails.
    """
    print(f'analising {name}...')
    
    gcode = Gcode()
    
    gcode.config.speed = 1440
    gcode.config.step = 0.01
    gcode.config.precision = 5
    
    # Read Gcode from gcodes/ directory
    # The path needs to be relative to the current working directory or absolute
    # When run from /home/mati/Documents/GcodeTools, 'gcodes/' is correct.
    # When run from tests/, it needs to be '../gcodes/'
    gcode_path = os.path.join(os.path.dirname(__file__), 'GcodeTools_gcodes', f'{name}.gcode')
    
    # tq = tqdm(unit="lines", desc=f"Reading Gcode {name}", position=id * 5 + 0)
    # update = lambda i, length: (setattr(tq, 'total', length), tq.update(1))
    
    try:
        out_gcode = Tools.trim(gcode.from_file(gcode_path))
    except FileNotFoundError:
        print(f"Error: G-code file not found at {gcode_path}")
        return None
    # except Exception as e:
    #     print(f"Error reading G-code file {name}: {e}")
    #     return None

    # Calculate total material
    total_material = sum(block.block_data.position.E for block in out_gcode)

    # Generate file thumbnail
    file_thumbnail_img = None
    # thumb_gcode_for_file = out_gcode.new()
    thumb_gcode_for_file = Tools.split(out_gcode)[2]
    # Collect relevant blocks for file thumbnail generation (e.g., blocks with extrusion data)
    # for block in out_gcode:
    #     if block.block_data.position.E is not None and block.block_data.position.E > 0:
    #         thumb_gcode_for_file.append(block.copy())

    if len(thumb_gcode_for_file) > 2: # Ensure there's enough data to generate a thumbnail
        try:
            file_thumbnail_img = gcode_thumbnails.Thumbnails.generate_thumbnail(thumb_gcode_for_file, render_scale=2, resolution=1000) # Doubled resolution
            if file_thumbnail_img.mode == 'RGBA':
                background = Image.new('RGB', file_thumbnail_img.size, (255, 255, 255))
                background.paste(file_thumbnail_img, mask=file_thumbnail_img.split()[3])
                file_thumbnail_img = background
        except Exception as e:
            print(f"Error generating file thumbnail for {name}: {e}")
            # Optionally save the error or a placeholder image
    else:
        print(f"Not enough extrusion data to generate file thumbnail for {name}.")

    # Generate Objects
    objects = {}
    # Tools.split returns a tuple (header, footer, pre_object_gcode, objects_dict, post_object_gcode)
    objects_dict = Tools.split(out_gcode)[3] # Get the dictionary of objects
    for obj_name, obj_gcode in objects_dict.items():
        # Ensure object name is valid and there's enough data for a thumbnail
        if obj_name and len(obj_gcode) > 2:
            try:
                obj_thumb_img = gcode_thumbnails.Thumbnails.generate_thumbnail(obj_gcode, render_scale=1, resolution=1000, draw_bounding_box=True) # Doubled resolution for Objects
                if obj_thumb_img.mode == 'RGBA':
                    background = Image.new('RGB', obj_thumb_img.size, (255, 255, 255))
                    background.paste(obj_thumb_img, mask=obj_thumb_img.split()[3])
                    obj_thumb_img = background
                objects[obj_name] = obj_thumb_img
            except Exception as e:
                print(f"Error generating thumbnail for object '{obj_name}' in {name}: {e}")
                # Optionally save a placeholder image for this object thumbnail
        elif obj_name:
            print(f"Not enough data to generate thumbnail for object '{obj_name}' in {name}.")

    # Return collected data
    return {
        'filename': name,
        'total_material': total_material,
        'file_thumbnail': file_thumbnail_img,
        'objects': objects
    }


def generate_report_image(data: list[dict], output_filename: str):
    """
    Generates a report image summarizing G-code files in a table format, with categories as rows.
    """
    if not data:
        print("No data to generate report.")
        return

    # Constants for layout and styling
    # CELL_PADDING = 10
    CELL_PADDING = 0
    # TEXT_LINE_HEIGHT will be calculated dynamically
    CATEGORY_COL_WIDTH = 200 # Fixed width for the category column
    FILE_THUMBNAIL_SIZE = 200
    OBJECT_THUMBNAIL_SIZE = 200
    LINE_SPACING = 5
    FONT_SIZE = 24 # Increased from 16
    OBJECT_NAME_FONT_SIZE = 10 # Smaller font size for object names
    OBJECT_THUMBNAIL_SPACING = 5  # Spacing between Objects vertically
    BOTTOM_MARGIN = 20 # Additional margin at the bottom of the report

    font = ImageFont.load_default(size=FONT_SIZE) # Load default font with specified size
    obj_name_font = ImageFont.load_default(size=OBJECT_NAME_FONT_SIZE)

    # Create a dummy image and draw object to calculate text dimensions
    dummy_img = Image.new('RGB', (1, 1), color=(255, 255, 255))
    draw = ImageDraw.Draw(dummy_img)

    # Calculate TEXT_LINE_HEIGHT dynamically based on new font size
    # Using 'Tg' to get a good average height for characters, including ascenders/descenders
    TEXT_LINE_HEIGHT = draw.textbbox((0, 0), "Tg", font=font)[3] - draw.textbbox((0, 0), "Tg", font=font)[1]
    # Ensure a minimum line height if the calculated one is too small
    if TEXT_LINE_HEIGHT < FONT_SIZE:
        TEXT_LINE_HEIGHT = FONT_SIZE + 4 # A bit more than font size for spacing

    OBJECT_NAME_TEXT_HEIGHT = draw.textbbox((0, 0), "Tg", font=obj_name_font)[3] - draw.textbbox((0, 0), "Tg", font=obj_name_font)[1]
    if OBJECT_NAME_TEXT_HEIGHT < OBJECT_NAME_FONT_SIZE:
        OBJECT_NAME_TEXT_HEIGHT = OBJECT_NAME_FONT_SIZE + 2 # A bit more than font size for spacing

    num_files = len(data)
    
    # Categories as rows
    categories = ["File Thumbnail", "Total Material", "Objects"]

    # Calculate column widths for each G-code file (excluding the category column)
    file_col_widths = []
    for item in data:
        max_content_width = 0
        
        # File Name
        filename_text = item['filename']
        max_content_width = max(max_content_width, draw.textbbox((0,0), filename_text, font=font)[2])

        # File Thumbnail (fixed size)
        max_content_width = max(max_content_width, FILE_THUMBNAIL_SIZE)

        # Total Material
        material_text = f"{item['total_material']:.4f} mm"
        max_content_width = max(max_content_width, draw.textbbox((0,0), material_text, font=font)[2])

        # Objects
        num_objs = len(item.get('objects', {}))
        # For vertical stacking, the width of the Objects will be fixed to OBJECT_THUMBNAIL_SIZE,
        # and the height will depend on the number of objects.
        max_content_width = max(max_content_width, OBJECT_THUMBNAIL_SIZE)
        
        file_col_widths.append(max_content_width + CELL_PADDING * 2) # Add padding

    # Determine maximum column width among all file columns
    max_file_content_width = max(file_col_widths) if file_col_widths else 0
    # Ensure all file columns are at least this wide for uniformity
    file_col_widths = [max(width, max_file_content_width) for width in file_col_widths]


    # Calculate total image width
    total_image_width = CATEGORY_COL_WIDTH + sum(file_col_widths) + CELL_PADDING * (num_files + 1) # Additional padding between columns and edges

    # Calculate row heights dynamically
    row_heights = {category: 0 for category in categories}

    # "File Name" row height
    row_heights["File Name"] = TEXT_LINE_HEIGHT + CELL_PADDING * 2

    # "File Thumbnail" row height
    row_heights["File Thumbnail"] = FILE_THUMBNAIL_SIZE + CELL_PADDING * 2

    # "Total Material" row height
    row_heights["Total Material"] = TEXT_LINE_HEIGHT + CELL_PADDING * 2

    # "Objects" row height (tallest object row across all files)
    max_objects_in_a_file = 0
    for item in data:
        max_objects_in_a_file = max(max_objects_in_a_file, len(item.get('objects', {})))
    
    # Each object now has a name and a thumbnail
    object_content_height_per_obj = OBJECT_NAME_TEXT_HEIGHT + LINE_SPACING + OBJECT_THUMBNAIL_SIZE
    object_row_total_height = max_objects_in_a_file * object_content_height_per_obj + \
                              max(0, max_objects_in_a_file - 1) * OBJECT_THUMBNAIL_SPACING + \
                              CELL_PADDING * 2
    row_heights["Objects"] = object_row_total_height


    # Calculate total image height
    total_image_height = sum(row_heights.values()) + CELL_PADDING * (len(categories) + 1) + BOTTOM_MARGIN

    # Create image
    img = Image.new('RGB', (total_image_width, total_image_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    current_y = CELL_PADDING

    # Draw headers (File Names as column headers)
    current_x = CATEGORY_COL_WIDTH + CELL_PADDING
    for i, item in enumerate(data):
        filename = item['filename']
        text_bbox = draw.textbbox((0,0), filename, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        
        # Center filename within its column
        text_x_pos = current_x + (file_col_widths[i] - text_width) / 2
        draw.text((text_x_pos, current_y), filename, fill=(0, 0, 0), font=font, stroke_width=1)
        current_x += file_col_widths[i] + CELL_PADDING

    # Update current_y for the content rows
    current_y += TEXT_LINE_HEIGHT + CELL_PADDING * 2

    # Draw content rows
    for category in categories:
        row_start_y = current_y
        row_height = row_heights[category]
        
        # Draw category label
        draw.text((CELL_PADDING, row_start_y + (row_height - TEXT_LINE_HEIGHT) / 2), category, fill=(0, 0, 0), font=font)
        
        current_x = CATEGORY_COL_WIDTH + CELL_PADDING
        for i, item in enumerate(data):
            # Draw content based on category
            if category == "File Thumbnail":
                file_thumbnail = item.get('file_thumbnail')
                if file_thumbnail:
                    thumbnail_img = file_thumbnail.resize((FILE_THUMBNAIL_SIZE, FILE_THUMBNAIL_SIZE))
                    # Center thumbnail horizontally and vertically within its cell
                    thumb_x_pos = current_x + (file_col_widths[i] - FILE_THUMBNAIL_SIZE) / 2
                    thumb_y_pos = row_start_y + (row_height - FILE_THUMBNAIL_SIZE) / 2
                    img.paste(thumbnail_img, (int(thumb_x_pos), int(thumb_y_pos)))
            elif category == "Total Material":
                total_material = item['total_material']
                material_text = f"{total_material:.4f} mm"
                text_bbox = draw.textbbox((0,0), material_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                
                # Center text horizontally and vertically within its cell
                text_x_pos = current_x + (file_col_widths[i] - text_width) / 2
                text_y_pos = row_start_y + (row_height - TEXT_LINE_HEIGHT) / 2
                draw.text((int(text_x_pos), int(text_y_pos)), material_text, fill=(0, 0, 0), font=font)
            elif category == "Objects":
                objects = item.get('objects', {})
                # Center Objects horizontally within their column
                initial_obj_x_pos = current_x + (file_col_widths[i] - OBJECT_THUMBNAIL_SIZE) / 2
                obj_y_offset = row_start_y + CELL_PADDING
                
                for obj_name, obj_thumb_img in objects.items():
                    # Draw object name
                    obj_name_bbox = draw.textbbox((0,0), obj_name, font=obj_name_font)
                    obj_name_width = obj_name_bbox[2] - obj_name_bbox[0]
                    obj_name_x_pos = initial_obj_x_pos + (OBJECT_THUMBNAIL_SIZE - obj_name_width) / 2
                    draw.text((int(obj_name_x_pos), int(obj_y_offset)), obj_name, fill=(0, 0, 0), font=obj_name_font)
                    
                    obj_y_offset += OBJECT_NAME_TEXT_HEIGHT + LINE_SPACING # Space for text and a line space

                    resized_obj_thumb = obj_thumb_img.resize((OBJECT_THUMBNAIL_SIZE, OBJECT_THUMBNAIL_SIZE))
                    img.paste(resized_obj_thumb, (int(initial_obj_x_pos), int(obj_y_offset)))
                    obj_y_offset += OBJECT_THUMBNAIL_SIZE + OBJECT_THUMBNAIL_SPACING # Space for thumbnail and spacing for next object
            
            current_x += file_col_widths[i] + CELL_PADDING
        
        current_y += row_height + CELL_PADDING * 2 # Update y for the next row

    # Save the image
    img.save(output_filename)
    print(f"Report image saved successfully to {output_filename}")


def main():
    global processed_data
    
    # Path to gcodes/ directory
    subprocess.call(['git', 'clone', 'https://github.com/Matszwe02/GcodeTools_gcodes'], cwd=os.path.dirname(__file__))
    gcodes_dir = os.path.join(os.path.dirname(__file__), 'GcodeTools_gcodes')
    paths = os.listdir(gcodes_dir)
    
    list_of_gcodes = [path.removesuffix('.gcode') for path in paths if path.endswith('.gcode')]
    
    total = len(list_of_gcodes)
    
    if total == 0:
        print("No G-code files found.")
        return

    print(f'Analising {total} gcodes')
    
    num_processes = min(os.cpu_count() or 1, total) # Use all available CPU cores, up to total files
    # num_processes = 1

    print(f"Using {num_processes} parallel processes.")

    futures = {}
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        for gcode_id, gcode_name in enumerate(list_of_gcodes):
            futures[executor.submit(process_gcode, gcode_name, gcode_id)] = gcode_name
        
        for future in as_completed(futures):
            gcode_name = futures[future]
            # try:
            result_data = future.result() # Get the dictionary returned by process_gcode
            if result_data:
                processed_data.append(result_data) # Append the dictionary to our list
            print(f'                GCODE PROCESSING: finished processing {len(processed_data)} out of {total} for {gcode_name}')
            # except Exception as exc:
            #     print(f'{gcode_name} generated an exception: {exc}')

    print('Finished processing G-codes!')
    
    # --- Call the report generation function ---
    if processed_data:
        generate_report_image(processed_data, os.path.join(os.path.dirname(__file__), 'gcode_report.png'))
    else:
        print("No G-code data processed or an error occurred. Report image not generated.")


if __name__ == '__main__':
    start_time = time.time()
    main()
    end_time = time.time()

    execution_time = end_time - start_time
    print(f"\nExecution time of generate_report.py: {execution_time:.1f} seconds")
