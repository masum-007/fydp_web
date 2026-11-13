"""Optional per-evidence XAI service for NeuralEdge v2 four-model stacking.

XAI is generated on the EXACT 224x224 MTCNN face crop used by inference.
The predictor for LIME/SHAP is the engine's ORIGINAL + FLIPPED TTA stacking
wrapper. New maps target the predicted Real or Fake category.

- Grad-CAM: four CNN predicted-category maps averaged, NOT final stacking attribution.
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
    """Red=supports the explicitly chosen target category; blue=opposes it.

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


def shap_target_attributions(values, target_label):
    """Select signed SHAP values for an EXPLICIT Real/Fake output index.

    Predictor order is [Real, Fake]. Do not silently reframe an old Fake map
    as a Real map; these must come from an actual target-specific explanation.
    """
    import numpy as np

    if target_label not in ("Real", "Fake"):
        raise ValueError("SHAP target must be Real or Fake")
    arr = np.asarray(values, dtype=np.float32)
    if arr.shape != (1, 224, 224, 3, 2):
        raise ValueError(
            f"Unsupported SHAP output shape {arr.shape}; expected (1,224,224,3,2) "
            "with outputs ['Real','Fake']."
        )
    if not np.isfinite(arr).all():
        raise ValueError("SHAP returned nonfinite values")
    return arr[0, ..., 0 if target_label == "Real" else 1].sum(axis=-1)


def shap_fake_attributions(values):
    """Legacy helper for old unit tests and historical Fake-target output."""
    return shap_target_attributions(values, "Fake")


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


def _region_summary(face_crop, raw, method, landmarker_task, target_label="Fake",
                    gradcam_members=None):
    """Fail closed: no named facial region when detection is unavailable."""
    if not landmarker_task or not Path(landmarker_task).is_file():
        return {
            "status": "not_configured",
            "narrative": "Facial-region localization is not configured. See the explanation image and method notes.",
            "regions": [],
        }
    try:
        from .face_region_interpreter import summarize_xai_regions

        args = (
            {"gradcam_fake": raw, "gradcam_target": target_label}
            if method == "gradcam"
            else {f"{method}_signed": raw, f"{method}_target": target_label}
        )
        if method == "gradcam" and gradcam_members:
            args["gradcam_members"] = gradcam_members
        summary = summarize_xai_regions(face_crop, str(landmarker_task), **args)
        method_key = method.upper() if method != "gradcam" else "Grad-CAM"
        return {
            "status": summary["status"],
            "narrative": summary.get("narratives", {}).get(
                method_key, summary.get("note", "No reliable region localized.")),
            "regions": summary.get("ranked_regions", {}).get(method_key, {}),
            "regional_metrics": summary.get("regional_metrics", {}).get(method_key, {}),
            "model_comparison": summary.get("model_comparison") if method == "gradcam" else None,
            "region_note": summary.get("note", ""),
        }
    except Exception:
        LOG.exception("Facial-region interpretation unavailable for %s", method)
        return {
            "status": "unavailable",
            "narrative": "Facial landmarks could not be localized reliably; no specific facial feature is identified.",
            "regions": [],
        }



def gradcam_metadata_from_map(face_crop, normalized_gradcam, *, model_version,
                              face_detected, weak_activation=False,
                              landmarker_task=None, target_label="Fake",
                              per_model_maps=None):
    """Record a truthful interpretation of a *previously computed* CNN Grad-CAM map.

    No model inference here. This is called in normal analysis immediately after
    the four CNN maps are averaged. Missing MediaPipe is not a failure.
    """
    from datetime import datetime, timezone
    import numpy as np

    if target_label not in ("Real", "Fake"):
        raise ValueError("Grad-CAM target must be Real or Fake")
    heat = np.asarray(normalized_gradcam, dtype=np.float32)
    if heat.shape != (224, 224) or not np.isfinite(heat).all():
        raise ValueError("Invalid Grad-CAM map geometry or values")
    if weak_activation or float(heat.max()) <= 1e-12:
        region = {
            "status": "weak_activation", "regions": [],
            "narrative": "Grad-CAM was generated, but the activation was too weak to identify a reliable facial region.",
        }
    elif not face_detected:
        region = {
            "status": "no_primary_face", "regions": [],
            "narrative": "Grad-CAM was generated on a center crop because the face detector found no reliable face. No facial feature is named.",
        }
    else:
        region = _region_summary(face_crop, heat, "gradcam", landmarker_task,
                                 target_label, gradcam_members=per_model_maps)
    return {
        "method": "gradcam", "status": "completed", "target_label": target_label,
        "coordinate_space": "face_crop_224_rgb", "model_version": model_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "interpretation": region,
        "note": (
            f"Mean of four original-view CNN {target_label}-category Grad-CAM maps. "
            "The maps are not a direct explanation of the stacking/TTA decision; "
            "highlighted regions do not prove manipulation or authenticity."
        ),
        "parameters": {"source": "mean_of_four_original_view_backbone_maps"},
    }


def _lime_map(engine, crop_rgb, num_samples, target_label="Fake"):
    from lime.lime_image import LimeImageExplainer

    if target_label not in ("Real", "Fake"):
        raise ValueError("LIME target must be Real or Fake")
    target_index = 0 if target_label == "Real" else 1
    explainer = LimeImageExplainer(random_state=42)
    explanation = explainer.explain_instance(
        crop_rgb,
        classifier_fn=engine.predict_proba_from_face_crops,
        labels=(target_index,),
        hide_color=0,
        num_samples=num_samples,
        batch_size=4,
    )
    weights = explanation.local_exp.get(target_index)
    if not weights:
        raise ValueError(f"LIME did not return {target_label}-class weights")
    return lime_fake_attributions(explanation.segments, weights)


def _shap_map(engine, crop_rgb, max_evals, target_label="Fake"):
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
    return shap_target_attributions(explained.values, target_label)


def generate_explanation(engine, original_bytes: bytes, method: str, *,
                         landmarker_task: str | None = None,
                         lime_samples: int = 150,
                         shap_evals: int = 120,
                         target_label: str = "Fake"):
    """Return (PNG bytes or None, JSON-safe metadata), no database writes.

    This takes some time on CPU: call only from authenticated, resource-limited
    on-demand endpoint. It never revises the original model decision.
    """
    import numpy as np
    from .inference_v2 import MODEL_ORDER

    if method not in SUPPORTED_METHODS:
        raise ValueError("Unknown explanation method")
    if target_label not in ("Real", "Fake"):
        raise ValueError("Explanation target must be Real or Fake")
    if not getattr(engine, "ready", False):
        raise RuntimeError("V2 inference engine is not ready")

    with engine.lock:
        crop, crop_info = engine._decode_crop(original_bytes)
        if method == "gradcam":
            member_maps = {
                name: engine._gradcam(crop, engine.models[name],
                                      target_label=target_label)[0]
                for name in MODEL_ORDER
            }
            raw = np.mean(np.stack(list(member_maps.values())), axis=0)
            maxval = float(raw.max())
            raw = raw / maxval if maxval > 0 else raw
        else:
            raw = None
    if method == "lime":
        raw = _lime_map(engine, crop, lime_samples, target_label)
    elif method == "shap":
        raw = _shap_map(engine, crop, shap_evals, target_label)

    assert raw is not None
    region = _region_summary(
        crop, raw, method, landmarker_task, target_label,
        gradcam_members=member_maps if method == "gradcam" else None,
    )
    method_notes = {
        "gradcam": (
            f"Mean of four CNN original-view {target_label}-category Grad-CAM maps; "
            "these are not a direct explanation of the stacking/TTA classifier. "
            "Bright areas indicate relative activation, not verified edits."
        ),
        "lime": (
            f"LIME locally approximates the four-model TTA stacking {target_label} output. "
            f"Red segments support {target_label}; blue segments oppose it. "
            "Results depend on masking, segmentation and sampling."
        ),
        "shap": (
            f"Partition SHAP explains the four-model TTA stacking {target_label} output "
            "relative to a blurred-image reference. "
            f"Red regions support {target_label}; blue regions oppose it."
        ),
    }
    meta = {
        "method": method,
        "status": "completed",
        "target_label": target_label,
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
