"""Smoke-test new four-model NeuralEdge engine locally (without starting FastAPI).

Usage from backend directory:
  python tools/smoke_v2.py --bundle artifacts_v2/deployment_bundle --image C:/path/test.png

Only use the trusted Kaggle export. Output PNGs are written to a separate folder.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.inference_v2 import InferenceEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("v2-smoke-results"))
    args = parser.parse_args()
    manifest = args.bundle / "deployment_config.json"
    engine = InferenceEngine(manifest)
    print("Loading four trained models and stacking learner...")
    engine.load()
    if not engine.ready:
        raise RuntimeError(f"Engine not ready: {engine.reason}; inspect logs above")
    raw = args.image.read_bytes()
    result, assets = engine.predict(raw)
    assert result["mode"] == "stacking"
    assert result["tta_applied"] is True
    assert set(result["members"]) == {"MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0"}
    assert set(assets) == {"heatmap", "overlay"}
    args.output.mkdir(parents=True, exist_ok=True)
    for name, png_bytes in assets.items():
        (args.output / (name + ".png")).write_bytes(png_bytes)
    (args.output / "prediction.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "prediction", "fake_probability", "real_probability", "confidence", "threshold",
        "model", "mode", "face_detected", "tta_applied")}, indent=2))
    print("V2 SMOKE TEST PASSED. Results saved under", args.output.resolve())
    print("Compare probability with new-deepfake-2.ipynb Cell 15, using the SAME input image.")


if __name__ == "__main__":
    main()
