from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    field_of_study: str | None = None
    institution: str | None = None
    learning_focus: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    field_of_study: str | None = None
    institution: str | None = None
    learning_focus: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    field_of_study: str | None = Field(default=None, max_length=160)
    institution: str | None = Field(default=None, max_length=180)
    learning_focus: str | None = Field(default=None, max_length=220)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ReactionRead(BaseModel):
    id: int
    reaction_name: str
    original_filename: str | None = None
    image_path: str | None = None
    equation: str | None = None
    reaction_type: str | None = None
    summary: str | None = None
    mechanism: str | None = None
    reactants: list[Any] | None = None
    products: list[Any] | None = None
    conditions: list[Any] | None = None
    catalyst: str | None = None
    temperature: str | None = None
    safety_notes: str | None = None
    extracted_text: str | None = None
    ocr_confidence: float | None = None
    requires_verification: bool
    visualization_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MoleculeValidateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=600)
    name: str | None = Field(default=None, max_length=220)


class MoleculeSaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    smiles: str = Field(min_length=1, max_length=600)
    source: str | None = Field(default="manual", max_length=80)
    identifiers: dict[str, Any] | None = None


class MoleculeRead(BaseModel):
    id: int | None = None
    name: str
    smiles: str
    formula: str | None = None
    molecular_weight: float | None = None
    source: str | None = None
    identifiers: dict[str, Any] | None = None
    visualization_data: dict[str, Any] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChemicalSearchResult(BaseModel):
    name: str
    smiles: str
    formula: str | None = None
    molecular_weight: float | None = None
    source: str
    identifiers: dict[str, Any] | None = None


class FlashcardProgress(BaseModel):
    state: str = "new"
    attempts: int = 0
    correct_recalls: int = 0
    review_count: int = 0
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None

    model_config = {"from_attributes": True}


class FlashcardRead(BaseModel):
    id: int
    topic: str
    difficulty: str
    front: str
    back: str
    example: str | None = None
    progress: FlashcardProgress


class FlashcardReviewRequest(BaseModel):
    state: str = Field(pattern="^(known|learning|needs_revision)$")
    correct: bool = False


class QuizChoiceRead(BaseModel):
    id: int
    text: str

    model_config = {"from_attributes": True}


class QuizQuestionRead(BaseModel):
    id: int
    topic: str
    difficulty: str
    prompt: str
    choices: list[QuizChoiceRead]

    model_config = {"from_attributes": True}


class QuizAnswerRequest(BaseModel):
    question_id: int
    choice_id: int | None = None


class QuizSubmitRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=120)
    difficulty: str | None = Field(default=None, max_length=40)
    answers: list[QuizAnswerRequest]


class QuizResponseRead(BaseModel):
    question_id: int
    prompt: str
    selected_choice_id: int | None
    correct_choice_id: int
    is_correct: bool
    explanation: str


class QuizAttemptRead(BaseModel):
    id: int
    topic: str | None = None
    difficulty: str | None = None
    total_questions: int
    answered_questions: int
    score: int
    percentage: float
    created_at: datetime
    responses: list[QuizResponseRead] = []

    model_config = {"from_attributes": True}


class ProfileProgress(BaseModel):
    total_quizzes_attempted: int
    average_quiz_score: float | None = None
    recent_quiz_scores: list[dict[str, Any]]
    topic_accuracy: list[dict[str, Any]]
    flashcards_reviewed: int
    flashcards_known: int
    flashcards_needing_revision: int
    saved_molecules: int
    saved_reactions: int
    recent_activity: list[dict[str, Any]]
