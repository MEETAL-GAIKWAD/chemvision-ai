# ChemVision AI

Intelligent Chemical Reaction Visualization and Learning Platform.

---

## Features

| Feature | Status |
|---------|--------|
| Signup / Login (JWT) | Implemented; configure a production secret before deployment |
| Reaction image upload + OCR | Implemented; OCR and reaction matching require user verification |
| 3D molecular visualization (Three.js + RDKit) | Implemented for supported structures; RDKit required for generated geometry |
| Molecular Studio (search PubChem, validate SMILES, save) | Implemented; no integrated sketcher or full export yet |
| Flashcard learning and review persistence | Implemented with a simple fixed-delay schedule |
| Chemistry Quiz (server-scored) | Implemented; no timer or duplicate-attempt idempotency |
| Profile with learning progress | Implemented for stored activities; no streak tracking |
| Light / Dark theme toggle | Implemented; browser-wide visual QA still needed |
| Reaction image classifier | Integrated but not reliable for automatic identity (4.76% held-out top-1 in saved report) |

---

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Home | `/home.html` | Landing page |
| Sign up / Sign in | `/signup.html` | Authentication |
| Dashboard | `/dashboard.html` | Upload reactions, view history |
| Molecular Studio | `/studio.html` | Search, validate, view 3D molecules |
| Flashcards | `/flashcards.html` | Spaced-repetition flashcard review |
| Chemistry Quiz | `/quiz.html` | Multiple-choice quizzes, scored on server |
| Visualizer | `/visualizer.html` | 3D reaction viewer |
| Profile | `/profile.html` | Profile + learning progress |

---

## Quick Start

### 1. Install backend dependencies

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Start the backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Backend runs at: `http://127.0.0.1:8000`
Swagger docs: `http://127.0.0.1:8000/docs`

### 3. Start the frontend

```powershell
# From the project root (where home.html is)
python -m http.server 8080
```

Frontend runs at: `http://127.0.0.1:8080/home.html`

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and set:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Set `production` to enforce a strong JWT secret and explicit HTTPS CORS origins. |
| `DATABASE_URL` | SQLite `app.db` | PostgreSQL or SQLite |
| `JWT_SECRET_KEY` | dev default | Change in production |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 24 hours |
| `FRONTEND_ORIGINS` | localhost variants | CORS allowed origins |
| `UPLOAD_DIR` | `uploads/` | Image upload directory |
| `MAX_UPLOAD_MB` | `8` | Max upload size |

---

## Supported Reactions (OCR + Filename Recognition)

Name your uploaded image after the reaction for best OCR results:

| Filename | Reaction |
|----------|---------|
| `methane_combustion.png` | CH₄ + 2O₂ → CO₂ + 2H₂O |
| `hydrogen_combustion.png` | 2H₂ + O₂ → 2H₂O |
| `hcl_naoh.png` | HCl + NaOH → NaCl + H₂O |
| `esterification.png` | Fischer esterification |
| `electrolysis.png` | Water electrolysis |
| `ethanol_oxidation.png` | Ethanol oxidation |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/signup` | No | Create account |
| POST | `/api/auth/login` | No | Login, get JWT |
| GET | `/api/profile` | Yes | Get profile |
| PUT | `/api/profile` | Yes | Update profile |
| GET | `/api/profile/progress` | Yes | Learning progress |
| GET | `/api/reactions` | Yes | List user reactions |
| POST | `/api/reactions/upload` | Yes | Upload image → OCR → 3D |
| GET | `/api/reactions/{id}` | Yes | Get reaction details |
| DELETE | `/api/reactions/{id}` | Yes | Delete reaction |
| POST | `/api/studio/validate` | Yes | Validate SMILES |
| GET | `/api/studio/search?q=` | Yes | Search PubChem |
| POST | `/api/studio/molecules` | Yes | Save molecule |
| GET | `/api/studio/molecules` | Yes | List saved molecules |
| GET | `/api/flashcards` | Yes | List flashcards (with filters) |
| POST | `/api/flashcards/{id}/review` | Yes | Mark card state |
| GET | `/api/quizzes/questions` | Yes | Get quiz questions |
| POST | `/api/quizzes/submit` | Yes | Submit quiz (server-scored) |
| GET | `/api/quizzes/attempts` | Yes | Quiz history |

---

## Architecture

```
finalchem/
├── backend/               FastAPI + SQLAlchemy + SQLite
│   ├── app/
│   │   ├── core/          config.py, security.py
│   │   ├── routes/        auth, profile, reactions, studio, flashcards, quizzes
│   │   ├── services/      reaction_processor, molecule_service, molecule_lookup,
│   │   │                  common_reactions, learning_content
│   │   ├── models.py      8 tables: users, reactions, saved_molecules,
│   │   │                  flashcards, flashcard_reviews, quiz_questions,
│   │   │                  quiz_choices, quiz_attempts, quiz_responses
│   │   ├── schemas.py     Pydantic validation schemas
│   │   └── main.py        App factory + seeding
│   ├── uploads/           User-uploaded images
│   └── requirements.txt
├── js/                    Frontend JavaScript (no framework)
│   ├── api.js             Centralized API client
│   ├── theme.js           Dark/light theme manager
│   ├── auth-page.js
│   ├── dashboard-page.js
│   ├── profile-page.js
│   ├── visualizer-page.js
│   ├── flashcards-page.js
│   ├── quiz-page.js
│   └── studio-page.js
├── home.html
├── signup.html
├── dashboard.html
├── studio.html
├── flashcards.html
├── quiz.html
├── visualizer.html
├── profile.html
└── docs/
    └── IMPLEMENTATION_PLAN.md
```

---

## Known Limitations

- OCR accuracy depends on image quality. For best results, name files after the reaction.
- EasyOCR first-call initialization takes ~10-15 seconds (model loading).
- PubChem search requires internet connectivity.
- Only 6 reactions in the common_reactions registry (easily extensible).
- The bundled reaction-classifier evaluation is 1/21 top-1 correct; classifier output is informational and should not be treated as reaction identification.
- PyTorch/torchvision are optional and listed in `ml/requirements.txt`; install those separately only if you want to load the experimental classifier checkpoint.
- The COCO dataset is reaction-class/region labeled and does not provide molecular graph transcription targets.
- A production deployment must configure a unique `JWT_SECRET_KEY`, database, exact frontend origins, and secure upload storage.
- No real-time collaboration or multi-device sync.

See [the project audit](docs/PROJECT_AUDIT.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md) for evidence and remaining work.

See [the ML and dataset audit](docs/ML_MODEL_AUDIT.md), [dataset sample report](docs/dataset_report.json), and [deployment guide](docs/DEPLOYMENT_GUIDE.md) for verified limitations and setup details. The provided classifier's old 1/21 score is based on only the subset whose labels overlapped training; it is experimental and does not establish reaction identity. Use `cd backend; .\\.venv\\Scripts\\python.exe ..\\ml\\audit_dataset.py` to validate dataset coverage before any training attempt.
