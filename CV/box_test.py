import cv2
import numpy as np
import argparse
import sys
import os
import json

# --- Configuration ---
# We want to find fragments, so let's REDUCE the width factor
KERNEL_WIDTH_FACTOR = 4
KERNEL_HEIGHT_FACTOR = 0.4
MIN_LINE_HEIGHT_FACTOR = 0.5
# Set a reasonable minimum width to filter out noise
MIN_LINE_WIDTH_FACTOR = 2# <--- Reduced to catch fragments
OPENING_KERNEL_SIZE = (3, 3) 
ADAPTIVE_BLOCK_SIZE = 15
ADAPTIVE_C = 7

# --- Grid Removal Config ---
GRID_LINE_KERNEL_LENGTH = 30
# -------------------------------

# --- Tuning Configuration ---
# We no longer need to tune to hit a target.
# We will just use one pass with our static kernel.
# So, the tuning config is no longer needed.
# MAX_BOXES_TARGET = 25
# MAX_TUNING_ATTEMPTS = 5      
# WIDTH_FACTOR_STEP = 2.0
# -------------------------------

def find_text_lines(image_path):
    """
    Finds, boxes, and numbers text lines.
    Includes steps for grid-line and noise removal.
    """
    
    # 1. Load the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)

    output = image.copy()

    # 2. Preprocessing
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 3. Adaptive Threshold
    thresh = cv2.adaptiveThreshold(gray, 255, 
                                 cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                 cv2.THRESH_BINARY_INV, 
                                 ADAPTIVE_BLOCK_SIZE, 
                                 ADAPTIVE_C)

    # -----------------------------------------------------------------
    # STEP 4: REMOVE GRID LINES
    # (This section is unchanged)
    # -----------------------------------------------------------------
    
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

    # -----------------------------------------------------------------
    # STEP 5: DE-NOISE (FIX FOR HOLES)
    # (This section is unchanged)
    # -----------------------------------------------------------------
    opening_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, OPENING_KERNEL_SIZE)
    cleaned_thresh = cv2.morphologyEx(thresh_no_grid, cv2.MORPH_OPEN, 
                                      opening_kernel, iterations=1)
    
    # -----------------------------------------------
    # PASS 1: ANALYZE TEXT SIZE (on cleaned, grid-less image)
    # (This section is unchanged)
    # -----------------------------------------------
    
    letter_contours, _ = cv2.findContours(cleaned_thresh.copy(), cv2.RETR_EXTERNAL, 
                                          cv2.CHAIN_APPROX_SIMPLE)

    heights = []
    for contour in letter_contours:
        (x, y, w, h) = cv2.boundingRect(contour)
        if h > 5 and h < 200 and w < 200:
            heights.append(h)

    if not heights:
        print("No text-like contours found. Try tuning ADAPTIVE_C or GRID_LINE_KERNEL_LENGTH.")
        # Removed intermediate imshow() calls as requested
        return

    median_height = np.median(heights)
    
    if np.isnan(median_height):
        print("Could not determine a median height. Exiting.")
        return

    print(f"Detected median text height: {median_height:.2f} pixels")

    # -----------------------------------------------
    # PASS 2: FIND ALL LINE FRAGMENTS
    # (This is simplified from the old tuning loop)
    # -----------------------------------------------
    
    # Set dynamic filters based on median height
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

    # Filter contours based on our minimums
    valid_contours = []
    for c in contours:
        (x, y, w, h) = cv2.boundingRect(c)
        if w > MIN_CONTOUR_WIDTH and h > MIN_CONTOUR_HEIGHT:
            valid_contours.append(c)
    
    print(f"Found {len(valid_contours)} valid line fragments.")

    # -----------------------------------------------
    # NEW PASS 3: MERGE FRAGMENTS ON THE SAME LINE
    # -----------------------------------------------

    if not valid_contours:
        print("No valid line fragments found. Exiting.")
        return # Exit if we have nothing to merge

    # Sort contours from top-to-bottom
    sorted_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[1])

    merged_boxes = [] # This will store the final (x, y, w, h) tuples
    
    # Define a vertical tolerance. How close do centers need to be?
    # We'll use half the median text height.
    Y_TOLERANCE = median_height * 5
    print(f"Using Y-merge tolerance: {Y_TOLERANCE:.2f} pixels")

    # Start with the first contour
    current_box = cv2.boundingRect(sorted_contours[0])

    for i in range(1, len(sorted_contours)):
        next_box = cv2.boundingRect(sorted_contours[i])
        (x_c, y_c, w_c, h_c) = current_box
        (x_n, y_n, w_n, h_n) = next_box
        
        # Calculate vertical centers
        center_c = y_c + h_c / 2.0
        center_n = y_n + h_n / 2.0
        
        # Check if they are on the same line (centers are close)
        if abs(center_c - center_n) < Y_TOLERANCE:
            # Yes, merge them
            min_x = min(x_c, x_n)
            min_y = min(y_c, y_n)
            max_x = max(x_c + w_c, x_n + w_n)
            max_y = max(y_c + h_c, y_n + h_n)
            
            # Update current_box with the new merged dimensions
            current_box = (min_x, min_y, max_x - min_x, max_y - min_y)
        else:
            # No, they are on different lines.
            # Save the completed 'current_box'
            merged_boxes.append(current_box)
            # And start a new 'current_box' with this 'next_box'
            current_box = next_box
    
    # After the loop, add the very last 'current_box'
    merged_boxes.append(current_box)
        
    print(f"Merged into {len(merged_boxes)} final lines.")


    # 6. Iterate, Draw, and Store Merged Boxes
    line_number = 1
    line_boxes = [] # This will store the (x, y, w, h)
    
    # Loop over the NEW merged_boxes list
    for box in merged_boxes:
        (x, y, w, h) = box

        box_coords = (x, y, w, h)
        line_boxes.append(box_coords)

        cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
        text_position = (x - 40, y + h // 2)
        
        cv2.putText(output, str(line_number), text_position, 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 2) # Font size 1.5
        
        line_number += 1

    # --- Prepare output filenames ---
    base_name = os.path.basename(image_path)
    file_name, file_ext = os.path.splitext(base_name)
    output_image_filename = f"{file_name}_boxed.jpg" 
    output_json_filename = f"{file_name}_boxed.json" 
    
    # --- Save box coordinates as JSON ---
    
    # Create a list of dictionaries for JSON
    json_output_data = []
    for i, box in enumerate(line_boxes):
        json_output_data.append({
            "number": i + 1,
            "box": box  # box is already (x, y, w, h)
        })
    
    # Write the JSON data to the file
    try:
        with open(output_json_filename, 'w') as json_file:
            json.dump(json_output_data, json_file, indent=2)
        print(f"\nSuccessfully saved box data to '{output_json_filename}'")
    except IOError as e:
        print(f"\nError writing JSON file: {e}")
    # ------------------------------------------

    # 7. SAVE AND DISPLAY
    cv2.imwrite(output_image_filename, output)
    print(f"Successfully processed and saved image to '{output_image_filename}'")

    # --- MODIFIED: Show only the final output ---
    cv2.imshow('Output', output)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    # --------------------------------------------

# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Finds and boxes lines of text in an image."
    )
    parser.add_argument("image_path", help="The path to the input image file.")
    args = parser.parse_args()
    
    find_text_lines(args.image_path)