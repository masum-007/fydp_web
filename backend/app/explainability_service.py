"""Optional per-evidence XAI service for NeuralEdge v2 four-model stacking.

XAI is generated on the EXACT 224x224 MTCNN face crop used by inference.
The predictor for LIME/SHAP is the engine's ORIGINAL + FLIPPED TTA stacking
wrapper. All maps target the Fake (positive) score.

- Grad-CAM: four CNN Fake-score maps averaged, NOT final stacking attribution.
- LIME: signed region contributions in a local surrogate of stacking.
- SHAP: signed contributions relative to its blur masking baseline.
- Region explanations: only if a MediaPipe task is configured and a single
  face can be localized on the same crop.

Keep this service authenticated; CPU/RAM costs can be high. Use a proper job
queue instead of synchronous calls for production hosting.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)
SUPPORTED_METHODS = ("gradcam", "lime", "shap")


def _png_rgb(rgb):
    import cv2
    import numpy as np

    img = np.asarray(rgb, dtype=np.uint8)
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError("Expected an RGB image")
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    if not ok:
        raise ValueError("Could not encode explanation PNG")
    return encoded.tobytes()


def signed_overlay(crop_rgb, signed_map):
    """Red=raises Fake score; blue=reduces Fake score in the local attribution.

    Normalize only for display; keep numerical signed values for regional
    interpretation. Never substitute an RGB rendering for raw attributions.
    """
    import numpy as np

    crop = np.asarray(crop_rgb, dtype=np.uint8)
    a = np.asarray(signed_map, dtype=np.float32)
    if crop.shape != (224, 224, 3) or a.shape != (224, 224):
        raise ValueError("Crop and signed attribution must share 224x224 coordinates")
    if not np.isfinite(a).all():
        raise ValueError("Attribution contains nonfinite values")
    norm = float(np.percentile(np.abs(a), 99))
    if norm <= 1e-12:
        return _png_rgb(crop)
    strength = np.clip(np.abs(a) / norm, 0, 1)
    colors = np.where(a[..., None] >= 0, [235, 75, 64], [58, 110, 221]).astype(np.float32)
    alpha = (0.68 * strength)[..., None]
    blended = np.clip(crop.astype(np.float32) * (1 - alpha) + colors * alpha, 0, 255).astype(np.uint8)
    return _png_rgb(blended)


def shap_fake_attributions(values):
    """Extract the explicitly ordered Fake output from SHAP image values.

    Expected output_names=['Real','Fake'], shape (1,224,224,3,2).
    Refuse unrecognized shapes rather than accidentally explain Real.
    """
    import numpy as np

    arr = np.asarray(values, dtype=np.float32)
    if arr.shape != (1, 224, 224, 3, 2):
        raise ValueError(
            f"Unsupported SHAP output shape {arr.shape}; expected (1,224,224,3,2) "
            "with outputs ['Real','Fake']. Do not silently choose an output."
        )
    if not np.isfinite(arr).all():
        raise ValueError("SHAP returned nonfinite values")
    return arr[0, ..., 1].sum(axis=-1)


def lime_fake_attributions(segments, local_exp):
    """Turn LIME's signed Fake-class superpixel weights into a spatial map."""
    import numpy as np

    segments = np.asarray(segments)
    if segments.shape != (224, 224):
        raise ValueError("Unexpected LIME superpixel dimensions")
    raw = np.zeros((224, 224), dtype=np.float32)
    for segment_id, weight in local_exp:
        if not np.isfinite(weight):
            raise ValueError("LIME returned nonfinite segment weights")
        raw[segments == int(segment_id)] = float(weight)
    return raw


def _region_summary(face_crop, raw, method, landmarker_task):
    """Fail closed: no named facial region when detection is unavailable."""
    if not landmarker_task or not Path(landmarker_task).is_file():
        return {
            "status": "not_configured",
            "narrative": "Facial-region localization is not configured. See the explanation image and method notes.",
            "regions": [],
        }
    try:
        from .face_region_interpreter import summarize_xai_regions

        args = {"gradcam_fake": raw} if method == "gradcam" else {f"{method}_signed": raw, f"{method}_target": "Fake"}
        summary = summarize_xai_regions(face_crop, str(landmarker_task), **args)
        return {
            "status": summary["status"],
            "narrative": summary.get("narratives", {}).get(method.upper() if method != "gradcam" else "Grad-CAM", summary.get("note", "No reliable facial-region attribution was identified.")),
            "regions": summary.get("ranked_regions", {}).get(method.upper() if method != "gradcam" else "Grad-CAM", {}),
        }
    except Exception:
        LOG.exception("Facial-region interpretation unavailable for %s", method)
        return {
            "status": "unavailable",
            "narrative": "Facial landmarks could not be localized reliably; no specific facial feature is identified.",
            "regions": [],
        }


def _lime_map(engine, crop_rgb, num_samples):
    from lime.lime_image import LimeImageExplainer

    explainer = LimeImageExplainer(random_state=42)
    explanation = explainer.explain_instance(
        crop_rgb,
        classifier_fn=engine.predict_proba_from_face_crops,
        labels=(1,),  # Fake: the stacking model's positive class
        hide_color=0,
        num_samples=num_samples,
        batch_size=4,
    )
    weights = explanation.local_exp.get(1)
    if not weights:
        raise ValueError("LIME did not return Fake-class weights")
    return lime_fake_attributions(explanation.segments, weights)


def _shap_map(engine, crop_rgb, max_evals):
    import numpy as np
    import shap

    # IMPORTANT: masking uses the SAME FACE-CROP coordinate space as the model.
    masker = shap.maskers.Image("blur(16,16)", crop_rgb.shape)
    explainer = shap.Explainer(
        engine.predict_proba_from_face_crops,
        masker,
        algorithm="partition",
        output_names=["Real", "Fake"],
    )
    explained = explainer(np.asarray(crop_rgb[None, ...]), max_evals=max_evals, batch_size=4)
    return shap_fake_attributions(explained.values)


def generate_explanation(engine, original_bytes: bytes, method: str, *,
                         landmarker_task: str | None = None,
                         lime_samples: int = 150,
                         shap_evals: int = 120):
    """Return (PNG bytes or None, JSON-safe metadata), no database writes.

    This takes some time on CPU: call only from authenticated, resource-limited
    on-demand endpoint. It never revises the original model decision.
    """
    import numpy as np
    from .inference_v2 import MODEL_ORDER

    if method not in SUPPORTED_METHODS:
        raise ValueError("Unknown explanation method")
    if not getattr(engine, "ready", False):
        raise RuntimeError("V2 inference engine is not ready")

    with engine.lock:
        crop, crop_info = engine._decode_crop(original_bytes)
        if method == "gradcam":
            maps = [engine._gradcam(crop, engine.models[name])[0] for name in MODEL_ORDER]
            raw = np.mean(np.stack(maps), axis=0)
            maxval = float(raw.max())
            raw = raw / maxval if maxval > 0 else raw
        else:
            raw = None
    if method == "lime":
        raw = _lime_map(engine, crop, lime_samples)
    elif method == "shap":
        raw = _shap_map(engine, crop, shap_evals)

    assert raw is not None
    region = _region_summary(crop, raw, method, landmarker_task)
    method_notes = {
        "gradcam": (
            "Average of four CNN Fake-output Grad-CAM maps for the original (unflipped) "
            "face crop; this is NOT a direct explanation of the stacking/TTA result. "
            "Highlights do not prove local manipulation."
        ),
        "lime": (
            "Local surrogate approximating the same four-model TTA stacking Fake score. "
            "Red areas locally support Fake, blue areas oppose it. "
            "Segments depend on the image perturbation and sampling procedure."
        ),
        "shap": (
            "Partition SHAP on the same four-model TTA stacking Fake score, relative "
            "to a blurred-image masking reference. Red areas increase Fake score, "
            "blue areas decrease it relative to that reference."
        ),
    }
    meta = {
        "method": method,
        "status": "completed",
        "target_label": "Fake",
        "coordinate_space": "face_crop_224_rgb",
        "face_crop": crop_info,
        "model_version": engine.model_version,
        "interpretation": region,
        "note": method_notes[method],
        "parameters": (
            {"source": "mean_of_four_original_view_backbone_maps"} if method == "gradcam"
            else {"random_state": 42, "samples": lime_samples, "hide_color": 0} if method == "lime"
            else {"max_evals": shap_evals, "masker": "blur(16,16)", "output_names": ["Real", "Fake"]}
        ),
    }
    png = None if method == "gradcam" else signed_overlay(crop, raw)
    return png, meta
