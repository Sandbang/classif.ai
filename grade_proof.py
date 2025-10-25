# grade_proof.py
import anthropic
import base64
import os
import json
import sys
import textwrap
import math
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import cv2  # <-- New import
import numpy as np # <-- New import

# --- Our Other Script ---
import find_text_lines # <-- NEW: Import your script

load_dotenv()  # Reads your .env file

# --- Configuration & Environment Variables ---
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    print("Error: ANTHROPIC_API_KEY environment variable not set.")
    sys.exit(1)

DEFAULT_MODEL = "claude-3-5-sonnet-20240620"
MODEL_NAME = os.environ.get("ANTHROPIC_MODEL_NAME", DEFAULT_MODEL)

client = anthropic.Anthropic(api_key=API_KEY)

# --- Helper Functions (Image Manipulation) ---

def draw_arrow(draw, start, end, color='red', width=3, head_length=15):
    """Draws a line with an arrowhead at the end."""
    draw.line([start, end], fill=color, width=width)
    try:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
    except ZeroDivisionError:
        return
        
    angle_p_30 = angle + math.radians(30)
    angle_m_30 = angle - math.radians(30)
    
    p1_x = end[0] - head_length * math.cos(angle_p_30)
    p1_y = end[1] - head_length * math.sin(angle_p_30)
    p2_x = end[0] - head_length * math.cos(angle_m_30)
    p2_y = end[1] - head_length * math.sin(angle_m_30)
    
    draw.polygon([end, (p1_x, p1_y), (p2_x, p2_y)], fill=color)

def annotate_image(image_array, layout_map, errors_list, original_image_path):
    """
    MODIFIED: Takes the numpy image array and draws error bubbles on it.
    Saves a new file based on the original_image_path.
    """
    try:
        # --- MODIFIED: Convert OpenCV BGR array to PIL RGB Image ---
        # OpenCV uses BGR, Pillow uses RGB. We must convert.
        image = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(image)
        # -----------------------------------------------------------
    except Exception as e:
        print(f"Error creating image from array: {e}")
        return

    # Font loading (unchanged)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            print("Warning: DejaVuSans.ttf or arial.ttf not found. Using default font.")
            font = ImageFont.load_default()

    # Drawing constants (unchanged)
    BUBBLE_PADDING = 10
    ARROW_GAP = 20
    TEXT_WRAP_WIDTH = 45
    BUBBLE_COLOR = 'red'
    
    print("Annotating image...")

    for error in errors_list:
        line_number = error.get('number')
        error_text = error.get('error')

        if not line_number or not error_text:
            continue

        if line_number not in layout_map:
            print(f"Warning: No layout box found for error number {line_number}. Skipping.")
            continue
            
        box = layout_map[line_number]
        x, y, w, h = box

        # 1. Define Target (Unchanged)
        target_point = (x + w, y + h // 2)

        # 2. Prepare Text Bubble (Unchanged)
        wrapper = textwrap.TextWrapper(width=TEXT_WRAP_WIDTH)
        wrapped_text = wrapper.fill(text=error_text)
        
        try:
            text_box_dims = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
            text_width = text_box_dims[2] - text_box_dims[0]
            text_height = text_box_dims[3] - text_box_dims[1]
        except AttributeError:
            text_width, text_height = draw.multiline_textsize(wrapped_text, font=font)

        bubble_width = text_width + (BUBBLE_PADDING * 2)
        bubble_height = text_height + (BUBBLE_PADDING * 2)

        # 3. Position Bubble (Unchanged)
        bubble_x = target_point[0] + ARROW_GAP
        bubble_y = target_point[1] - (bubble_height // 2)

        if bubble_x + bubble_width > image.width:
            bubble_x = x - bubble_width - ARROW_GAP
        if bubble_y < 0:
            bubble_y = 10
        if bubble_y + bubble_height > image.height:
            bubble_y = image.height - bubble_height - 10

        bubble_rect = [bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height]
        text_origin = (bubble_x + BUBBLE_PADDING, bubble_y + BUBBLE_PADDING)

        # 4. Draw Bubble & Text (Unchanged)
        draw.rectangle(bubble_rect, outline=BUBBLE_COLOR, fill='white', width=2)
        draw.multiline_text(text_origin, wrapped_text, fill='black', font=font)
        
        # 5. Define Arrow Start Point (Unchanged)
        if bubble_x > target_point[0]:
            arrow_start = (bubble_x, bubble_y + bubble_height // 2)
        else:
            arrow_start = (bubble_x + bubble_width, bubble_y + bubble_height // 2)

        # 6. Draw Arrow (Unchanged)
        draw_arrow(draw, arrow_start, target_point, color=BUBBLE_COLOR)

    # --- 7. Save Image (MODIFIED) ---
    # Use the *original* path to create a clean name
    base = os.path.basename(original_image_path)
    name, ext = os.path.splitext(base)
    save_path = f"annotated_{name}.jpg" # <-- Cleaner output name
    
    image.save(save_path, "JPEG") # Specify format for clarity
    print(f"\nSuccessfully created annotated image: {save_path}")

# --- Main API Call Function ---

def grade_proof_image(image_array):
    """
    MODIFIED: Sends a numpy image array to the Claude API for grading.
    """
    
    # --- MODIFIED: Encode numpy array to base64 ---
    try:
        # Encode the image as JPEG in memory
        _, buffer = cv2.imencode('.jpg', image_array)
        # Convert the buffer to a base64 string
        image_data = base64.b64encode(buffer).decode('utf-8')
        media_type = "image/jpeg"
    except Exception as e:
        print(f"Error encoding image array: {e}")
        return None
    # ----------------------------------------------
    
    system_prompt = """
    You are an AI assistant specializing in grading undergraduate mathematics...
    (Unchanged system prompt)
    ...
    The JSON object must have the following exact structure:
    {
      "total_grade": "string (e.g., 'A', 'B-', 'C+')",
      "errors": [
        {
          "number": "integer (the red number for the line with the error)",
          "error": "string (a concise description of the error)"
        }
      ]
    }
    ...
    """
    user_message_content = [
        {
            "type": "image",
            "source": { "type": "base64", "media_type": media_type, "data": image_data, },
        },
        {
            "type": "text",
            "text": "Please grade this proof. The image is annotated with red numbers. Identify all errors, referencing the red line number for each. Provide a total grade. Return *only* JSON."
        }
    ]

    print(f"Sending request to Claude (Model: {MODEL_NAME})...")
    try:
        response = client.messages.create(
            model=MODEL_NAME, max_tokens=2048, system=system_prompt,
            messages=[{"role": "user", "content": user_message_content}]
        )
        raw_response_text = response.content[0].text
        
        if raw_response_text.startswith("```json"):
            raw_response_text = raw_response_text[7:-3].strip()

        try:
            result_json = json.loads(raw_response_text)
            return result_json
        except json.JSONDecodeError:
            print("\n--- Error: Failed to decode JSON from Claude's response ---")
            print("Raw response received:")
            print(raw_response_text)
            return None
    except Exception as e:
        print(f"\nAn error occurred with the API: {e}")
        return None

# --- Script Execution (MODIFIED) ---

if __name__ == "__main__":
    if len(sys.argv) != 2: # <-- Updated: Only one argument
        print("Usage: python grade_proof.py <path_to_image>")
        sys.exit(1)
        
    image_file_path = sys.argv[1] # This is the *original* image
    
    # --- 1. NEW: Call OpenCV script ---
    print(f"--- Running text line detection on {image_file_path} ---")
    # Call the imported function to get data in memory
    boxed_image_array, layout_data_list = find_text_lines.find_text_lines(image_file_path)
    
    # Handle failure from the OpenCV script
    if boxed_image_array is None or layout_data_list is None:
        print("Error: Text line detection failed. Exiting.")
        sys.exit(1)
    
    print("--- Text detection successful ---")

    # --- 2. Get grading from Claude ---
    # Pass the numpy image array directly
    grading_result = grade_proof_image(image_array=boxed_image_array)
    
    if grading_result:
        print("\n--- Grading Result (JSON) ---")
        print(json.dumps(grading_result, indent=2))
        
        errors = grading_result.get('errors', [])
        if not errors:
            print("\nNo errors found by AI.")
        else:
            # --- 3. NEW: Prepare Layout Map from in-memory list ---
            try:
                # This replaces the old load_layout_data() function
                layout_map = {item['number']: item['box'] for item in layout_data_list}
            except KeyError:
                print("Error: Layout data from find_text_lines has incorrect format.")
                sys.exit(1)

            # --- 4. Create the annotated image ---
            annotate_image(
                image_array=boxed_image_array,
                layout_map=layout_map,
                errors_list=errors,
                original_image_path=image_file_path # Pass for naming the final file
            )