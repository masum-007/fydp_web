"""NeuralEdge v2: trusted four-backbone TTA + logistic stacking inference.

Canonical source: new-deepfake-2.ipynb cells 2, 7, 8, 10, 14 and 15.

Input: original JPEG/PNG bytes. Face crop: MTCNN, largest bounding box,
25% margin, 1:1 square, OpenCV INTER_AREA / INTER_CUBIC resize to 224.
Prediction: mean of each model's original + horizontally flipped predictions,
then logistic-regression predict_proba on [MobileNetV2, ResNet50V2, Xception,
EfficientNetB0] in that exact order. All models embed preprocessing.

IMPORTANT: The notebook validation/test pipeline also used a fixed JPEG+blur
'evaluation equalizer', but its exported production smoke test did not.
This adapter deliberately matches that exported *production* inference path.
Treat test metrics as not directly established for this path until parity is
measured. Do not add the equalizer silently or claim exact test-set accuracy.

Grad-CAM is a mean of four CNN *predicted-category*, original-view spatial attribution
maps, NOT a direct explanation of stacking or test-time augmentation. Its
coordinate system is the analyzed face crop, not the original full image.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import math
from pathlib import Path
from threading import Lock

from .prediction import classify

LOG = logging.getLogger(__name__)
MODEL_ORDER = ("MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_deployment_config(config_path: str | Path):
    """Validate trusted bundle layout before loading Keras/joblib code."""
    config_path = Path(config_path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    spec = cfg.get("input_specification", {})
    if (spec.get("width"), spec.get("height"), spec.get("channels")) != (224, 224, 3):
        raise ValueError("Expected 224 x 224 x 3 input specification.")
    if spec.get("color_space") != "RGB" or spec.get("pixel_value_range") != [0, 255]:
        raise ValueError("Expected RGB images with raw pixel values in [0, 255].")
    if spec.get("tta_enabled") is not True:
        raise ValueError("The exported stacking learner was trained with TTA features.")
    if cfg.get("positive_class") != "Fake (1)":
        raise ValueError("Expected Fake class (1) as positive class.")
    if cfg.get("models") != [name + ".keras" for name in MODEL_ORDER]:
        raise ValueError("Model ordering differs from the stacking learner's feature order.")
    if cfg.get("stacking_meta_learner") != "stacking_meta_learner.joblib":
        raise ValueError("Unexpected stacking meta-learner filename.")
    t = cfg.get("optimal_youden_threshold")
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or not 0 < t < 1:
        raise ValueError("Invalid saved stacking decision threshold.")
    root = config_path.parent
    files = [root / (name + ".keras") for name in MODEL_ORDER]
    files.append(root / "stacking_meta_learner.joblib")
    for item in files:
        if not item.is_file() or not item.resolve().is_relative_to(root):
            raise FileNotFoundError(f"Missing or unsafe bundle artifact: {item}")
    return cfg, files


def crop_face(rgb, detector, cv2):
    """Reproduce notebook MTCNN largest-face crop; returns RGB crop and metadata.

    The metadata describes the square region in source-image pixel coordinates.
    If the detector finds no usable face, we deliberately use a center crop
    (matching the notebook) and disclose it to callers.
    """
    import numpy as np

    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[-1] != 3 or rgb.dtype != np.uint8:
        raise ValueError("Expected RGB uint8 image of shape H x W x 3")
    height, width = rgb.shape[:2]
    if height < 2 or width < 2:
        raise ValueError("Image too small")
    faces = detector.detect_faces(rgb) or []
    valid_faces = []
    for face in faces:
        try:
            x, y, w, h = (int(v) for v in face["box"])
            if w > 0 and h > 0:
                valid_faces.append((w * h, x, y, w, h))
        except (KeyError, TypeError, ValueError):
            continue
    if valid_faces:
        _, x, y, w, h = max(valid_faces, key=lambda v: v[0])
        cx, cy = x + w // 2, y + h // 2
        side = int(max(w, h) * 1.5)  # 25% margin per side
        side = min(min(width, height), max(32, side))
        x1 = max(0, min(width - side, cx - side // 2))
        y1 = max(0, min(height - side, cy - side // 2))
        face_detected = True
    else:
        side = min(width, height)
        x1, y1 = (width - side) // 2, (height - side) // 2
        face_detected = False
    square = rgb[y1:y1 + side, x1:x1 + side]
    interpolation = cv2.INTER_AREA if square.shape[0] > 224 else cv2.INTER_CUBIC
    crop = cv2.resize(square, (224, 224), interpolation=interpolation)
    info = {"face_detected": face_detected, "faces_detected": len(valid_faces),
            "x": int(x1), "y": int(y1), "side": int(side),
            "coordinate_space": "original_image", "crop_size": [224, 224],
            "primary_face_only": True}
    return crop, info


class InferenceEngine:
    def __init__(self, manifest_path):
        # Existing Settings.model_manifest now points to deployment_config.json.
        self.path = Path(manifest_path)
        self.ready = False
        self.reason = "MODEL_NOT_CONFIGURED"
        self.lock = Lock()
        self.models = {}
        self.model_artifacts = []

    def load(self):
        self.ready = False
        self.reason = "MODEL_NOT_CONFIGURED"
        if not self.path.is_file():
            return
        try:
            cfg, files = check_deployment_config(self.path)
            import cv2
            import joblib
            import numpy as np
            import tensorflow as tf
            from mtcnn import MTCNN

            self.cv2, self.np, self.tf = cv2, np, tf
            self.cfg = cfg
            self.threshold = float(cfg["optimal_youden_threshold"])
            self.model_artifacts = [
                {"name": name, "sha256": _sha256_file(path)}
                for name, path in zip([*MODEL_ORDER, "StackingMetaLearner"], files)
            ]
            self.model_version = hashlib.sha256(
                json.dumps({"config_sha256": _sha256_file(self.path),
                            "artifacts": self.model_artifacts}, sort_keys=True).encode("utf-8")
            ).hexdigest()
            loaded = {}
            for name, path in zip(MODEL_ORDER, files[:4]):
                model = tf.keras.models.load_model(path, compile=False, safe_mode=True)
                if tuple(model.input_shape) != (None, 224, 224, 3) or tuple(model.output_shape) != (None, 1):
                    raise ValueError(f"Unexpected input/output shape: {name}")
                if model.name != name:
                    raise ValueError(f"Model name differs from expected: {name}")
                layer = model.get_layer("preprocess_rescaling")
                if not isinstance(layer, tf.keras.layers.Rescaling):
                    raise ValueError(f"Incorrect preprocessing layer in {name}")
                spec = layer.get_config()
                expected_scale, expected_offset = ((1.0, 0.0) if name == "EfficientNetB0"
                                                   else (1.0 / 127.5, -1.0))
                if (not math.isclose(float(spec["scale"]), expected_scale, rel_tol=1e-5, abs_tol=1e-7)
                        or not math.isclose(float(spec["offset"]), expected_offset, abs_tol=1e-7)):
                    raise ValueError(f"Unexpected rescaling in {name}")
                if model.get_layer("prob_fake").get_config()["activation"] != "sigmoid":
                    raise ValueError(f"Unexpected output class mapping in {name}")
                loaded[name] = model
            learner = joblib.load(files[4])  # Only load YOUR Kaggle export; joblib executes Python code.
            if (int(getattr(learner, "n_features_in_", 0)) != 4
                    or list(getattr(learner, "classes_", [])) != [0, 1]):
                raise ValueError("Stacking meta-learner has unexpected feature order/labels")
            if not hasattr(learner, "predict_proba"):
                raise ValueError("Meta-learner lacks predict_proba")
            self.models = loaded
            self.learner = learner
            self.detector = MTCNN()
            # Exercise ensemble graph once before reporting ready.
            blank = np.zeros((2, 224, 224, 3), np.float32)
            self._member_scores(blank)
            self.reason = None
            self.ready = True
        except Exception:
            LOG.exception("NeuralEdge v2 model startup failed")
            self.models = {}
            self.ready = False
            self.reason = "MODEL_LOAD_FAILED"

    def _member_scores(self, augmented_batch):
        """Batched ORIGINAL+FLIP prediction, exactly two views per crop."""
        result = {}
        for name in MODEL_ORDER:
            values = self.np.asarray(
                self.models[name].predict(augmented_batch, verbose=0), dtype="float64"
            ).reshape(-1)
            if values.shape != (len(augmented_batch),) or not self.np.isfinite(values).all():
                raise ValueError(f"Invalid network output from {name}")
            if (values < 0).any() or (values > 1).any():
                raise ValueError(f"Network probabilities outside [0, 1]: {name}")
            result[name] = values
        return result

    def _score_crops(self, crops):
        """Core classifier on ALREADY CROPPED 224 RGB images, with TTA.

        This is also the exact prediction wrapper for future LIME/SHAP methods;
        explanation perturbations happen in crop coordinates, without rerunning MTCNN.
        """
        np = self.np
        arr = np.asarray(crops, dtype=np.float32)
        if arr.ndim != 4 or arr.shape[1:] != (224, 224, 3):
            raise ValueError("Expected a batch of 224 x 224 RGB face crops")
        if not np.isfinite(arr).all() or (arr < 0).any() or (arr > 255).any():
            raise ValueError("Crops must contain finite RGB values in [0,255]")
        augmented = np.empty((2 * len(arr), 224, 224, 3), dtype=np.float32)
        augmented[0::2] = arr
        augmented[1::2] = arr[:, :, ::-1, :]
        views = self._member_scores(augmented)
        member_probs = {name: scores.reshape(len(arr), 2).mean(axis=1)
                        for name, scores in views.items()}
        features = np.column_stack([member_probs[name] for name in MODEL_ORDER])
        probs = np.asarray(self.learner.predict_proba(features), dtype=np.float64)
        if probs.shape != (len(arr), 2) or not np.isfinite(probs).all():
            raise ValueError("Meta-learner returned invalid predictions")
        if (probs < 0).any() or (probs > 1).any():
            raise ValueError("Stacking probabilities outside [0, 1]")
        return probs[:, 1], member_probs

    def predict_proba_from_face_crops(self, face_crops_rgb):
        """Future SHAP/LIME adapter: predict [P(Real), P(Fake)] with same TTA.

        Input must be 224x224 cropped RGB images in [0,255]. This method
        handles multiple perturbed crops in small batches to cap memory.
        """
        np = self.np
        x = np.asarray(face_crops_rgb)
        if x.ndim == 3:
            x = x[None, ...]
        if x.ndim != 4 or x.shape[1:] != (224, 224, 3):
            raise ValueError("Expected RGB crops with shape (N, 224, 224, 3)")
        results = []
        with self.lock:
            for start in range(0, len(x), 8):
                p, _ = self._score_crops(x[start:start + 8])
                results.append(np.column_stack([1.0 - p, p]))
        return np.concatenate(results, axis=0) if results else np.empty((0, 2))

    def _decode_crop(self, raw):
        np, cv2 = self.np, self.cv2
        data = np.frombuffer(raw, dtype=np.uint8)
        bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("Could not decode JPEG/PNG image")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return crop_face(rgb, self.detector, cv2)

    def _gradcam(self, face_crop, model, target_label="Fake"):
        """Per-backbone original-view class-specific Grad-CAM.

        Real target is 1 - sigmoid(Fake). The mean of member maps remains
        separate from and does not explain the stacking meta-learner.
        """
        if target_label not in ("Real", "Fake"):
            raise ValueError("Grad-CAM target must be Real or Fake")
        tf, np, cv2 = self.tf, self.np, self.cv2
        rescaling = model.get_layer("preprocess_rescaling")
        backbone_index = next((i for i, layer in enumerate(model.layers)
                               if isinstance(layer, tf.keras.Model)), None)
        if backbone_index is None:
            raise ValueError("No nested CNN backbone found")
        backbone = model.layers[backbone_index]
        head_layers = model.layers[backbone_index + 1:]
        batch = tf.convert_to_tensor(face_crop[None, ...], dtype=tf.float32)
        with tf.GradientTape() as tape:
            scaled = rescaling(batch)
            fmap = backbone(scaled, training=False)
            tape.watch(fmap)
            x = fmap
            for layer in head_layers:
                x = layer(x, training=False)
            fake_score = x[:, 0]
            target_score = fake_score if target_label == "Fake" else 1.0 - fake_score
        grads = tape.gradient(target_score, fmap)
        if grads is None:
            raise ValueError("Disconnected Grad-CAM gradients")
        weights = tf.reduce_mean(tf.cast(grads, tf.float32), axis=(0, 1, 2))
        activation = tf.reduce_sum(tf.cast(fmap[0], tf.float32) * weights, axis=-1)
        activation = tf.nn.relu(activation)
        activation = tf.math.divide_no_nan(activation, tf.reduce_max(activation))
        raw = np.asarray(activation.numpy(), dtype=np.float32)
        if not np.isfinite(raw).all():
            raise ValueError("Grad-CAM map contains invalid values")
        return cv2.resize(raw, (224, 224), interpolation=cv2.INTER_LINEAR), backbone.name

    def predict(self, data: bytes):
        if not self.ready:
            raise RuntimeError("Inference engine is not ready")
        with self.lock:
            face_crop, face_info = self._decode_crop(data)
            fake_probs, per_model = self._score_crops(face_crop[None, ...])
            prob = float(fake_probs[0])
            decision = classify(prob, self.threshold)
            members = {name: classify(float(per_model[name][0]), 0.5) for name in MODEL_ORDER}
            # Average of four CNN maps: not a gradient of the stacking learner.
            maps, layers = [], {}
            for name in MODEL_ORDER:
                heat, layer_name = self._gradcam(
                    face_crop, self.models[name], target_label=decision["prediction"]
                )
                maps.append(heat)
                layers[name] = layer_name
            avg = self.np.mean(self.np.stack(maps), axis=0)
            maxval = float(avg.max())
            avg = avg / maxval if maxval > 0 else avg
            color = self.cv2.applyColorMap(
                (self.np.clip(avg, 0, 1) * 255).astype(self.np.uint8),
                self.cv2.COLORMAP_JET,
            )
            color = self.cv2.cvtColor(color, self.cv2.COLOR_BGR2RGB)
            overlay = self.cv2.addWeighted(face_crop, 0.60, color, 0.40, 0)
            assets = {}
            for name, image in (("heatmap", color), ("overlay", overlay)):
                ok, png = self.cv2.imencode(".png", self.cv2.cvtColor(image, self.cv2.COLOR_RGB2BGR))
                if not ok:
                    raise RuntimeError("Could not encode Grad-CAM PNG")
                assets[name] = png.tobytes()
            # Convert the Grad-CAM map already computed above into a saved,
            # method-specific interpretation. Do NOT recompute Grad-CAM.
            # Failure/missing MediaPipe asset must not break inference.
            import os
            from .explainability_service import gradcam_metadata_from_map
            gradcam_meta = gradcam_metadata_from_map(
                face_crop, avg,
                model_version=self.model_version,
                face_detected=bool(face_info["face_detected"]),
                weak_activation=bool(maxval <= 1e-12),
                landmarker_task=os.getenv("FACE_LANDMARKER_TASK"),
                target_label=decision["prediction"],
                per_model_maps=dict(zip(MODEL_ORDER, maps)),
            )
            explanation = {
                "method": "Grad-CAM",
                "model": "Four backbone mean",
                "target_label": decision["prediction"],
                "threshold": self.threshold,
                "fake_probability": prob,
                "layer": "Last nested backbone feature map per model",
                "layers": layers,
                "weak_activation": bool(maxval <= 0),
                "scope": "mean_per_model_original_view_not_stacking",
                "coordinate_space": "face_crop_224_rgb",
                "note": "Mean of four predicted-class CNN Grad-CAM maps for the original face crop. This is not a gradient explanation of the stacking classifier or its flipped-image TTA. Bright regions are not evidence of editing.",
            }
            result = {
                **decision,
                "model": "FourModelStacking",
                "mode": "stacking",
                "model_version": self.model_version,
                "model_artifacts": self.model_artifacts,
                "preprocessing": "mtcnn_square_face_margin25_opencv224_rgb_raw255_no_eval_equalizer_tta_orig_flip_v1",
                "tta_applied": True,
                "face_detected": face_info["face_detected"],
                "face_crop": face_info,
                "soft_vote_fake_probability": float(self.np.mean([per_model[n][0] for n in MODEL_ORDER])),
                "members": members,
                "explanation": explanation,
                "xai": {"gradcam": gradcam_meta},
            }
            return result, assets
