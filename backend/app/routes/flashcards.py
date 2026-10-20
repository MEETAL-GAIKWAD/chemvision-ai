from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Flashcard, FlashcardReview, User
from app.schemas import FlashcardProgress, FlashcardRead, FlashcardReviewRequest


router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


def _progress(review: FlashcardReview | None) -> FlashcardProgress:
    if review is None:
        return FlashcardProgress()
    return FlashcardProgress.model_validate(review)


@router.get("", response_model=list[FlashcardRead])
def list_flashcards(
    topic: str | None = Query(default=None, max_length=120),
    difficulty: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
    mode: str | None = Query(default=None, pattern="^(all|revision)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Flashcard).where(Flashcard.is_active.is_(True))
    if topic:
        stmt = stmt.where(Flashcard.topic == topic)
    if difficulty:
        stmt = stmt.where(Flashcard.difficulty == difficulty)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Flashcard.front.ilike(like), Flashcard.back.ilike(like), Flashcard.topic.ilike(like)))

    cards = db.scalars(stmt.order_by(Flashcard.topic, Flashcard.difficulty, Flashcard.id)).all()
    reviews = {
        review.flashcard_id: review
        for review in db.scalars(
            select(FlashcardReview).where(
                and_(
                    FlashcardReview.user_id == current_user.id,
                    FlashcardReview.flashcard_id.in_([card.id for card in cards] or [0]),
                )
            )
        )
    }
    now = datetime.now(timezone.utc)
    output = []
    for card in cards:
        review = reviews.get(card.id)
        if mode == "revision":
            nra = review and review.next_review_at
            # SQLite may return naive datetimes — make comparison safe
            if nra:
                if nra.tzinfo is None:
                    from datetime import timezone as _tz
                    nra = nra.replace(tzinfo=_tz.utc)
                due = nra <= now
            else:
                due = False
            needs = review and review.state == "needs_revision"
            if not (due or needs):
                continue
        output.append(
            FlashcardRead(
                id=card.id,
                topic=card.topic,
                difficulty=card.difficulty,
                front=card.front,
                back=card.back,
                example=card.example,
                progress=_progress(review),
            )
        )
    return output


@router.post("/{flashcard_id}/review", response_model=FlashcardProgress)
def review_flashcard(
    flashcard_id: int,
    payload: FlashcardReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Flashcard, flashcard_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found.",
        )

    review = db.scalar(
        select(FlashcardReview).where(
            FlashcardReview.user_id == current_user.id,
            FlashcardReview.flashcard_id == flashcard_id,
        )
    )
    if review is None:
        review = FlashcardReview(
            user_id=current_user.id,
            flashcard_id=flashcard_id,
            attempts=0,
            review_count=0,
            correct_recalls=0,
        )

    now = datetime.now(timezone.utc)
    review.state         = payload.state
    review.attempts      = (review.attempts or 0) + 1
    review.review_count  = (review.review_count or 0) + 1
    if payload.correct:
        review.correct_recalls = (review.correct_recalls or 0) + 1

    if payload.state == "known":
        delay = timedelta(days=7 if payload.correct else 2)
    elif payload.state == "learning":
        delay = timedelta(days=2 if payload.correct else 1)
    else:
        delay = timedelta(hours=12)

    review.last_reviewed_at = now
    review.next_review_at = now + delay
    db.add(review)
    db.commit()
    db.refresh(review)
    return FlashcardProgress.model_validate(review)
