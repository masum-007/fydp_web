# FYDP 2 — Backend Stage 2: notebook-derived inference integration

This is a full backend source replacement for Stage 1. Copy `backend/app`, `backend/tools`, `backend/tests`, requirements files and this README into your project's backend folder. Keep your existing `.env`, `storage/` and virtual environment. Do not delete them. The startup schema change is additive (`analyses` table); no existing users/evidence tables are dropped. Back up your local data before applying any update.

The frontend is unchanged. Use Swagger to validate this stage before wiring the UI.

## What the uploaded notebook establishes

| Setting | Verified notebook source/output |
| --- | --- |
| Framework | TensorFlow 2.20.0; notebook Python metadata 3.12.13 |
| Labels | Real=0, Fake=1 |
| Model input | 224x224 RGB float32 with pixels in 0–255 |
| Normalization | Embedded `Rescaling(1/127.5, offset=-1)` layer named `preprocess` |
| Output | One sigmoid probability for Fake |
| Ensemble | Arithmetic mean of three model probabilities, not majority voting |
| Ensemble threshold in recorded run | 0.565 |
| Single-model thresholds | ResNet50V2 0.375; MobileNetV2 0.205; Xception 0.505 |
| Exported deployment model | Best single model, ResNet50V2 in recorded run |
| Explanation | Grad-CAM on best single model's last spatial layer, targeting its own predicted class |

Thresholds are read from your real exported metadata/CSV. They are not hard-coded into inference.

IMPORTANT: `deepfake_detector_best_single.keras` is NOT an ensemble file. The `.ipynb` contains source and saved outputs, not trained weight tensors. You must supply the exports below.

## Files to obtain from Kaggle

Your notebook's final cell creates `/kaggle/working/deepfake_xai_reports.zip`. Download that existing output if available; extract it locally. You do not need to rerun training when the outputs already exist.

Minimum single-model setup:

- `deepfake_detector_best_single.keras`
- `deployment_metadata.json`

For the complete ensemble, also retain:

- `models/MobileNetV2_best.keras`
- `models/ResNet50V2_best.keras`
- `models/Xception_best.keras`
- `reports/validation_all_candidates.csv`

Use the directory containing `deployment_metadata.json` as the source argument below. Do not use `*_head_best.keras` or `*_finetuned_best.keras` in place of selected `*_best.keras` exports without verifying selection. Never upload model files through the public evidence endpoint; only the backend administrator installs trusted `.keras` artifacts.

## VS Code setup — Windows PowerShell

From your project root:

```powershell
cd backend
# Only if no environment exists yet:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-ml.txt
```

For a new install only:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste that generated value into `.env` as `JWT_SECRET`. If Stage 1 already works, KEEP its `.env`. The new setting defaults to `MODEL_MANIFEST=artifacts/manifest.json`; you may add that line explicitly. `.env` is loaded from the backend directory regardless of the terminal working directory.

Prepare either deployment mode, replacing the example path with the extracted export directory:

```powershell
# Single-model deployment: smaller memory requirement, matches notebook's final export.
.\.venv\Scripts\python.exe tools/prepare_artifacts.py "C:\path\to\deepfake_xai_outputs" --mode single

# OR all three models, with the best single model supplying its own Grad-CAM:
.\.venv\Scripts\python.exe tools/prepare_artifacts.py "C:\path\to\deepfake_xai_outputs" --mode ensemble
```

The command copies selected weights into `backend/artifacts/` and writes a hash-verified manifest. Restart the API after changing mode or artifacts.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows Python path. CPU inference is the initial target. GPU setup and throughput are not validated. TensorFlow is pinned to the notebook's recorded version; loading still needs verification with the actual exported model and Keras version.

## API workflow

Open http://127.0.0.1:8000/docs.

1. Register with `POST /api/auth/register`: JSON name, email, password (at least 12 characters).
2. Log in with `POST /api/auth/login`: JSON email, password.
3. Copy `access_token` into Swagger's **Authorize** dialog without the `Bearer ` prefix.
4. `POST /api/evidence`: multipart field `file`. Keep returned evidence `id`.
5. `POST /api/analyze`: JSON `{"evidence_id":"paste-evidence-id"}`.
6. Inspect the returned analysis, per-model probabilities, actual decision threshold and explanation identity.
7. `GET /api/analyses` lists your completed analyses. `GET /api/analyses/{analysis_id}` retrieves one.
8. `GET /api/analyses/{analysis_id}/heatmap` and `/overlay` return authenticated PNG bytes.

This is intentionally a two-step API: upload evidence first, then analyze its ID. It differs from the original architecture's one-step multipart `/api/analyze`; the separation preserves an evidence record even when inference is unavailable and avoids duplicate uploads. `/api/evidence` still accepts JPEG/PNG/WEBP; this stage analyzes JPEG/PNG only. WEBP analysis returns 415 until a validated decoding contract is added.

The bearer token expires after 30 minutes. Health is public: `/api/health`. `inference_ready=true` means the manifest, model shapes/rescaling, a model-forward probe and Grad-CAM probe all succeeded. It does not mean scientific accuracy/generalization was verified. With absent weights or dependencies the app still serves authentication/evidence APIs and returns 503 for analysis.

## New or changed files

| File | Responsibility |
| --- | --- |
| app/inference.py | Load trusted Keras models once, verify shape/preprocessing, run inference and Grad-CAM under a lock |
| app/manifest.py | Validate deployment mode, thresholds, class mapping, file paths and model hashes |
| app/prediction.py | Threshold classification and predicted-class score semantics |
| app/main.py | Analysis API, ownership checks, original hash checks, persistence and protected assets |
| app/database.py | Add analyses table without deleting Stage 1 records |
| app/config.py | Add MODEL_MANIFEST setting |
| app/schemas.py | Add AnalyzeRequest |
| tools/prepare_artifacts.py | Build manifest from existing notebook outputs without training |
| requirements-ml.txt | TensorFlow, NumPy and plotting dependencies |
| tests/test_contract.py | Dependency-free contract/export tests |
| tests/test_inference.py | Synthetic Keras inference/gradient checks; not a real-weight validation |
| tests/test_api.py | Authentication, upload, ownership, hash and analysis-route tests |

## Preprocessing and explanation details

The training/validation pipeline uses `tf.io.decode_image(..., channels=3)` and TensorFlow bilinear resize with `antialias=True`. The notebook's later single-image/Grad-CAM demo uses Pillow bilinear resize instead. Those pipelines are not numerically identical. This backend deliberately uses the validation pipeline for both predictions and explanations, records its preprocessing identifier and passes 0–255 pixels into the embedded rescaling layer. Do not divide by 255 or call `preprocess_input` again.

No EXIF orientation correction or face crop is added: neither is part of the notebook's inference preprocessing. Models trained on cropped faces should receive comparable cropped images; arbitrary full scenes are out-of-distribution and are not validated here. Original bytes remain unchanged and SHA-256 is checked before inference.

An ensemble result includes each member's Fake probability. The Grad-CAM explanation names its own single model, threshold and predicted target class. It may disagree with the ensemble, which is preserved in the response. It must not be labeled an ensemble explanation. The map is model influence, not a manipulation mask.

`confidence` retains the notebook's meaning: the raw score of the threshold-selected class. With a non-0.5 threshold it can be below 0.5. Show Fake probability and decision threshold; do not present this score as calibrated certainty. No calibration was established by this notebook.

## Connecting the existing frontend later

The existing AuthProvider/login form still use local state and must call this API. The analyze page still shows hard-coded outputs and must await completed API results. Result components must receive values via props. Fetch private heatmap URLs with the Authorization header, convert the response to a Blob/object URL and revoke it when replaced/unmounted; a plain image URL cannot attach your bearer header. Do not expose storage directories publicly to make image tags work.

This package does not change frontend files. Keep fake result displays out of real use until integration is complete. PDF reports, case management, PostgreSQL migration and deployment remain later work.

## Verification

Dependency-free tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_contract.py -v
```

Full API and synthetic ML suite (after installing requirements-dev and requirements-ml):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Delivery environment checks: six dependency-free tests passed; Python syntax compilation passed; SQLite analysis schema smoke check passed. FastAPI/TensorFlow dependencies could not be installed in this environment, so API/ML integration tests were NOT executed here. Real trained model loading, Grad-CAM graph compatibility, CPU mixed-precision behavior, numerical parity and latency remain unverified until the actual `.keras` exports are provided and exercised. No scientific performance claim is made from source inspection.

The notebook saved mixed-float16 layers. Do not silently change saved layer dtypes to make CPU execution work: validate any conversion against reference predictions first. Compare backend results to the notebook validation pipeline on the same files, allowing small floating-point differences, especially near thresholds.

## Local-development limits inherited from Stage 1

Keep the server bound to 127.0.0.1. SQLite replaces planned PostgreSQL for local development. Public registration grants the investigator role and has no invitation/approval/email verification flow. No token revocation, refresh tokens, rate limiting, request-size middleware, encryption at rest or tamper-proof audit log is implemented. The application checks file size after multipart parsing/spooling: configure proxy body limits before public deployment. Analysis is synchronous and serialized per worker, with no queue/cancellation/job retries. Run one worker initially; each worker loads a full model set into memory. Authenticated users can accumulate files; no storage quota/deletion/retention API is included.

Do not commit `.env`, storage or trained weights. Back up originals and metadata together. Model manifest/file hashes record artifact identity, not provenance or legal chain of custody. Report generation is deliberately not implemented in this stage.

References checked during implementation:
- https://keras.io/examples/vision/grad_cam/
- https://www.tensorflow.org/api_docs/python/tf/keras/models/load_model
- https://www.tensorflow.org/api_docs/python/tf/image/resize
