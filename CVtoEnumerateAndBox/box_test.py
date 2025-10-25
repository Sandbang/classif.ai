import cv2
import numpy as np
import argparse
import sys
import os

# --- Configuration ---
KERNEL_WIDTH_FACTOR = 4.0
KERNEL_HEIGHT_FACTOR = 0.4
MIN_LINE_HEIGHT_FACTOR = 0.5
MIN_LINE_WIDTH_FACTOR = 1.5
OPENING_KERNEL_SIZE = (3, 3) 
ADAPTIVE_BLOCK_SIZE = 15
ADAPTIVE_C = 7

# --- NEW: Grid Removal Config ---
# Length of kernel to detect grid lines.
# This value should be > average letter width/height
# but < the spacing between lines. Tune if needed.
GRID_LINE_KERNEL_LENGTH = 30
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
    # This gets text, holes, AND grid lines
    thresh = cv2.adaptiveThreshold(gray, 255, 
                                 cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                 cv2.THRESH_BINARY_INV, 
                                 ADAPTIVE_BLOCK_SIZE, 
                                 ADAPTIVE_C)

    # -----------------------------------------------------------------
    # STEP 4: REMOVE GRID LINES
    # -----------------------------------------------------------------
    
    # --- Remove Horizontal Lines ---
    # Create a long horizontal kernel
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, 
                                                (GRID_LINE_KERNEL_LENGTH, 1))
    # Use morphology OPEN to find all horizontal lines
    detected_horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, 
                                                 horizontal_kernel, iterations=2)
    # Dilate them slightly to make sure we get the whole line
    detected_horizontal_lines = cv2.dilate(detected_horizontal_lines, None, iterations=2)

    # --- Remove Vertical Lines ---
    # Create a long vertical kernel
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, 
                                              (1, GRID_LINE_KERNEL_LENGTH))
    # Use morphology OPEN to find all vertical lines
    detected_vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, 
                                               vertical_kernel, iterations=2)
    # Dilate them slightly
    detected_vertical_lines = cv2.dilate(detected_vertical_lines, None, iterations=2)

    # --- Combine and Subtract ---
    # Combine the horizontal and vertical line "masks"
    grid_mask = detected_horizontal_lines + detected_vertical_lines
    
    # Subtract the grid mask from the original thresholded image
    thresh_no_grid = cv2.subtract(thresh, grid_mask)

    # -----------------------------------------------------------------
    # STEP 5: DE-NOISE (FIX FOR HOLES)
    # -----------------------------------------------------------------
    # Now, on the grid-less image, remove the binder holes (noise)
    opening_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, OPENING_KERNEL_SIZE)
    cleaned_thresh = cv2.morphologyEx(thresh_no_grid, cv2.MORPH_OPEN, 
                                      opening_kernel, iterations=1)
    
    # -----------------------------------------------
    # PASS 1: ANALYZE TEXT SIZE (on cleaned, grid-less image)
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
        cv2.imshow('Original', image)
        cv2.imshow('1. Threshold (With Grid)', thresh)
        cv2.imshow('2. Grid Mask', grid_mask)
        cv2.imshow('3. Threshold (No Grid)', thresh_no_grid)
        cv2.imshow('4. Cleaned (No Holes)', cleaned_thresh)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    median_height = np.median(heights)
    
    if np.isnan(median_height):
        print("Could not determine a median height. Exiting.")
        return

    print(f"Detected median text height: {median_height:.2f} pixels")

    # -----------------------------------------------
    # PASS 2: BUILD DYNAMIC KERNEL (on cleaned, grid-less image)
    # -----------------------------------------------
    
    k_height = int(max(1, median_height * KERNEL_HEIGHT_FACTOR))
    k_width = int(max(1, median_height * KERNEL_WIDTH_FACTOR))
    KERNEL_SIZE = (k_width, k_height)

    MIN_CONTOUR_HEIGHT = int(median_height * MIN_LINE_HEIGHT_FACTOR)
    MIN_CONTOUR_WIDTH = int(median_height * MIN_LINE_WIDTH_FACTOR)

    print(f"Using Dynamic Kernel: {KERNEL_SIZE}")
    print(f"Using Dynamic Filters: min_h={MIN_CONTOUR_HEIGHT}, min_w={MIN_CONTOUR_WIDTH}")

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, KERNEL_SIZE)
    # Dilate the *cleaned* image
    dilate = cv2.dilate(cleaned_thresh, kernel, iterations=1)

    contours, hierarchy = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        sorted_contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[1])
    else:
        sorted_contours = []
        print("No line contours found after dilation.")

    print(f"Found {len(sorted_contours)} potential lines.")

    # 6. Iterate, Filter, and Draw
    line_number = 1
    line_boxes = [] # <--- CHANGE 1: INITIALIZE LIST
    for contour in sorted_contours:
        (x, y, w, h) = cv2.boundingRect(contour)

        if w > MIN_CONTOUR_WIDTH and h > MIN_CONTOUR_HEIGHT:
            
            # <--- CHANGE 2: APPEND COORDINATES ---
            box_coords = (x, y, w, h)
            line_boxes.append(box_coords)
            # ------------------------------------

            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
            text_position = (x - 40, y + h // 2)
            
            # <--- CHANGE 3: FONT SIZE INCREASED ---
            cv2.putText(output, str(line_number), text_position, 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 2)
            # -------------------------------------
            
            line_number += 1

    # <--- CHANGE 4: PRINT ALL STORED BOXES ---
    print(f"\n--- Stored Box Coordinates (x, y, w, h) ---")
    for i, box in enumerate(line_boxes):
        print(f"Line {i+1}: {box}")
    print("----------------------------------------------\n")
    # ------------------------------------------

    # 7. SAVE AND DISPLAY
    base_name = os.path.basename(image_path)
    file_name, file_ext = os.path.splitext(base_name)
    output_filename = f"{file_name}_boxed.jpg" 
    
    cv2.imwrite(output_filename, output)
    print(f"Successfully processed and saved to '{output_filename}'")

    # Show all the intermediate steps for debugging
    cv2.imshow('Original', image)
    cv2.imshow('1. Threshold (With Grid)', thresh)
    cv2.imshow('2. Grid Mask', grid_mask)
    cv2.imshow('3. Threshold (No Grid)', thresh_no_grid)
    cv2.imshow('4. Cleaned (No Holes)', cleaned_thresh)
    cv2.imshow('5. Dilated (Lines)', dilate)
    cv2.imshow('6. Output', output)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Finds and boxes lines of text in an image."
    )
    parser.add_argument("image_path", help="The path to the input image file.")
    args = parser.parse_args()
    
    find_text_lines(args.image_path)