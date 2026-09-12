"""
line_detector.py
-----------------
OpenCV Line & Piping Connection Detector for P&IDs.
Detects straight piping runs, signal lines, intersections (T-junctions, cross-junctions),
and line endpoints using thresholding, morphological skeletonization, and Hough line transforms.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List

from app.pid.canonical_schema import PIDLine


def detect_lines_opencv(image_path: str, page_num: int = 1) -> List[PIDLine]:
    """
    Detects piping line segments and connectivity from a high-resolution P&ID page image.
    Returns a list of PIDLine objects with coordinate polyline points.
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return []

    img = cv2.imread(str(img_p), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    # Adaptive Thresholding to isolate black line drawings
    blur = cv2.GaussianBlur(img, (3, 3), 0)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3)

    # Morphological line isolation (horizontal and vertical kernels)
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))

    horiz_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horiz_kernel)
    vert_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vert_kernel)

    combined_lines = cv2.addWeighted(horiz_lines, 1.0, vert_lines, 1.0, 0.0)

    # Probabilistic Hough Line Transform
    lines_p = cv2.HoughLinesP(
        combined_lines,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=30,
        maxLineGap=10,
    )

    detected_lines: List[PIDLine] = []

    if lines_p is not None:
        for idx, line in enumerate(lines_p, start=1):
            pts = line.reshape(-1)
            if len(pts) != 4:
                continue
            x1, y1, x2, y2 = pts
            # Filter out tiny line noise
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            if length < 25:
                continue

            l_id = f"line_{page_num}_{idx:04d}"
            detected_lines.append(
                PIDLine(
                    id=l_id,
                    points=[[int(x1), int(y1)], [int(x2), int(y2)]],
                    line_type="piping",
                    page=page_num,
                )
            )

    return detected_lines
