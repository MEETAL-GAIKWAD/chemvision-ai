# ChemVision AI implementation plan

This plan reflects the repository as audited on 2026-10-20. The project already contains authentication, reaction upload, a molecular studio, flashcards, quizzes, profile progress, theme support, and an ML inference adapter. Work should close identified correctness and reliability gaps without replacing the existing architecture.

## Follow-up completed on 2026-10-20

- Added `docs/ML_MODEL_AUDIT.md`, `docs/DEPLOYMENT_GUIDE.md`, and the full `docs/dataset_report.json` sample accounting report.
- Added `ml/audit_dataset.py`; independently checked 221/221 valid image records, including labels, file presence, and decodability.
- Made the PyTorch dataset loader strict. It now raises instead of silently filtering unknown split labels or invalid records.
- Made the trainer select checkpoints by validation macro-F1, log validation macro-F1/balanced accuracy, and preserve the best checkpoint instead of overwriting it with the final epoch.
- Updated complete-manifest evaluation; all 54 test images are accounted for and unseen labels count as incorrect. Saved the complete per-class results and error examples.
- Hardened production startup configuration to require a non-placeholder JWT secret and HTTPS CORS origins; development-only `null` and localhost allowances are disabled for production.
- Added and ran `backend/tests/test_smoke.py` against a temporary SQLite database. All 3 tests pass. `backend/app.db` was not used.
- Removed the public upload mount; image responses are owner-checked, non-cacheable, and fetched by the visualizer with the bearer token. The API smoke test verifies owner access, cross-user denial, no public `/uploads` route, and deletion of an owned image.
- Added an accessible theme toggle and early saved-theme application to the landing page. Browser-verified light/dark and persistence after reload at the default viewport.

## Current hard blocker for ML training

The provided class split cannot be evaluated or used to train safely: 8 of 14 validation samples and 33 of 54 test samples have classes absent from the 153-sample training set. The strict loader intentionally stops before fitting. No new model training or held-out score was produced. Replace/rebuild the splits from verified, licensed examples grouped by source document, then rerun the audit before model selection.

## Completed in this audit pass

- Added `docs/PROJECT_AUDIT.md` with current architecture, evidence, status, blockers, and owner requirements.
- Added byte-level image verification after MIME/size checks so a renamed non-image cannot be retained as an upload.
- Prevented the low-performing classifier from selecting a reaction as if identified. It may still provide suggestion metadata.
- Marked reaction matches as requiring user verification unless a parsed equation match also has adequate OCR confidence.
- Removed runtime use of hand-authored molecular coordinates. Failed RDKit conformer embedding now fails instead of presenting a planar depiction as 3D; supported optimization uses UFF or MMFF where available.
- Preserved actual fractional RDKit bond orders and report `unavailable` if reaction visualization could not generate every component.
- Added a 404 for an unknown flashcard review and a 422 for duplicate question IDs in quiz submissions.
- Added a dark charcoal molecular stage with polished element-colored atoms, atom-label toggle, distinct multiple bonds, and geometry-based camera fit.
- Show the uploaded source image with an explicit reason when a verified 3D model cannot be shown or WebGL fails; reject incomplete reaction geometry instead of showing a partial model.
- Handle empty Molecular Studio structures without starting a blank render loop, and dispose atom-label textures when replacing a scene.

## Remaining phases

### Phase 1: Chemistry correctness

- Add tests for valid/invalid SMILES, deterministic coordinates, formula/weight, stereochemistry, aromatic bond order, charges, unsupported elements, and conformer failures.
- Add atom hover/selection and molecule metadata/source display.
- Add component-specific diagnostics for failed reaction structures; the current viewer safely falls back to the source image with a general explanation.
- Add formula and equation balance checks before a registry match is treated as supported.

### Phase 2: Molecular Studio

- Add a sketcher after reviewing maintained candidates, license, asset hosting, and browser compatibility.
- Add explicit candidate selection for ambiguous PubChem lookups and a clear unknown identity state.
- Implement fit-to-view from geometry bounds, ball-and-stick/stick/space-filling modes, and supported structure export.

### Phase 3: Recognition and evaluation

- Keep the current classifier informational only until it meets a held-out evaluation threshold on a representative dataset.
- Audit the COCO source license and category coverage; its manifests report 153/14/54 images and 89 raw categories. It does not contain atom-level transcription targets.
- Obtain additional licensed equation and molecular-structure images with verified labels and source-grouped train/validation/test splits.
- Evaluate OCR character/sequence error and structure-aware correctness, not only reaction class top-k accuracy.
- Do not claim training gains until a reproducible run and held-out evaluation are recorded.

### Phase 4: Learning workflows

- Add backend tests for flashcard state transitions, spaced review dates, persistence, empty filters, quiz answer ownership/validation, scoring, attempts and profile aggregation.
- Prevent duplicate attempt creation with an idempotency key if retry semantics are needed by the frontend.
- Expand content only through curated, reviewed questions/cards stored separately from application logic.

### Phase 5: Profile and saved content

- Add links to reopen owned reactions and saved molecules from history.
- Add streak only after actual dated activity records are available; do not infer study time from review count.
- Keep all profile aggregates derived from authenticated-user-owned records.

### Phase 6: Security, migrations, and verification

- Replace `create_all()`-only schema evolution with Alembic or explicit migrations before existing columns change.
- Restrict production CORS origins, set a strong environment secret, and protect uploaded files if they contain private information.
- Add upload size/format spoofing checks and authenticated-route ownership tests.
- Perform browser checks for every page in light/dark mode and desktop/tablet/mobile widths.
- Record exact tests, environment requirements, model/data sources and known failures in final delivery notes.

## Required resources and setup

- No new user input is needed for source-level work.
- Production use needs a secure `JWT_SECRET_KEY`, configured `DATABASE_URL`, exact `FRONTEND_ORIGINS`, and persistent upload storage.
- PubChem requires internet access. EasyOCR may download its pretrained OCR files on first inference.
- A better reaction recognition model requires a larger licensed dataset with verified labels. GPU access is optional and only needed for practical fine-tuning at scale.
- Do not automatically fetch large checkpoints or datasets without reviewing license, size, and compute requirements.
