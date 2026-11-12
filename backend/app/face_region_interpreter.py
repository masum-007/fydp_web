"""Optional, evidence-cautious localization of model attributions on a FACE CROP.

The input image and attribution maps MUST share the same coordinate system.
Use original, numeric attribution arrays, never a colorized overlay or PNG.

MediaPipe's optional face_landmarker.task is supplied by the application owner.
This module does NOT download assets or load any model at import time.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import cv2

# Landmark indices belong to the FACE SUBJECT, not the viewer's mirrored image.
# First implementation uses approximate eye, nose and mouth areas rather than
# claiming a pixel-accurate anatomical segmentation.
REGIONS: dict[str, tuple[int, ...]] = {
    "person's left eye": (362, 385, 387, 263, 373, 380),
    "person's right eye": (33, 160, 158, 133, 153, 144),
    "nose": (168, 197, 1, 4, 5, 98, 97, 2, 326, 327),
    "mouth": (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91),
}


def locate_single_face(crop_rgb: np.ndarray, landmarker_task_path: str):
    """Return MediaPipe landmarks, or None if not EXACTLY one face was found.

    The task asset must come from the official Google MediaPipe model bundle.
    """
    if crop_rgb.ndim != 3 or crop_rgb.shape[2] != 3 or crop_rgb.dtype != np.uint8:
        raise ValueError("crop_rgb must be an RGB uint8 array with shape H x W x 3")
    import mediapipe as mp  # optional runtime dependency
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(landmarker_task_path)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=2,
    )
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                        data=np.ascontiguousarray(crop_rgb))
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        result = detector.detect(mp_image)
    return result.face_landmarks[0] if len(result.face_landmarks) == 1 else None


def region_masks(landmarks, height: int, width: int) -> dict[str, np.ndarray]:
    """Build *approximate* facial-feature masks from normalized landmarks."""
    if len(landmarks) < 478:
        raise ValueError("Expected a full MediaPipe Face Landmarker result")
    masks: dict[str, np.ndarray] = {}
    for name, ids in REGIONS.items():
        pts = np.array(
            [(np.clip(landmarks[i].x, 0, 1) * (width - 1),
              np.clip(landmarks[i].y, 0, 1) * (height - 1)) for i in ids],
            dtype=np.float32,
        ).astype(np.int32)
        mask = np.zeros((height, width), dtype=np.uint8)
        if len(np.unique(pts, axis=0)) >= 3:
            cv2.fillConvexPoly(mask, cv2.convexHull(pts), 1)
            # Include the area immediately around the features, not only the
            # exact eye/lip outline; about 2% of the image width.
            radius = max(2, round(width * 0.02))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                (radius * 2 + 1, radius * 2 + 1))
            mask = cv2.dilate(mask, kernel)
        masks[name] = mask.astype(bool)
    return masks


def _spatial_map(array: np.ndarray, height: int, width: int, *, signed: bool) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim == 3 and arr.shape[-1] == 3 and signed:
        # SHAP values may have one value per color channel; preserve signs by
        # summing channels before selecting positive vs negative contributions.
        arr = arr.sum(axis=-1)
    if arr.ndim != 2 or min(arr.shape) < 2:
        raise ValueError("Provide an original numeric H x W attribution map; not a rendered overlay")
    if not np.isfinite(arr).all():
        raise ValueError("Attribution map contains NaN or infinity")
    if arr.shape != (height, width):
        arr = cv2.resize(arr, (width, height), interpolation=cv2.INTER_LINEAR)
    return arr


def dominant_regions(signal: np.ndarray,
                     masks: Mapping[str, np.ndarray],
                     *, ratio: float = 1.30) -> list[str]:
    """Rank local *mean* attribution to reduce the bias toward large regions.

    A diffuse/near-uniform map does not justify naming a precise facial part.
    The ratio is a heuristic, NOT a calibrated confidence threshold.
    """
    values = []
    for name, mask in masks.items():
        if mask.shape != signal.shape or not np.any(mask):
            continue
        values.append((name, float(np.maximum(signal[mask], 0).mean())))
    if len(values) < 2:
        return []
    values.sort(key=lambda item: item[1], reverse=True)
    top = values[0][1]
    baseline = float(np.mean([v for _, v in values]))
    if top < 1e-8 or top < baseline * ratio:
        return []
    # Only mention second region if nearly as prominent as the first.
    out = [values[0][0]]
    if len(values) > 1 and values[1][1] >= 0.85 * top:
        out.append(values[1][0])
    return out


def summarize_xai_regions(
    crop_rgb: np.ndarray,
    landmarker_task_path: str,
    *,
    gradcam_fake: np.ndarray | None = None,
    shap_signed: np.ndarray | None = None,
    shap_target: str = "Fake",
    lime_signed: np.ndarray | None = None,
    lime_target: str = "Fake",
) -> dict:
    """Generate cautious, method-specific report sentences.

    gradcam_fake: raw positive Grad-CAM map for FAKE-class score (individual
      backbone or a separately labeled average of backbones).
    shap_signed: signed SHAP values for one EXPLICIT output class, not the
      output of shap.image_plot or a 'red-only' rendering.
    lime_signed: pixel/segment map reconstructed from LIME local_exp weights
      for one EXPLICIT class, not the colorized segmentation preview.

    The labels here describe attribution only, NEVER proven manipulation.
    """
    if shap_target not in ("Fake", "Real") or lime_target not in ("Fake", "Real"):
        raise ValueError("Target must explicitly be 'Fake' or 'Real'")
    h, w = crop_rgb.shape[:2]
    if crop_rgb.ndim != 3 or crop_rgb.shape[2] != 3:
        raise ValueError("Expected RGB face crop")
    landmarks = locate_single_face(crop_rgb, landmarker_task_path)
    if landmarks is None:
        return {
            "status": "face_regions_unavailable",
            "narratives": {},
            "note": "Facial regions could not be localized reliably (no single face detected).",
        }
    masks = region_masks(landmarks, h, w)
    narratives: dict[str, str] = {}
    rankings: dict[str, list[str]] = {}
    specs = (
        ("Grad-CAM", gradcam_fake, False, "Fake"),
        ("SHAP", shap_signed, True, shap_target),
        ("LIME", lime_signed, True, lime_target),
    )
    for method, values, signed, target in specs:
        if values is None:
            continue
        a = _spatial_map(values, h, w, signed=signed)
        labels = dominant_regions(np.maximum(a, 0.0), masks)
        opposed = dominant_regions(np.maximum(-a, 0.0), masks) if signed else []
        rankings[method] = {"supporting": labels, "opposing": opposed}
        if not labels:
            narratives[method] = (
                f"{method} did not show sufficiently concentrated positive attribution "
                "to name one facial feature reliably."
            )
        else:
            features = " and ".join(labels)
            if method == "Grad-CAM":
                narratives[method] = (
                    f"For the Fake-category score, Grad-CAM showed comparatively stronger "
                    f"activation near the {features}. This is model attention, not evidence "
                    "that these pixels were manipulated."
                )
            elif method == "SHAP":
                narratives[method] = (
                    f"For the {target}-category output, SHAP estimated stronger positive "
                    f"contributions around the {features}, relative to the masking baseline. "
                    "The attribution is not an authenticity finding."
                )
            else:
                narratives[method] = (
                    f"For the {target}-category output, LIME's local approximation "
                    f"assigned positive weight to image segments near the {features}. "
                    "This does not establish that the regions were altered."
                )
        if opposed:
            narratives[method] += (
                f" Opposing contributions to the {target}-category score were "
                f"more concentrated around the {' and '.join(opposed)}."
            )
    return {
        "status": "localized",
        "ranked_regions": rankings,
        "narratives": narratives,
        "note": "All descriptions refer to the analyzed face crop. Left/right are the person's, not the viewer's. Only the specified class and prediction wrapper are explained.",
    }
