from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(160), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(180), nullable=True)
    learning_focus: Mapped[str | None] = mapped_column(String(220), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    reactions: Mapped[list["Reaction"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    saved_molecules: Mapped[list["SavedMolecule"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    flashcard_reviews: Mapped[list["FlashcardReview"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Reaction(Base):
    __tablename__ = "reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reaction_name: Mapped[str] = mapped_column(String(220), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    equation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reaction_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    reactants: Mapped[list | None] = mapped_column(JSON, nullable=True)
    products: Mapped[list | None] = mapped_column(JSON, nullable=True)
    conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    catalyst: Mapped[str | None] = mapped_column(String(180), nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visualization_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped[User] = relationship(back_populates="reactions")


class SavedMolecule(Base):
    __tablename__ = "saved_molecules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    smiles: Mapped[str] = mapped_column(String(600), nullable=False)
    formula: Mapped[str | None] = mapped_column(String(120), nullable=True)
    molecular_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    identifiers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    visualization_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    owner: Mapped[User] = relationship(back_populates="saved_molecules")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    example: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    reviews: Mapped[list["FlashcardReview"]] = relationship(back_populates="flashcard", cascade="all, delete-orphan")


class FlashcardReview(Base):
    __tablename__ = "flashcard_reviews"
    __table_args__ = (UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_review_user_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), default="learning", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_recalls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    owner: Mapped[User] = relationship(back_populates="flashcard_reviews")
    flashcard: Mapped[Flashcard] = relationship(back_populates="reviews")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    choices: Mapped[list["QuizChoice"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    responses: Mapped[list["QuizResponse"]] = relationship(back_populates="question")


class QuizChoice(Base):
    __tablename__ = "quiz_choices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    question: Mapped[QuizQuestion] = relationship(back_populates="choices")
    responses: Mapped[list["QuizResponse"]] = relationship(back_populates="choice")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    answered_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    owner: Mapped[User] = relationship(back_populates="quiz_attempts")
    responses: Mapped[list["QuizResponse"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class QuizResponse(Base):
    __tablename__ = "quiz_responses"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_quiz_response_attempt_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False, index=True)
    choice_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_choices.id"), nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="responses")
    question: Mapped[QuizQuestion] = relationship(back_populates="responses")
    choice: Mapped[QuizChoice | None] = relationship(back_populates="responses")
