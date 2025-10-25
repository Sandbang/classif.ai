import anthropic
import base64
import os
import json
import sys
import textwrap
import math
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont  # <-- New imports

load_dotenv()  # <-- Reads your .env file and loads all variables

# --- Configuration & Environment Variables ---

# 1. Get API Key (Required)
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    print("Error: ANTHROPIC_API_KEY environment variable not set in .env file or environment.")
    print("Please set the variable before running the script.")
    sys.exit(1)

# 2. Get Model Name (Optional, with fallback)
DEFAULT_MODEL = "claude-3-5-sonnet-20240620"
MODEL_NAME = os.environ.get("ANTHROPIC_MODEL_NAME", DEFAULT_MODEL)

# Initialize the Anthropic client
client = anthropic.Anthropic(api_key=API_KEY)

# --- Helper Functions (Old) ---

def get_image_media_type(image_path):
    """Determines the media type based on the file extension."""
    extension = os.path.splitext(image_path)[1].lower()
    if extension in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif extension == ".png":
        return "image/png"
    elif extension == ".webp":
        return "image/webp"
    else:
        raise ValueError(f"Unsupported image format: {extension}")

def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Image file not found at '{image_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading image file: {e}")
        sys.exit(1)

# --- Helper Functions (New) ---

def load_layout_data(layout_path):
    """
    Loads the layout JSON and converts it to a dictionary
    mapping number -> box coordinates.
    """
    try:
        with open(layout_path, 'r') as f:
            layout_list = json.load(f)
            
        # Convert list of objects to a more efficient lookup dictionary
        layout_map = {item['number']: item['box'] for item in layout_list}
        return layout_map
        
    except FileNotFoundError:
        print(f"Error: Layout file not found at '{layout_path}'")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{layout_path}'. Check for syntax errors.")
        sys.exit(1)
    except KeyError:
        print("Error: Layout JSON has incorrect format. Expected list of {'number': n, 'box': [x,y,w,h]}")
        sys.exit(1)

def draw_arrow(draw, start, end, color='red', width=3, head_length=15):
    """Draws a line with an arrowhead at the end."""
    # Draw the line
    draw.line([start, end], fill=color, width=width)
    
    # Calculate arrowhead geometry
    try:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
    except ZeroDivisionError:
        return # Cannot draw arrowhead if start == end
        
    # Angle for the two barbs
    angle_p_30 = angle + math.radians(30)
    angle_m_30 = angle - math.radians(30)
    
    # Points for the arrowhead polygon
    p1_x = end[0] - head_length * math.cos(angle_p_30)
    p1_y = end[1] - head_length * math.sin(angle_p_30)
    
    p2_x = end[0] - head_length * math.cos(angle_m_30)
    p2_y = end[1] - head_length * math.sin(angle_m_30)
    
    # Draw the polygon
    draw.polygon([end, (p1_x, p1_y), (p2_x, p2_y)], fill=color)

def annotate_image(image_path, layout_map, errors_list):
    """
    Opens an image and draws error bubbles and arrows based on
    the layout map and the errors from Claude.
    """
    try:
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return

    # Try to load a good font, with fallbacks
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            print("Warning: DejaVuSans.ttf or arial.ttf not found. Using default font.")
            # Use default font, which is small but guaranteed to work
            font = ImageFont.load_default()

    # --- Constants for drawing ---
    BUBBLE_PADDING = 10
    ARROW_GAP = 20
    TEXT_WRAP_WIDTH = 45
    BUBBLE_COLOR = 'red'
    
    print("Annotating image...")

    for error in errors_list:
        line_number = error.get('number')
        error_text = error.get('error')

        if not line_number or not error_text:
            print(f"Skipping invalid error entry: {error}")
            continue

        # Find the box coordinates from our layout map
        if line_number not in layout_map:
            print(f"Warning: No layout box found for error number {line_number}. Skipping.")
            continue
            
        box = layout_map[line_number]
        x, y, w, h = box

        # --- 1. Define Target ---
        # Point the arrow at the middle-right of the error box
        target_point = (x + w, y + h // 2)

        # --- 2. Prepare Text Bubble ---
        wrapper = textwrap.TextWrapper(width=TEXT_WRAP_WIDTH)
        wrapped_text = wrapper.fill(text=error_text)
        
        # Get text size
        try:
            # Use textbbox for modern Pillow versions
            text_box_dims = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
            text_width = text_box_dims[2] - text_box_dims[0]
            text_height = text_box_dims[3] - text_box_dims[1]
        except AttributeError:
            # Fallback for older Pillow versions
            text_width, text_height = draw.multiline_textsize(wrapped_text, font=font)

        bubble_width = text_width + (BUBBLE_PADDING * 2)
        bubble_height = text_height + (BUBBLE_PADDING * 2)

        # --- 3. Position Bubble ---
        # Place bubble to the right of the target, with a gap
        bubble_x = target_point[0] + ARROW_GAP
        bubble_y = target_point[1] - (bubble_height // 2) # Center vertically

        # Adjust if bubble goes off-screen
        if bubble_x + bubble_width > image.width:
            # Place it to the left instead
            bubble_x = x - bubble_width - ARROW_GAP
        if bubble_y < 0:
            bubble_y = 10 # Pin to top
        if bubble_y + bubble_height > image.height:
            bubble_y = image.height - bubble_height - 10 # Pin to bottom

        bubble_rect = [bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height]
        text_origin = (bubble_x + BUBBLE_PADDING, bubble_y + BUBBLE_PADDING)

        # --- 4. Draw Bubble & Text ---
        draw.rectangle(bubble_rect, outline=BUBBLE_COLOR, fill='white', width=2)
        draw.multiline_text(text_origin, wrapped_text, fill='black', font=font)
        
        # --- 5. Define Arrow Start Point ---
        # Find closest point on bubble to the target
        if bubble_x > target_point[0]: # Bubble is on the right
            arrow_start = (bubble_x, bubble_y + bubble_height // 2)
        else: # Bubble is on the left
            arrow_start = (bubble_x + bubble_width, bubble_y + bubble_height // 2)

        # --- 6. Draw Arrow ---
        draw_arrow(draw, arrow_start, target_point, color=BUBBLE_COLOR)

    # --- 7. Save Image ---
    # Create a new filename, e.g., "annotated_image_d86a7d.jpg"
    base = os.path.basename(image_path)
    name, ext = os.path.splitext(base)
    save_path = f"annotated_{name}{ext}"
    
    image.save(save_path)
    print(f"\nSuccessfully created annotated image: {save_path}")

# --- Main API Call Function ---

def grade_proof_image(image_path):
    """
    Sends an image of a proof to the Claude API for grading and returns a
    JSON object with the grade and errors.
    """
    
    media_type = get_image_media_type(image_path)
    image_data = encode_image_to_base64(image_path)
    system_prompt = """
    You are an AI assistant specializing in grading undergraduate mathematics, specifically topology and real analysis.
    You will be given an image of a handwritten proof. The image is annotated with red numbers on the left, each corresponding to a line or block of text.
    Your task is to analyze the proof for logical errors, mathematical inaccuracies, or incomplete justifications.
    
    You MUST return your response *only* as a single, valid JSON object. 
    Do not include any text, pleasantries, or markdown formatting (like ```json) before or after the JSON object.
    
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
    
    If no errors are found, return an empty 'errors' list and an appropriate 'total_grade'.
    Base the 'total_grade' on the number and severity of any errors found.
    """
    user_message_content = [
        {
            "type": "image",
            "source": { "type": "base64", "media_type": media_type, "data": image_data, },
        },
        {
            "type": "text",
            "text": "Please grade this proof. Identify all errors, referencing the red line number for each. Provide a total grade. Return the result *only* in the specified JSON format."
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

    except anthropic.APIError as e:
        print(f"\n--- Anthropic API Error ---")
        print(f"Status Code: {e.status_code}\nResponse: {e.response}")
        return None
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return None

# --- Script Execution ---

if __name__ == "__main__":
    if len(sys.argv) != 3: # <-- Updated check
        print("Usage: python grade_proof.py <path_to_image> <path_to_layout_json>")
        sys.exit(1)
        
    image_file_path = sys.argv[1]
    layout_file_path = sys.argv[2] # <-- New argument
    
    # 1. Load layout data
    layout_map = load_layout_data(layout_file_path)
    
    # 2. Get grading from Claude
    grading_result = grade_proof_image(image_path=image_file_path)
    
    if grading_result:
        print("\n--- Grading Result (JSON) ---")
        print(json.dumps(grading_result, indent=2))
        
        errors = grading_result.get('errors', [])
        if not errors:
            print("\nNo errors found by AI.")
        else:
            # 3. Create the annotated image
            annotate_image(
                image_path=image_file_path,
                layout_map=layout_map,
                errors_list=errors
            )