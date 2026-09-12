"""
symbol_detector.py
------------------
Local P&ID Symbol Detector.
Supports SAHI (Slicing Aided Hyper Inference) / YOLO model interfaces as well as
OpenCV contour shape fallback detection for P&ID symbol categories:
  - pump, compressor, tank, vessel, heat_exchanger
  - gate_valve, ball_valve, control_valve, check_valve
  - pressure_transmitter, pressure_indicator, flow_transmitter, level_transmitter
  - flange, reducer, nozzle
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List

from app.pid.canonical_schema import PIDSymbol


SYMBOL_TAXONOMY = [
    "pump",
    "compressor",
    "tank",
    "vessel",
    "heat_exchanger",
    "gate_valve",
    "ball_valve",
    "control_valve",
    "check_valve",
    "pressure_transmitter",
    "pressure_indicator",
    "flow_transmitter",
    "flow_indicator",
    "temperature_transmitter",
    "level_transmitter",
    "flange",
    "reducer",
    "nozzle",
]


def detect_symbols_opencv_heuristics(image_path: str, page_num: int = 1) -> List[PIDSymbol]:
    """
    OpenCV geometric contour detection fallback for P&ID symbols (circles, triangles/valves, rectangles/vessels).
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return []

    img = cv2.imread(str(img_p), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    # Adaptive Thresholding & Morphological Operations
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    symbols: List[PIDSymbol] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 100 or area > (img.shape[0] * img.shape[1] * 0.25):
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h
        perimeter = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * perimeter, True)
        num_vertices = len(approx)

        x1, y1, x2, y2 = x, y, x + w, y + h
        symbol_type = None

        # Circles (Transmitters / Instruments / Centrifugal Pumps)
        if 8 <= num_vertices <= 16 and 0.85 <= aspect_ratio <= 1.15:
            if 150 <= area <= 2500:
                symbol_type = "pressure_transmitter"
            elif area > 2500:
                symbol_type = "pump"

        # Triangles / Bow-ties (Valves)
        elif num_vertices == 3 or (num_vertices == 6 and aspect_ratio > 1.2):
            symbol_type = "gate_valve"

        # Rectangles / Cylinders (Tanks, Vessels, Heat Exchangers)
        elif num_vertices == 4:
            if aspect_ratio > 2.0 or aspect_ratio < 0.5:
                symbol_type = "vessel"
            elif 0.8 <= aspect_ratio <= 1.2 and area > 5000:
                symbol_type = "tank"

        if symbol_type:
            s_id = f"symbol_{page_num}_{len(symbols) + 1:04d}"
            symbols.append(
                PIDSymbol(
                    id=s_id,
                    type=symbol_type,
                    bbox=[x1, y1, x2, y2],
                    confidence=0.85,
                    page=page_num,
                )
            )

    return symbols


def detect_symbols_sahi_yolo(image_path: str, model_path: str | None = None, page_num: int = 1) -> List[PIDSymbol]:
    """
    SAHI (Slicing Aided Hyper Inference) tiled inference wrapper for local YOLO models.
    Falls back to OpenCV geometric heuristic detection if no custom weights file is loaded.
    """
    if model_path and Path(model_path).exists():
        try:
            from sahi import AutoDetectionModel
            from sahi.predict import get_sliced_prediction

            detection_model = AutoDetectionModel.from_pretrained(
                model_type="yolov8",
                model_path=model_path,
                confidence_threshold=0.3,
                device="cpu",
            )
            result = get_sliced_prediction(
                image_path,
                detection_model,
                slice_height=512,
                slice_width=512,
                overlap_height_ratio=0.2,
                overlap_width_ratio=0.2,
            )

            symbols = []
            for idx, pred in enumerate(result.object_prediction_list, start=1):
                bbox = [
                    int(pred.bbox.minx),
                    int(pred.bbox.miny),
                    int(pred.bbox.maxx),
                    int(pred.bbox.maxy),
                ]
                cat_name = pred.category.name.lower()
                symbols.append(
                    PIDSymbol(
                        id=f"symbol_{page_num}_{idx:04d}",
                        type=cat_name if cat_name in SYMBOL_TAXONOMY else "instrument",
                        bbox=bbox,
                        confidence=round(float(pred.score.value), 3),
                        page=page_num,
                    )
                )
            return symbols
        except Exception:
            pass

    return detect_symbols_opencv_heuristics(image_path, page_num=page_num)
