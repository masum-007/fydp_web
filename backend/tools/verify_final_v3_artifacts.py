"""NeuralEdge final v3 deployment sanity checker.

Use only on a trusted bundle exported by YOUR Kaggle notebook.
Usage:
  python tools/verify_final_v3_artifacts.py artifacts/deployment_config.json
  python tools/verify_final_v3_artifacts.py artifacts/deployment_config.json --smoke-image path/to/test_image.jpg
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
import zipfile
from pathlib import Path

EXPECTED = ("MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0")


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Preflight check for NeuralEdge v3 deployment")
    parser.add_argument("config", type=Path, help="Path to deployment_config.json")
    parser.add_argument("--smoke-image", type=Path, help="Optional image for full TensorFlow/FastAPI inference smoke test")
    args = parser.parse_args()
    root = args.config.expanduser().resolve().parent
    problems = []
    warnings_list = []
    def check(ok, label):
        print(("PASS" if ok else "FAIL") + "  " + label)
        if not ok:
            problems.append(label)

    def note(text):
        print("INFO  " + text)

    check(args.config.is_file(), "deployment_config.json is present")
    if not args.config.is_file():
        return 1
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        check(False, f"Deployment configuration parses as JSON: {e}")
        return 1
    check(cfg.get("model_order") == list(EXPECTED), "Four-model stacking feature order")
    check(cfg.get("models") == [x + ".keras" for x in EXPECTED], "Four Keras model filenames")
    check(cfg.get("stacking_meta_learner") == "stacking_meta_learner.joblib", "Stacking learner filename")
    spec = cfg.get("input_specification", {})
    check((spec.get("width"), spec.get("height"), spec.get("channels")) == (224, 224, 3), "224 x 224 RGB input")
    check(spec.get("color_space") == "RGB" and spec.get("pixel_value_range") == [0, 255], "Raw RGB [0,255] preprocessing")
    check(spec.get("tta_enabled") is True, "Original + horizontal-flip TTA")
    check(cfg.get("positive_class") == "Fake (1)", "Fake is the positive class")
    threshold = cfg.get("operating_threshold")
    check(isinstance(threshold, (float, int)) and not isinstance(threshold, bool) and
          math.isfinite(threshold) and threshold == 0.5 and
          cfg.get("optimal_youden_threshold") == threshold, "Saved operating threshold = 0.50 (legacy alias agrees)")
    check(cfg.get("preprocessing") == "mtcnn_square_face_margin25_opencv224_rgb_raw255_no_eval_equalizer_tta_orig_flip_v1", "Preprocessing identifier")
    expected_files = [name + ".keras" for name in EXPECTED] + ["stacking_meta_learner.joblib", "deployment_config.json", "xai_report_contract.json", "sha256_checksums.json", "threshold_selection_protocol.json", "environment_versions.json"]
    for fname in expected_files:
        check((root / fname).is_file(), f"Exists: {fname}")

    hashes = root / "sha256_checksums.json"
    if hashes.is_file():
        try:
            hashes_dict = json.loads(hashes.read_text(encoding="utf-8"))
            for fname, expected_hash in hashes_dict.items():
                p = (root / fname).resolve()
                if not p.is_relative_to(root) or not p.is_file():
                    check(False, f"Checksum file missing or unsafe: {fname}")
                else:
                    check(sha256(p) == expected_hash, f"SHA-256: {fname}")
        except (ValueError, OSError) as e:
            check(False, f"Read checksums: {e}")

    for name in EXPECTED:
        p = root / (name + ".keras")
        if not p.is_file():
            continue
        try:
            check(zipfile.is_zipfile(p), f"Native Keras archive structure: {p.name}")
            if zipfile.is_zipfile(p):
                with zipfile.ZipFile(p) as z:
                    members = set(z.namelist())
                    check("config.json" in members and "metadata.json" in members,
                          f"Keras config and metadata present: {p.name}")
        except (OSError, zipfile.BadZipFile) as e:
            check(False, f"Keras archive read: {p.name}: {e}")

    meta = root / "stacking_meta_learner.joblib"
    if meta.is_file():
        try:
            import joblib
            import numpy as np
            import sklearn
            # Only load a trusted joblib file: pickle deserialization can execute code.
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                learner = joblib.load(meta)
            sklearn_warn = [str(w.message) for w in captured if "InconsistentVersionWarning" in str(w.category)]
            check(getattr(learner, "n_features_in_", None) == 4 and list(getattr(learner, "classes_", [])) == [0, 1], "Stacking learner input dimensions and labels")
            coefficients = [cfg.get("stacking_coefficients", {}).get(x) for x in EXPECTED]
            check(all(x is not None for x in coefficients) and np.allclose(learner.coef_[0], coefficients, rtol=1e-10, atol=1e-12) and
                  np.allclose(learner.intercept_[0], cfg.get("stacking_intercept"), rtol=1e-10, atol=1e-12), "Serialized stacking coefficients agree with config")
            note(f"Local scikit-learn: {sklearn.__version__}")
            if sklearn_warn:
                warnings_list.extend(sklearn_warn)
        except ImportError as e:
            warnings_list.append(f"Stacking numerical check skipped; dependency missing: {e}")
        except Exception as e:
            check(False, f"Loading/validating trusted stacking learner: {e}")

    contract = root / "xai_report_contract.json"
    if contract.is_file():
        try:
            xai = json.loads(contract.read_text(encoding="utf-8"))
            check("blur(32,32)" in xai.get("shap", {}).get("source", ""), "SHAP reference recorded as blur(32,32)")
            check(xai.get("pdf_logic", {}).get("optional", "").lower().find("until user requests") >= 0, "LIME/SHAP opt-in narrative contract")
        except (ValueError, OSError) as e:
            check(False, f"Read XAI contract: {e}")

    if args.smoke_image:
        image = args.smoke_image.expanduser().resolve()
        check(image.is_file(), "Smoke image exists")
        if image.is_file() and not problems:
            try:
                from app.inference_v2 import InferenceEngine
                engine = InferenceEngine(args.config)
                engine.load()
                check(engine.ready, f"FastAPI inference engine ready (reason={engine.reason})")
                if engine.ready:
                    result, assets = engine.predict(image.read_bytes())
                    note(f"Real image prediction: {result['prediction']}, Fake score={result['fake_probability']:.8f}, threshold={result['threshold']:.2f}")
                    check(all(x in assets for x in ("overlay", "heatmap")), "Class-aware Grad-CAM assets generated")
                    check("gradcam" in result.get("xai", {}), "Per-image Grad-CAM explanation metadata")
                    note("Compare this Fake score with the SAME source image's saved Kaggle prediction ledger.")
            except Exception as e:
                check(False, f"Full inference smoke test: {e}")
    if warnings_list:
        print("\nWarnings:")
        for message in warnings_list:
            print("WARN  " + message)
    print("\n" + ("FAILED" if problems else "PREFLIGHT PASSED") + f" - {len(problems)} issue(s)")
    if not args.smoke_image:
        note("For full CPU/GPU load, Grad-CAM, and numerical parity, rerun with --smoke-image after installing all runtime dependencies.")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
