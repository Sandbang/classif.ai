# find_text_lines.py
import cv2
import numpy as np
import argparse
import sys
import os
import json

# --- Configuration (Unchanged) ---
KERNEL_WIDTH_FACTOR = 4
KERNEL_HEIGHT_FACTOR = 0.4
MIN_LINE_HEIGHT_FACTOR = 0.5
MIN_LINE_WIDTH_FACTOR = 2
OPENING_KERNEL_SIZE = (3, 3) 
ADAPTIVE_BLOCK_SIZE = 15
ADAPTIVE_C = 7
GRID_LINE_KERNEL_LENGTH = 30
# -------------------------------

def find_text_lines(image_path):
    """
    Finds, boxes, and numbers text lines.
    Returns the annotated image array (numpy) and the box data (list).
    """
    
    # 1. Load the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        return None, None # <-- MODIFIED: Return None instead of exit

    output = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 3. Adaptive Threshold
    thresh = cv2.adaptiveThreshold(gray, 255, 
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 
                                  ADAPTIVE_BLOCK_SIZE, 
                                  ADAPTIVE_C)

    # 4. REMOVE GRID LINES (Unchanged)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, 
                                                 (GRID_LINE_KERNEL_LENGTH, 1))
    detected_horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, 
                                                  horizontal_kernel, iterations=2)
    detected_horizontal_lines = cv2.dilate(detected_horizontal_lines, None, iterations=2)

    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, 
                                               (1, GRID_LINE_KERNEL_LENGTH))
    detected_vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, 
                                                vertical_kernel, iterations=2)
    detected_vertical_lines = cv2.dilate(detected_vertical_lines, None, iterations=2)

    grid_mask = detected_horizontal_lines + detected_vertical_lines
    thresh_no_grid = cv2.subtract(thresh, grid_mask)

    # 5. DE-NOISE (Unchanged)
    opening_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, OPENING_KERNEL_SIZE)
    cleaned_thresh = cv2.morphologyEx(thresh_no_grid, cv2.MORPH_OPEN, 
                                      opening_kernel, iterations=1)
    
    # PASS 1: ANALYZE TEXT SIZE (Unchanged)
    letter_contours, _ = cv2.findContours(cleaned_thresh.copy(), cv2.RETR_EXTERNAL, 
                                          cv2.CHAIN_APPROX_SIMPLE)
    heights = []
    for contour in letter_contours:
        (x, y, w, h) = cv2.boundingRect(contour)
        if h > 5 and h < 200 and w < 200:
            heights.append(h)

    if not heights:
        print("No text-like contours found.")
        return None, None # <-- MODIFIED: Return None

    median_height = np.median(heights)
    
    if np.isnan(median_height):
        print("Could not determine a median height. Exiting.")
        return None, None # <-- MODIFIED: Return None

    print(f"Detected median text height: {median_height:.2f} pixels")

    # PASS 2: FIND ALL LINE FRAGMENTS (Unchanged)
    MIN_CONTOUR_HEIGHT = int(median_height * MIN_LINE_HEIGHT_FACTOR)
    MIN_CONTOUR_WIDTH = int(median_height * MIN_LINE_WIDTH_FACTOR)
    print(f"Using Dynamic Filters: min_h={MIN_CONTOUR_HEIGHT}, min_w={MIN_CONTOUR_WIDTH}")

    k_height = int(max(1, median_height * KERNEL_HEIGHT_FACTOR))
    k_width = int(max(1, median_height * KERNEL_WIDTH_FACTOR)) 
    KERNEL_SIZE = (k_width, k_height)
    
    print(f"  Using Dynamic Kernel: {KERNEL_SIZE}")
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, KERNEL_SIZE)
    dilate = cv2.dilate(cleaned_thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_contours = []
    for c in contours:
        (x, y, w, h) = cv2.boundingRect(c)
        if w > MIN_CONTOUR_WIDTH and h > MIN_CONTOUR_HEIGHT:
            valid_contours.append(c)
    
    print(f"Found {len(valid_contours)} valid line fragments.")

    # NEW PASS 3: MERGE FRAGMENTS ON THE SAME LINE (Unchanged)
    if not valid_contours:
        print("No valid line fragments found. Exiting.")
        return None, None # <-- MODIFIED: Return None

    sorted_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[1])
    merged_boxes = []
    Y_TOLERANCE = median_height * 5
    print(f"Using Y-merge tolerance: {Y_TOLERANCE:.2f} pixels")

    current_box = cv2.boundingRect(sorted_contours[0])
    for i in range(1, len(sorted_contours)):
        next_box = cv2.boundingRect(sorted_contours[i])
        (x_c, y_c, w_c, h_c) = current_box
        (x_n, y_n, w_n, h_n) = next_box
        
        center_c = y_c + h_c / 2.0
        center_n = y_n + h_n / 2.0
        
        if abs(center_c - center_n) < Y_TOLERANCE:
            min_x = min(x_c, x_n)
            min_y = min(y_c, y_n)
            max_x = max(x_c + w_c, x_n + w_n)
            max_y = max(y_c + h_c, y_n + h_n)
            current_box = (min_x, min_y, max_x - min_x, max_y - min_y)
        else:
            merged_boxes.append(current_box)
            current_box = next_box
    
    merged_boxes.append(current_box)
    print(f"Merged into {len(merged_boxes)} final lines.")

    # 6. Iterate, Draw, and Store Merged Boxes
    line_number = 1
    json_output_data = [] # <-- MODIFIED: This was line_boxes
    
    for box in merged_boxes:
        (x, y, w, h) = box
        
        # Add data for JSON output
        json_output_data.append({
            "number": line_number,
            "box": (x, y, w, h)
        })

        # Draw on the output image
        cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
        text_position = (x - 40, y + h // 2)
        cv2.putText(output, str(line_number), text_position, 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 2)
        
        line_number += 1

    # --- MODIFIED: Return data instead of saving files ---
    print("Text detection function complete. Returning image array and box data.")
    return output, json_output_data
    # ----------------------------------------------------


# --- SCRIPT ENTRY POINT ---
# This part now *uses* the function above, so you can still run this
# file directly to test the OpenCV logic.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Finds and boxes lines of text in an image."
    )
    parser.add_argument("image_path", help="The path to the input image file.")
    args = parser.parse_args()
    
    # Call the function
    annotated_image, box_data = find_text_lines(args.image_path)
    
    if annotated_image is not None and box_data is not None:
        # --- Prepare output filenames ---
        base_name = os.path.basename(args.image_path)
        file_name, file_ext = os.path.splitext(base_name)
        output_image_filename = f"{file_name}_boxed.jpg" 
        output_json_filename = f"{file_name}_boxed.json" 
        
        # --- Save box coordinates as JSON ---
        try:
            with open(output_json_filename, 'w') as json_file:
                json.dump(box_data, json_file, indent=2)
            print(f"\nSuccessfully saved box data to '{output_json_filename}'")
        except IOError as e:
            print(f"\nError writing JSON file: {e}")

        # 7. SAVE AND DISPLAY
        cv2.imwrite(output_image_filename, annotated_image)
        print(f"Successfully processed and saved image to '{output_image_filename}'")
        
        cv2.imshow('Output', annotated_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("Processing failed.")