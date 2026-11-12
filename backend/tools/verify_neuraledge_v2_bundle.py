"""Verify trusted Kaggle four-model deployment exports without modifying the FYDP backend.

Run from backend:
 python tools/verify_neuraledge_v2_bundle.py --bundle artifacts_v2/deployment_bundle --image sample.jpg

Only load .joblib files you generated yourself. Pick a non-sensitive test image.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

EXPECTED = ("MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0")


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def load_bundle(path):
    import joblib  # trusted local file only
    import numpy as np
    import tensorflow as tf

    meta_path = path / "deployment_config.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Missing deployment metadata: {meta_path}")
    cfg = json.loads(meta_path.read_text(encoding="utf8"))
    if cfg.get("input_specification", {}).get("width") != 224 or cfg.get("input_specification", {}).get("height") != 224:
        raise ValueError("Unexpected image size; expected 224 x 224")
    if cfg.get("positive_class") != "Fake (1)":
        raise ValueError("Unexpected positive-class mapping")
    models_list = cfg.get("models")
    if models_list != [f"{name}.keras" for name in EXPECTED]:
        raise ValueError(f"Unexpected model order: {models_list!r}; expected {EXPECTED}")
    files = [path / file for file in models_list]
    meta_file = path / cfg.get("stacking_meta_learner", "")
    for f in files + [meta_file]:
        if not f.is_file() or not f.resolve().is_relative_to(path.resolve()):
            raise FileNotFoundError(f"Required bundle file missing/outside directory: {f}")
    threshold = float(cfg.get("optimal_youden_threshold", float("nan")))
    if not math.isfinite(threshold) or not (0 < threshold < 1):
        raise ValueError("Invalid decision threshold")
    print(f"TensorFlow version: {tf.__version__}; notebook export: {cfg.get('tensorflow_version')}")
    print(f"Threshold: {threshold:.4f}; TTA enabled in export: {cfg.get('input_specification', {}).get('tta_enabled')}")
    models = {}
    for name, f in zip(EXPECTED, files):
        print(f"Loading {name} ({f.stat().st_size / 2**20:.1f} MiB) ...")
        m = tf.keras.models.load_model(f, compile=False, safe_mode=True)
        if tuple(m.input_shape) != (None, 224, 224, 3) or tuple(m.output_shape) != (None, 1):
            raise ValueError(f"Unexpected input/output tensor shapes for {name}")
        if m.get_layer("prob_fake").get_config()["activation"] != "sigmoid":
            raise ValueError(f"Expected sigmoid fake-class output: {name}")
        layer = m.get_layer("preprocess_rescaling")
        if not isinstance(layer, tf.keras.layers.Rescaling):
            raise ValueError(f"Missing expected preprocessing layer: {name}")
        scale = float(layer.get_config()["scale"])
        offset = float(layer.get_config()["offset"])
        target_scale, target_offset = (1, 0) if name == "EfficientNetB0" else (1 / 127.5, -1)
        if not math.isclose(scale, target_scale, rel_tol=1e-5) or not math.isclose(offset, target_offset, abs_tol=1e-6):
            raise ValueError(f"Preprocessing differs from notebook for {name}")
        models[name] = m
        print(f"  OK; SHA-256: {hash_file(f)}")
    learner = joblib.load(meta_file)  # no arbitrary .joblib files from the Internet
    if getattr(learner, "n_features_in_", None) != 4 or list(learner.classes_) != [0, 1]:
        raise ValueError("Stacking learner expects unexpected features/classes")
    print(f"Stacking learner OK; SHA-256: {hash_file(meta_file)}")
    print("MODEL FILES AND META-LEARNER VERIFIED")
    return cfg, models, learner


def face_crop(rgb, target_size=(224, 224)):
    import cv2
    from mtcnn import MTCNN
    detector = MTCNN()
    height, width = rgb.shape[:2]
    faces = detector.detect_faces(rgb)
    if faces:
        box = max(faces, key=lambda f: f["box"][2] * f["box"][3])["box"]
        x, y, w, h = [int(v) for v in box]
        cx, cy = x + w // 2, y + h // 2
        side = max(32, min(int(max(w, h) * 1.5), min(width, height)))
        x1 = max(0, min(width - side, cx - side // 2))
        y1 = max(0, min(height - side, cy - side // 2))
        found = True
    else:
        side = min(width, height)
        x1, y1 = (width - side) // 2, (height - side) // 2
        found = False
    crop = rgb[y1:y1 + side, x1:x1 + side]
    interp = cv2.INTER_AREA if crop.shape[0] > target_size[0] else cv2.INTER_CUBIC
    return cv2.resize(crop, target_size, interpolation=interp), found


def evaluate(img_rgb, models, learner, threshold, equalized=False):
    import cv2
    import numpy as np
    rgb = img_rgb.copy()
    if equalized:
        # Diagnostic approximation of notebook eval_equalizer; Albumentations
        # version and JPEG handling can affect byte-exact reproducibility.
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        ok, compressed = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok: raise RuntimeError('JPEG encoding failed')
        bgr = cv2.imdecode(compressed, cv2.IMREAD_COLOR)
        bgr = cv2.GaussianBlur(bgr, (3, 3), 0)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    x = rgb.astype(np.float32)
    batch = np.stack([x, x[:, ::-1, :]], axis=0)
    members = {}
    for name in EXPECTED:
        prob = np.asarray(models[name].predict(batch, verbose=0)).reshape(-1)
        if len(prob) != 2 or not np.isfinite(prob).all():
            raise RuntimeError(f"Non-finite/invalid output from {name}")
        members[name] = float(prob.mean())
    features = np.array([[members[name] for name in EXPECTED]])
    probability = float(learner.predict_proba(features)[0, 1])
    return {'prediction': 'Fake' if probability >= threshold else 'Real',
            'stacking_fake_probability': round(probability, 6),
            'threshold': threshold, 'members': members}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--image', type=Path, help='Optional consented JPG or PNG test image')
    args = parser.parse_args()
    cfg, models, learner = load_bundle(args.bundle.resolve())
    if args.image:
        import cv2
        import numpy as np
        raw = np.fromfile(str(args.image), dtype=np.uint8)
        bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if bgr is None: raise ValueError('Cannot decode the provided image')
        crop, found = face_crop(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        threshold = float(cfg['optimal_youden_threshold'])
        print('Face detected:', found)
        for eq in [False, True]:
            print(('WITH' if eq else 'WITHOUT') + ' deterministic evaluation equalization:')
            print(json.dumps(evaluate(crop, models, learner, threshold, equalized=eq), indent=2))
        print('NOTE: These two diagnostic pathways may differ; establish and document the canonical web preprocessing before deployment.')


if __name__ == '__main__':
    main()
