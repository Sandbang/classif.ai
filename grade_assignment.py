import anthropic
import base64
import json
import os
import io
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Load environment variables (your API key)
load_dotenv()

# --- 1. Configuration ---

# The Anthropic API client
try:
    client = anthropic.Anthropic()
except anthropic.AuthenticationError as e:
    print("Authentication Error: Please check your ANTHROPIC_API_KEY in the .env file.")
    print(f"Details: {e}")
    exit()

# The image you want to grade
INPUT_IMAGE_PATH = "assignment.jpg"
OUTPUT_IMAGE_PATH = "graded_assignment.png"

# This model is working for your account.
MODEL_NAME = "claude-3-haiku-20240307"

# Maximum file size allowed by the API (5 MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 

# --- 2. The System Prompt (The "Brain" Configuration) ---

SYSTEM_PROMPT = """
You are an expert Teaching Assistant for a university-level mathematics course.
Your task is to grade a handwritten assignment provided as an image.
Analyze the image, identify the question, and evaluate the student's proof.

You must identify every conceptual error, logical flaw, or notational mistake.
For each error, you must provide:
1.  A `bounding_box` as a JSON array of four numbers [x_min, y_min, x_max, y_max]
    that precisely encloses the error on the original image.
2.  A `comment` string that provides concise, constructive feedback.

You MUST return your response as a single, valid JSON object.
Do not write *any* text outside of the JSON object.

The JSON object must follow this exact schema:
{
  "overall_grade": "A score, e.g., '8/10'",
  "summary": "A 2-3 sentence summary of the student's performance.",
  "errors": [
    {
      "bounding_box": [x_min, y_min, x_max, y_max],
      "comment": "Your constructive feedback for this specific error."
    }
  ]
}
"""

# --- 3. Helper Functions ---

def encode_image_to_base64(image_path):
    """
    Converts an image to base64, compressing and resizing as needed
    to stay under the 5MB API limit.
    """
    try:
        with Image.open(image_path) as img:
            # Fix orientation issues from phone cameras
            img = ImageOps.exif_transpose(img)
            
            # Handle transparency (e.g., from PNGs) by converting to RGB
            if img.mode == 'RGBA' or img.mode == 'P':
                print("Note: Converting transparent image to RGB for JPEG compression.")
                img = img.convert('RGB')

            # Save to an in-memory buffer *first* using high-quality JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90, optimize=True)
            binary_data = buffer.getvalue()
            
            # Check size *after* initial compression
            file_size = len(binary_data)
            media_type = "image/jpeg"

            # If it's *still* too big, resize and re-compress
            if file_size > MAX_FILE_SIZE_BYTES:
                print(f"Warning: Image size after compression ({file_size / (1024*1024):.2f} MB) still exceeds 5 MB limit.")
                print("Attempting to resize...")
                
                # Clear the buffer
                buffer.seek(0)
                buffer.truncate(0)
                
                # Resize to a max dimension of 2048px, maintaining aspect ratio
                max_dim = 2048
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
                # Save again with slightly lower quality
                img.save(buffer, format="JPEG", quality=80, optimize=True)
                binary_data = buffer.getvalue()
                
                new_size = len(binary_data)
                if new_size > MAX_FILE_SIZE_BYTES:
                    print(f"Error: Resize failed. Final size {new_size / (1024*1024):.2f} MB is still too large.")
                    print("Please manually resize your image to be under 5 MB.")
                    return None, None
                
                print(f"Successfully resized and compressed to {new_size / (1024*1024):.2f} MB.")
            else:
                print(f"Image successfully compressed to {file_size / (1024*1024):.2f} MB. Sending to API.")

            # Encode the final binary data to base64
            base64_encoded_data = base64.b64encode(binary_data)
            base64_string = base64_encoded_data.decode('utf-8')
            return base64_string, media_type

    except FileNotFoundError:
        print(f"Error: Input image file not found at '{image_path}'")
        print("Please create an 'assignment.jpg' file in the same directory.")
        return None, None
    except Exception as e:
        print(f"Error encoding or resizing image: {e}")
        return None, None

def annotate_image(image_path, output_path, errors):
    """Draws feedback boxes and comments on the original image."""
    try:
        # Open with Image.open and apply EXIF transpose to fix rotation
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA")

            # Create a drawing context
            draw = ImageDraw.Draw(img)
            
            # Create a separate overlay for semi-transparent boxes
            overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            # --- FONT & SIZE CONFIGURATION ---
            FONT_SIZE = 40  # Adjust as needed, 40 is a good starting point
            COMMENT_PADDING = 15 # Padding around text and from bounding box
            LINE_SPACING = 5 # Pixels between lines of wrapped text
            MAX_COMMENT_WIDTH_RATIO = 0.4 # Comment can be up to 40% of image width

            try:
                # Use absolute path for Arial for robustness
                # Please ensure 'arial.ttf' (lowercase) is the correct filename on your system
                # If not, try "C:/Windows/Fonts/arial.ttf" or "C:\\Windows\\Fonts\\arial.ttf"
                font = ImageFont.truetype("arial.ttf", size=FONT_SIZE)
                print("Arial font loaded successfully.")
            except IOError:
                print("--- FONT WARNING ---")
                print("Font 'arial.ttf' not found at expected path or by name.")
                print("Attempting to load default Pillow font (which cannot be scaled).")
                print("For best results, ensure 'arial.ttf' is installed and accessible,")
                print("or specify a full path like 'C:/Windows/Fonts/arial.ttf'.")
                print("----------------------")
                font = ImageFont.load_default() # Fallback, size parameter might be ignored

            img_width, img_height = img.size
            max_comment_width = int(img_width * MAX_COMMENT_WIDTH_RATIO)
            
            # Keep track of occupied areas to prevent comment overlap
            occupied_regions = []

            for error in errors:
                box = [int(coord) for coord in error['bounding_box']]
                comment_text = error['comment']

                # 1. Draw the semi-transparent error box on the overlay
                draw_overlay.rectangle(box, outline="red", width=5, fill=(255, 0, 0, 64))
                
                # Calculate box center for leader line
                box_center_x = box[0] + (box[2] - box[0]) // 2
                box_center_y = box[1] + (box[3] - box[1]) // 2

                # 2. Wrap the comment text
                wrapped_comment_lines = []
                current_line = []
                current_line_width = 0

                for word in comment_text.split():
                    word_width = font.getbbox(word)[2] - font.getbbox(word)[0] # Get text width
                    space_width = font.getbbox(" ")[2] - font.getbbox(" ")[0]

                    if current_line_width + word_width + space_width > max_comment_width and current_line:
                        wrapped_comment_lines.append(" ".join(current_line))
                        current_line = [word]
                        current_line_width = word_width
                    else:
                        current_line.append(word)
                        current_line_width += (word_width + space_width)
                if current_line:
                    wrapped_comment_lines.append(" ".join(current_line))
                
                # Calculate total wrapped text height and width
                total_text_height = 0
                max_wrapped_line_width = 0
                for line in wrapped_comment_lines:
                    line_bbox = font.getbbox(line)
                    line_height = line_bbox[3] - line_bbox[1]
                    total_text_height += line_height
                    max_wrapped_line_width = max(max_wrapped_line_width, line_bbox[2] - line_bbox[0])
                total_text_height += (len(wrapped_comment_lines) - 1) * LINE_SPACING # Add line spacing

                # --- Dynamic Text Placement ---
                # Attempt to place: Right -> Below -> Above
                
                # Initial attempt: To the right of the bounding box
                comment_rect_x1 = box[2] + COMMENT_PADDING
                comment_rect_y1 = box_center_y - (total_text_height // 2)

                # If right placement goes off screen, or is too far left relative to box
                if comment_rect_x1 + max_wrapped_line_width + COMMENT_PADDING * 2 > img_width or \
                   comment_rect_x1 < box[2] + COMMENT_PADDING: # Ensure it's not starting directly on the box
                    
                    # Second attempt: Below the bounding box
                    comment_rect_x1 = box[0] # Align with left of box
                    comment_rect_y1 = box[3] + COMMENT_PADDING # Below the box
                    
                    # If below placement goes off screen or below the image
                    if comment_rect_y1 + total_text_height + COMMENT_PADDING * 2 > img_height:
                        # Third attempt: Above the bounding box
                        comment_rect_x1 = box[0] # Align with left of box
                        comment_rect_y1 = box[1] - total_text_height - COMMENT_PADDING # Above the box
                        
                        # If above placement also off screen (highly unlikely)
                        if comment_rect_y1 < 0:
                            comment_rect_y1 = 0 # Just put it at the top

                # Calculate the full rectangle for the comment (including padding)
                comment_bg_x1 = comment_rect_x1 - COMMENT_PADDING
                comment_bg_y1 = comment_rect_y1 - COMMENT_PADDING
                comment_bg_x2 = comment_rect_x1 + max_wrapped_line_width + COMMENT_PADDING
                comment_bg_y2 = comment_rect_y1 + total_text_height + COMMENT_PADDING
                
                # Adjust if it goes off the right edge (last resort)
                if comment_bg_x2 > img_width:
                    offset = comment_bg_x2 - img_width
                    comment_bg_x1 -= offset
                    comment_bg_x2 -= offset
                    comment_rect_x1 -= offset
                
                # Adjust if it goes off the top edge (last resort)
                if comment_bg_y1 < 0:
                    offset = 0 - comment_bg_y1
                    comment_bg_y1 += offset
                    comment_bg_y2 += offset
                    comment_rect_y1 += offset
                
                # 3. Draw the comment text on the main image
                draw.rectangle((comment_bg_x1, comment_bg_y1, comment_bg_x2, comment_bg_y2), fill=(255, 255, 220, 220)) # Light yellow bg with transparency

                current_text_y = comment_rect_y1
                for line in wrapped_comment_lines:
                    draw.text((comment_rect_x1, current_text_y), line, fill="red", font=font)
                    line_bbox = font.getbbox(line)
                    line_height = line_bbox[3] - line_bbox[1]
                    current_text_y += line_height + LINE_SPACING
                
                # 4. Draw a leader line from the box to the start of the comment
                # Line goes from the appropriate edge of the error box to the closest edge of the comment box
                
                line_start_x, line_start_y = box_center_x, box_center_y
                line_end_x, line_end_y = comment_rect_x1, comment_rect_y1 + (total_text_height // 2) # Center of the comment text block

                # Adjust leader line start point to be from the edge of the box closest to the comment
                if comment_rect_x1 > box[2]: # Comment is to the right
                    line_start_x = box[2]
                elif comment_bg_x2 < box[0]: # Comment is to the left (unlikely with current logic)
                    line_start_x = box[0]
                elif comment_rect_y1 > box[3]: # Comment is below
                    line_start_y = box[3]
                    line_start_x = box_center_x
                    line_end_x = comment_rect_x1 + (max_wrapped_line_width // 2)
                    line_end_y = comment_rect_y1
                elif comment_bg_y2 < box[1]: # Comment is above
                    line_start_y = box[1]
                    line_start_x = box_center_x
                    line_end_x = comment_rect_x1 + (max_wrapped_line_width // 2)
                    line_end_y = comment_bg_y2 # Bottom of comment background

                draw.line([ (line_start_x, line_start_y), (line_end_x, line_end_y) ], fill="red", width=3)


            # Composite the overlay onto the main image
            img = Image.alpha_composite(img, overlay)

            # Convert back to RGB before saving as PNG/JPEG
            img = img.convert("RGB")
            img.save(output_path)
            print(f"\nSuccessfully saved annotated image to '{output_path}'")

    except Exception as e:
        print(f"Error annotating image: {e}")


# --- 4. Main Execution ---

def main():
    print(f"Loading image from '{INPUT_IMAGE_PATH}'...")
    base64_string, media_type = encode_image_to_base64(INPUT_IMAGE_PATH)
    
    if not base64_string:
        return

    print("Sending request to Claude API. This may take a moment...")
    
    try:
        # Send the request to the API
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_string,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Please grade this assignment."
                        }
                    ],
                }
            ],
        )

        # Extract the JSON text from the response
        json_response_text = response.content[0].text
        
        # Parse the JSON
        try:
            grading_data = json.loads(json_response_text)
        except json.JSONDecodeError:
            print("\n--- API Response (Error) ---")
            print("Error: Claude did not return valid JSON. Response:")
            print(json_response_text)
            return

        print("\n--- Grading Complete ---")
        print(f"Grade: {grading_data.get('overall_grade', 'N/A')}")
        print(f"Summary: {grading_data.get('summary', 'N/A')}")

        errors = grading_data.get('errors', [])
        if errors:
            print(f"\nFound {len(errors)} errors. Annotating image...")
            annotate_image(INPUT_IMAGE_PATH, OUTPUT_IMAGE_PATH, errors)
        else:
            print("No errors found. Well done!")

    except anthropic.APIError as e:
        print(f"An error occurred with the Anthropic API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if not os.path.exists(INPUT_IMAGE_PATH):
        print(f"Error: Input file '{INPUT_IMAGE_PATH}' not found.")
        print("Please create an image file with this name and run the script again.")
    else:
        main()