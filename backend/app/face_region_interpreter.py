"""Geometry-based interpretation of existing Grad-CAM, SHAP and LIME maps.

NO new pretrained model. Uses the optional already-installed MediaPipe
FaceLandmarker for landmarks; broad hairline/ear-adjacent labels are geometric
APPROXIMATIONS, not actual hair or ear segmentation.

Inputs MUST be numeric maps aligned to the 224x224 analyzed face crop.
Grad-CAM has no negative direction; LIME/SHAP preserve positive/negative signs.
All percentages below describe distribution of *attribution within the map*,
never the probability of editing or the reliability of a model prediction.
"""
from __future__ import annotations

from collections import Counter
from typing import Mapping

import cv2
import numpy as np

REGIONS: dict[str, tuple[int, ...]] = {
    "person's left eye": (362, 385, 387, 263, 373, 380),
    "person's right eye": (33, 160, 158, 133, 153, 144),
    "nose": (168, 197, 1, 4, 5, 98, 97, 2, 326, 327),
    "mouth and chin": (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91,
                       152, 148, 377, 176, 400),
    "person's left eyebrow": (336, 296, 334, 293, 300),
    "person's right eyebrow": (70, 63, 105, 66, 107),
}
# Face oval indices from MediaPipe's published Face Mesh topology.
FACE_OVAL = (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361,
             288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
             150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103,
             67, 109)


def locate_single_face(crop_rgb: np.ndarray, landmarker_task_path: str):
    """Return one face's landmarks, or None; never select an arbitrary face."""
    if crop_rgb.ndim != 3 or crop_rgb.shape[2] != 3 or crop_rgb.dtype != np.uint8:
        raise ValueError("crop_rgb must be RGB uint8 with shape H x W x 3")
    import mediapipe as mp
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(landmarker_task_path)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE, num_faces=2,
    )
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                        data=np.ascontiguousarray(crop_rgb))
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        result = detector.detect(mp_image)
    return result.face_landmarks[0] if len(result.face_landmarks) == 1 else None


def _pts(landmarks, ids, h, w):
    return np.array([[int(round(np.clip(landmarks[i].x, 0, 1) * (w - 1))),
                      int(round(np.clip(landmarks[i].y, 0, 1) * (h - 1)))]
                     for i in ids], dtype=np.int32)


def _polygon(shape, points, dilation=0):
    mask = np.zeros(shape, np.uint8)
    if len(np.unique(points, axis=0)) >= 3:
        cv2.fillConvexPoly(mask, cv2.convexHull(points), 1)
        if dilation:
            d = 2 * dilation + 1
            mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d)))
    return mask.astype(bool)


def _rectangle(shape, x1, y1, x2, y2):
    h, w = shape
    x1, x2 = sorted((max(0, min(w, int(x1))), max(0, min(w, int(x2)))))
    y1, y2 = sorted((max(0, min(h, int(y1))), max(0, min(h, int(y2)))))
    mask = np.zeros(shape, bool)
    if x2 > x1 and y2 > y1:
        mask[y1:y2, x1:x2] = True
    return mask


def region_masks(landmarks, height: int, width: int) -> dict[str, np.ndarray]:
    """Approximate landmark and geometric zones, ALL in crop coordinates.

    Broad positional labels are explicitly not pixel-wise semantic segmentation.
    Returns partly overlapping masks for compatibility; ranking resolves overlaps
    using priority, so no heatmap pixel is counted twice.
    """
    if len(landmarks) < 478:
        raise ValueError("Expected a full MediaPipe Face Landmarker result")
    if height < 4 or width < 4:
        raise ValueError("Image dimensions too small")
    shape = (height, width)
    radius = max(2, round(width * .015))
    masks = {name: _polygon(shape, _pts(landmarks, ids, height, width), radius)
             for name, ids in REGIONS.items()}
    outline_points = _pts(landmarks, FACE_OVAL, height, width)
    outline = _polygon(shape, outline_points)
    if not outline.any():
        # Degenerate landmarks: don't invent physical positions.
        masks["outside the tracked facial features"] = ~np.logical_or.reduce(list(masks.values()))
        return masks
    x0, y0 = outline_points.min(axis=0)
    x1, y1 = outline_points.max(axis=0)
    fw = max(2, x1 - x0)
    fh = max(2, y1 - y0)
    xmid = (x0 + x1) / 2

    # Coarse zones derived from face outline, and landmark-based eyebrows/mouth.
    # Forehead ends above the eyebrow line; cheeks occupy the lateral middle face.
    eyebrows = _pts(landmarks, REGIONS["person's right eyebrow"] +
                    REGIONS["person's left eyebrow"], height, width)
    brow_y = float(np.median(eyebrows[:, 1]))
    eye_pts = _pts(landmarks, REGIONS["person's right eye"] +
                   REGIONS["person's left eye"], height, width)
    eye_y = float(np.median(eye_pts[:, 1]))
    nose_y = float(landmarks[2].y * (height - 1))
    mouth_y = float(landmarks[17].y * (height - 1))

    masks["forehead"] = outline & _rectangle(shape, x0 + .13*fw, y0 + .02*fh,
                                               x1 - .13*fw, max(y0+.04*fh, brow_y))
    masks["person's right cheek"] = outline & _rectangle(
        shape, x0 + .04*fw, eye_y + .05*fh, xmid-.11*fw, max(nose_y, mouth_y-.13*fh))
    masks["person's left cheek"] = outline & _rectangle(
        shape, xmid+.11*fw, eye_y + .05*fh, x1 - .04*fw, max(nose_y, mouth_y-.13*fh))
    masks["jawline"] = outline & _rectangle(shape, x0+.06*fw, mouth_y-.02*fh,
                                             x1-.06*fw, y1+.01*fh)
    # These cannot establish pixel semantics such as actual hair/ears/skin.
    masks["upper-head / hairline vicinity (approximate)"] = _rectangle(
        shape, x0 + .02*fw, y0 - .24*fh, x1 - .02*fw, y0+.06*fh)
    masks["side-of-head / ear vicinity (approximate)"] = (
        _rectangle(shape, x0 - .19*fw, y0+.26*fh, x0+.05*fw, y0+.73*fh) |
        _rectangle(shape, x1 - .05*fw, y0+.26*fh, x1+.19*fw, y0+.73*fh))
    masks["lower crop / neck-clothing vicinity (approximate)"] = _rectangle(
        shape, 0, y1, width, height)
    masks["other face area"] = outline
    masks["outside estimated face/head regions"] = np.ones(shape, bool)
    return masks


def _spatial_map(array, height, width, *, signed):
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim == 3 and arr.shape[-1] == 3 and signed:
        arr = arr.sum(axis=-1)
    if arr.ndim != 2 or min(arr.shape) < 2:
        raise ValueError("Provide a numeric H x W attribution map, not a rendered overlay")
    if not np.isfinite(arr).all():
        raise ValueError("Attribution contains NaN or infinity")
    if arr.shape != (height, width):
        arr = cv2.resize(arr, (width, height), interpolation=cv2.INTER_LINEAR)
    return arr


def dominant_regions(signal, masks: Mapping[str, np.ndarray], *, ratio: float = 1.15):
    """Legacy API: cautious mean-based localization (preserved for old tests)."""
    signal = np.maximum(np.asarray(signal, dtype=np.float32), 0.0)
    if not np.isfinite(signal).all() or float(signal.max()) <= 1e-8:
        return []
    if float(signal.std()) / max(float(signal.mean()), 1e-8) < .05:
        return []
    high = signal >= max(float(np.quantile(signal, .88)), float(signal.max()) * .35)
    all_values, candidates = [], []
    for name, mask in masks.items():
        if mask.shape != signal.shape or not np.any(mask):
            continue
        mean = float(signal[mask].mean())
        all_values.append(mean)
        if float(high[mask].mean()) >= .07:
            candidates.append((name, mean))
    if len(all_values) < 2 or not candidates:
        return []
    candidates.sort(key=lambda x: x[1], reverse=True)
    if candidates[0][1] < max(1e-8, float(np.mean(all_values)) * ratio):
        return []
    top = candidates[0][1]
    return [name for name, value in candidates[:2] if value >= .85 * top]


def rank_attribution_regions(signal, masks: Mapping[str, np.ndarray], max_regions=2):
    """Rank using coverage + high-activation share + per-pixel concentration.

    Maps are divided into disjoint masks by declared priority. 'signal_share_pct'
    means percent of positive attribution mass inside the *map*, NOT
    'chance this physical region was edited'. Thresholds are heuristics.
    """
    x = np.maximum(np.asarray(signal, dtype=np.float32), 0)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError("Expected finite two-dimensional attribution map")
    if float(x.max()) < 1e-10 or float(x.std()) / max(float(x.mean()), 1e-9) < .05:
        return []
    strong = x >= max(float(np.quantile(x, .88)), float(x.max())*.35)
    all_mass = float(x.sum())
    strong_count = int(strong.sum())
    if all_mass <= 1e-10 or strong_count == 0:
        return []
    consumed = np.zeros(x.shape, bool)
    results = []
    for name, original in masks.items():
        m = np.asarray(original, dtype=bool)
        if m.shape != x.shape:
            raise ValueError(f"Region mask shape mismatch: {name}")
        m = m & ~consumed
        consumed |= m
        n = int(m.sum())
        if not n:
            continue
        coverage = float(x[m].sum())/all_mass
        peak_share = float(np.logical_and(m, strong).sum())/strong_count
        mean = float(x[m].mean())
        density = mean/max(float(x.mean()), 1e-10)
        # A region can be supported by a concentrated hotspot or substantial
        # attribution mass. Tiny accidental fragments should be ignored.
        if peak_share < .05 and coverage < .07:
            continue
        results.append({
            "region": name,
            "signal_share_pct": round(coverage*100, 1),
            "strong_pixel_share_pct": round(peak_share*100, 1),
            "relative_density": round(density, 2),
            "_rank": .57*peak_share + .33*coverage + .10*min(density/2, 1),
        })
    results.sort(key=lambda d: d["_rank"], reverse=True)
    if not results:
        return []
    winner = results[0]["_rank"]
    selected = [r for r in results if r["_rank"] >= winner*.46][:max_regions]
    for item in selected:
        del item["_rank"]
    return selected


def _names(rows):
    return [item["region"] for item in rows]


def _joined(items):
    return " and ".join(items)


def summarize_xai_regions(crop_rgb, landmarker_task_path, *, gradcam_fake=None,
                          gradcam_target="Fake", shap_signed=None, shap_target="Fake",
                          lime_signed=None, lime_target="Fake", gradcam_members=None):
    """One landmark pass for all methods and four already-computed CNN maps.

    Historical 'gradcam_fake' parameter accepts either target via gradcam_target.
    Per-model agreement describes locations, not independent class votes.
    """
    if any(t not in ("Fake", "Real") for t in (gradcam_target, shap_target, lime_target)):
        raise ValueError("Target must be Fake or Real")
    crop = np.asarray(crop_rgb)
    if crop.ndim != 3 or crop.shape[2] != 3 or crop.dtype != np.uint8:
        raise ValueError("Expected RGB uint8 face crop")
    h, w = crop.shape[:2]
    landmarks = locate_single_face(crop, landmarker_task_path)
    if landmarks is None:
        return {"status": "face_regions_unavailable", "narratives": {},
                "note": "Could not identify exactly one face in the analyzed crop.",
                "ranked_regions": {}, "regional_metrics": {}}
    masks = region_masks(landmarks, h, w)
    narratives, rankings, metrics = {}, {}, {}
    for method, raw, signed, target in (
        ("Grad-CAM", gradcam_fake, False, gradcam_target),
        ("SHAP", shap_signed, True, shap_target),
        ("LIME", lime_signed, True, lime_target),
    ):
        if raw is None:
            continue
        arr = _spatial_map(raw, h, w, signed=signed)
        positive = rank_attribution_regions(np.maximum(arr, 0), masks)
        negative = rank_attribution_regions(np.maximum(-arr, 0), masks) if signed else []
        support, oppose = _names(positive), _names(negative)
        rankings[method] = {"supporting": support, "opposing": oppose}
        metrics[method] = {"supporting": positive, "opposing": negative}
        if not support:
            narratives[method] = (
                f"{method} showed distributed or weak {target}-target attribution; "
                "no particular image region was localized reliably."
            )
        elif method == "Grad-CAM":
            narratives[method] = (
                f"For the {target}-category output, Grad-CAM showed stronger CNN activation "
                f"around {_joined(support)}. These locations indicate a model response, "
                "not confirmed editing."
            )
        else:
            narratives[method] = (
                f"For the {target}-category output, {method} attributed positive "
                f"contribution to {_joined(support)}. This is not a finding "
                "that those regions were digitally altered."
            )
        if oppose:
            narratives[method] += (
                f" Opposing attribution was concentrated around {_joined(oppose)}."
            )
    comparison = None
    if gradcam_members:
        individuals = {}
        vote = Counter()
        for model_name, raw in gradcam_members.items():
            if not isinstance(model_name, str) or len(model_name) > 80:
                raise ValueError("Invalid model identifier")
            single = rank_attribution_regions(
                _spatial_map(raw, h, w, signed=False), masks, max_regions=1
            )
            lead = single[0]["region"] if single else None
            individuals[model_name] = {"top_region": lead, "regional_metrics": single}
            if lead:
                vote[lead] += 1
        best = vote.most_common(1)
        n = len(individuals)
        overlap_region, overlap_count = best[0] if best else (None, 0)
        comparison = {
            "total_models": n,
            "models": individuals,
            "leading_region": overlap_region if overlap_count >= 2 else None,
            "models_agreeing": overlap_count if overlap_count >= 2 else 0,
            "note": "Comparing original-view CNN attention locations only, not the stacking classifier's class evidence.",
        }
    return {
        "status": "localized" if any(v["supporting"] for v in rankings.values()) else "distributed_activation",
        "ranked_regions": rankings,
        "regional_metrics": metrics,
        "model_comparison": comparison,
        "narratives": narratives,
        "note": ("Positions are approximate geometric zones in the analyzed face crop; "
                 "hairline/ear/neck labels are vicinity descriptions, not semantic segmentation. "
                 "Percentages refer to attribution-map mass, not the probability of manipulation. "
                 "Left/right facial sides belong to the person, not the viewer."),
    }
