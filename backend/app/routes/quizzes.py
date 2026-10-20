from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.database import get_db
from app.models import QuizAttempt, QuizChoice, QuizQuestion, QuizResponse, User
from app.schemas import QuizAttemptRead, QuizQuestionRead, QuizResponseRead, QuizSubmitRequest


router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


@router.get("/questions", response_model=list[QuizQuestionRead])
def list_questions(
    topic: str | None = Query(default=None, max_length=120),
    difficulty: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(QuizQuestion).options(selectinload(QuizQuestion.choices)).where(QuizQuestion.is_active.is_(True))
    if topic:
        stmt = stmt.where(QuizQuestion.topic == topic)
    if difficulty:
        stmt = stmt.where(QuizQuestion.difficulty == difficulty)
    return db.scalars(stmt.order_by(QuizQuestion.topic, QuizQuestion.id).limit(limit)).all()


@router.post("/submit", response_model=QuizAttemptRead, status_code=status.HTTP_201_CREATED)
def submit_quiz(
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.answers:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Submit at least one answer.")

    question_ids = [answer.question_id for answer in payload.answers]
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each quiz question can be answered only once.",
        )
    questions = {
        question.id: question
        for question in db.scalars(
            select(QuizQuestion)
            .options(selectinload(QuizQuestion.choices))
            .where(QuizQuestion.id.in_(question_ids), QuizQuestion.is_active.is_(True))
        )
    }
    if len(questions) != len(set(question_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more quiz questions were not found.")

    answers_by_question = {answer.question_id: answer.choice_id for answer in payload.answers}
    score = 0
    responses = []
    response_reads = []
    for question_id, question in questions.items():
        correct_choice = next((choice for choice in question.choices if choice.is_correct), None)
        if correct_choice is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Quiz question has no correct answer.")
        selected_choice_id = answers_by_question.get(question_id)
        valid_choice_ids = {choice.id for choice in question.choices}
        if selected_choice_id is not None and selected_choice_id not in valid_choice_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected answer does not belong to its question.")
        is_correct = selected_choice_id == correct_choice.id
        if is_correct:
            score += 1
        responses.append(
            QuizResponse(question_id=question_id, choice_id=selected_choice_id, is_correct=is_correct)
        )
        response_reads.append(
            QuizResponseRead(
                question_id=question_id,
                prompt=question.prompt,
                selected_choice_id=selected_choice_id,
                correct_choice_id=correct_choice.id,
                is_correct=is_correct,
                explanation=question.explanation,
            )
        )

    total = len(questions)
    answered = sum(1 for answer in payload.answers if answer.choice_id is not None)
    percentage = round((score / total) * 100, 2) if total else 0.0
    attempt = QuizAttempt(
        user_id=current_user.id,
        topic=payload.topic,
        difficulty=payload.difficulty,
        total_questions=total,
        answered_questions=answered,
        score=score,
        percentage=percentage,
        responses=responses,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return QuizAttemptRead(
        id=attempt.id,
        topic=attempt.topic,
        difficulty=attempt.difficulty,
        total_questions=attempt.total_questions,
        answered_questions=attempt.answered_questions,
        score=attempt.score,
        percentage=attempt.percentage,
        created_at=attempt.created_at,
        responses=response_reads,
    )


@router.get("/attempts", response_model=list[QuizAttemptRead])
def list_attempts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(desc(QuizAttempt.created_at), desc(QuizAttempt.id))
        .limit(20)
    ).all()
    return [
        QuizAttemptRead(
            id=attempt.id,
            topic=attempt.topic,
            difficulty=attempt.difficulty,
            total_questions=attempt.total_questions,
            answered_questions=attempt.answered_questions,
            score=attempt.score,
            percentage=attempt.percentage,
            created_at=attempt.created_at,
            responses=[],
        )
        for attempt in attempts
    ]
