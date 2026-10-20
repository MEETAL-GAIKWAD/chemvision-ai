"""Small local smoke suite; uses a temporary database and never opens app.db."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
TEMP = tempfile.TemporaryDirectory(prefix="chemvision-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP.name) / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(Path(TEMP.name) / "uploads")
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-for-production-1234567890"
os.environ["FRONTEND_ORIGINS"] = "http://testserver"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "ml"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services.molecule_lookup import validate_smiles  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Reaction  # noqa: E402
from audit_dataset import audit_split  # noqa: E402


class ChemVisionSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.auth_headers = None

    def test_dataset_manifest_accounting_and_split_coverage(self):
        train = audit_split(ROOT / "CHEMVISION.v7i.coco", "train")
        valid = audit_split(ROOT / "CHEMVISION.v7i.coco", "valid")
        test = audit_split(ROOT / "CHEMVISION.v7i.coco", "test")
        self.assertEqual((train["manifest_images"], train["included_samples"], train["excluded_samples"]), (153, 153, 0))
        self.assertEqual((valid["manifest_images"], valid["included_samples"], valid["excluded_samples"]), (14, 14, 0))
        self.assertEqual((test["manifest_images"], test["included_samples"], test["excluded_samples"]), (54, 54, 0))
        self.assertEqual(valid["canonical_class_counts"].get("Iodoform Reaction"), 3)

    def test_rdkit_validation_and_geometry(self):
        molecule = validate_smiles("C", "methane")
        self.assertEqual(molecule["formula"], "CH4")
        geometry = molecule["visualization_data"]["molecules"]["reactants"][0]
        self.assertEqual(len(geometry["atoms"]), 5)
        self.assertEqual(len(geometry["bonds"]), 4)
        with self.assertRaises(ValueError):
            validate_smiles("not-a-smiles")

    def test_api_auth_learning_and_profile_persistence(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["database"], "available")

        signup = self.client.post("/api/auth/signup", json={
            "full_name": "Smoke Student", "email": "cv.smoke@example.com", "password": "StrongPass123"
        })
        self.assertEqual(signup.status_code, 201, signup.text)
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/profile", headers=headers).status_code, 200)

        private_image = Path(TEMP.name) / "uploads" / "owned.png"
        private_image.parent.mkdir(parents=True, exist_ok=True)
        private_image.write_bytes(b"private test image")
        with SessionLocal() as db:
            reaction = Reaction(
                user_id=signup.json()["user"]["id"],
                reaction_name="Private test reaction",
                image_path="/uploads/owned.png",
                requires_verification=True,
            )
            db.add(reaction)
            db.commit()
            db.refresh(reaction)
            reaction_id = reaction.id
        own_reaction = self.client.get(f"/api/reactions/{reaction_id}", headers=headers)
        self.assertEqual(own_reaction.status_code, 200)
        self.assertEqual(own_reaction.json()["image_path"], f"/api/reactions/{reaction_id}/image")
        own_image = self.client.get(own_reaction.json()["image_path"], headers=headers)
        self.assertEqual(own_image.status_code, 200)
        self.assertEqual(own_image.content, b"private test image")
        self.assertEqual(self.client.get("/uploads/owned.png").status_code, 404)

        second_signup = self.client.post("/api/auth/signup", json={
            "full_name": "Second Student", "email": "second.smoke@example.com", "password": "StrongPass123"
        })
        other_headers = {"Authorization": f"Bearer {second_signup.json()['access_token']}"}
        denied = self.client.get(f"/api/reactions/{reaction_id}/image", headers=other_headers)
        self.assertEqual(denied.status_code, 404)
        removed = self.client.delete(f"/api/reactions/{reaction_id}", headers=headers)
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(private_image.exists())

        cards = self.client.get("/api/flashcards", headers=headers)
        self.assertEqual(cards.status_code, 200, cards.text)
        self.assertTrue(cards.json())
        card = cards.json()[0]
        reviewed = self.client.post(f"/api/flashcards/{card['id']}/review", headers=headers, json={"state": "known", "correct": True})
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["review_count"], 1)

        questions = self.client.get("/api/quizzes/questions?limit=1", headers=headers)
        self.assertEqual(questions.status_code, 200, questions.text)
        question = questions.json()[0]
        submitted = self.client.post("/api/quizzes/submit", headers=headers, json={
            "topic": question["topic"], "difficulty": question["difficulty"],
            "answers": [{"question_id": question["id"], "choice_id": question["choices"][0]["id"]}],
        })
        self.assertEqual(submitted.status_code, 201, submitted.text)
        self.assertEqual(submitted.json()["total_questions"], 1)
        progress = self.client.get("/api/profile/progress", headers=headers)
        self.assertEqual(progress.status_code, 200, progress.text)
        self.assertEqual(progress.json()["total_quizzes_attempted"], 1)
        self.assertEqual(progress.json()["flashcards_reviewed"], 1)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        from app.database import engine
        engine.dispose()
        TEMP.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
