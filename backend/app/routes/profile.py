from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import FlashcardReview, QuizAttempt, Reaction, SavedMolecule, User
from app.schemas import ProfileProgress, ProfileUpdate, UserProfile


router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("", response_model=UserProfile)
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value.strip() if isinstance(value, str) else value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/progress", response_model=ProfileProgress)
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(desc(QuizAttempt.created_at), desc(QuizAttempt.id))
    ).all()
    reviews = db.scalars(
        select(FlashcardReview).where(FlashcardReview.user_id == current_user.id)
    ).all()
    saved_molecules = db.scalars(
        select(SavedMolecule).where(SavedMolecule.user_id == current_user.id)
    ).all()
    reactions = db.scalars(
        select(Reaction)
        .where(Reaction.user_id == current_user.id)
        .order_by(desc(Reaction.created_at), desc(Reaction.id))
    ).all()

    avg_score = None
    if attempts:
        avg_score = round(sum(attempt.percentage for attempt in attempts) / len(attempts), 2)

    topic_totals: dict[str, dict[str, float]] = {}
    for attempt in attempts:
        topic = attempt.topic or "Mixed"
        bucket = topic_totals.setdefault(topic, {"count": 0, "total": 0.0})
        bucket["count"] += 1
        bucket["total"] += attempt.percentage

    recent_activity = []
    for attempt in attempts[:5]:
        recent_activity.append(
            {
                "type": "quiz",
                "title": attempt.topic or "Mixed quiz",
                "detail": f"{attempt.score}/{attempt.total_questions} ({attempt.percentage:.0f}%)",
                "created_at": attempt.created_at,
            }
        )
    for molecule in saved_molecules[:5]:
        recent_activity.append(
            {
                "type": "molecule",
                "title": molecule.name,
                "detail": molecule.formula or molecule.smiles,
                "created_at": molecule.created_at,
            }
        )
    for reaction in reactions[:5]:
        recent_activity.append(
            {
                "type": "reaction",
                "title": reaction.reaction_name,
                "detail": reaction.equation or reaction.reaction_type or "Reaction upload",
                "created_at": reaction.created_at,
            }
        )
    recent_activity.sort(key=lambda item: item["created_at"], reverse=True)

    return ProfileProgress(
        total_quizzes_attempted=len(attempts),
        average_quiz_score=avg_score,
        recent_quiz_scores=[
            {"id": attempt.id, "topic": attempt.topic or "Mixed", "percentage": attempt.percentage, "created_at": attempt.created_at}
            for attempt in attempts[:8]
        ],
        topic_accuracy=[
            {"topic": topic, "attempts": int(data["count"]), "average": round(data["total"] / data["count"], 2)}
            for topic, data in sorted(topic_totals.items())
        ],
        flashcards_reviewed=sum(review.review_count for review in reviews),
        flashcards_known=sum(1 for review in reviews if review.state == "known"),
        flashcards_needing_revision=sum(1 for review in reviews if review.state == "needs_revision"),
        saved_molecules=len(saved_molecules),
        saved_reactions=len(reactions),
        recent_activity=recent_activity[:10],
    )
