from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from pathlib import Path
import mimetypes

from app.core.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models import Reaction, User
from app.schemas import ReactionRead
from app.services.reaction_processor import process_reaction_image, save_upload


router = APIRouter(prefix="/api/reactions", tags=["reactions"])


def _reaction_read(reaction: Reaction) -> ReactionRead:
    """Expose only the authenticated image route, never a public file URL."""
    result = ReactionRead.model_validate(reaction)
    return result.model_copy(update={"image_path": f"/api/reactions/{reaction.id}/image"})


@router.get("", response_model=list[ReactionRead])
def list_reactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reactions = db.scalars(
        select(Reaction)
        .where(Reaction.user_id == current_user.id)
        .order_by(desc(Reaction.created_at), desc(Reaction.id))
    ).all()
    return [_reaction_read(reaction) for reaction in reactions]


@router.post("/upload", response_model=ReactionRead, status_code=status.HTTP_201_CREATED)
def upload_reaction(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved_path, saved_name = save_upload(file)
    try:
        data = process_reaction_image(saved_path, file.filename)
        reaction = Reaction(
            user_id=current_user.id,
            original_filename=file.filename,
            image_path=f"/uploads/{saved_name}",
            **data,
        )
        db.add(reaction)
        db.commit()
        db.refresh(reaction)
        return _reaction_read(reaction)
    except Exception:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise


@router.get("/{reaction_id}", response_model=ReactionRead)
def get_reaction(
    reaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reaction = db.get(Reaction, reaction_id)
    if reaction is None or reaction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction not found.")
    return _reaction_read(reaction)


@router.get("/{reaction_id}/image")
def get_reaction_image(
    reaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reaction = db.get(Reaction, reaction_id)
    if reaction is None or reaction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction not found.")
    if not reaction.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction image not found.")

    upload_root = get_settings().upload_dir.resolve()
    image_path = (upload_root / Path(reaction.image_path).name).resolve()
    if image_path.parent != upload_root or not image_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction image not found.")
    return FileResponse(
        image_path,
        media_type=mimetypes.guess_type(image_path.name)[0] or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{reaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reaction(
    reaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reaction = db.get(Reaction, reaction_id)
    if reaction is None or reaction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction not found.")
    image_path = None
    if reaction.image_path:
        upload_root = get_settings().upload_dir.resolve()
        candidate = (upload_root / Path(reaction.image_path).name).resolve()
        if candidate.parent == upload_root:
            image_path = candidate
    db.delete(reaction)
    db.commit()
    if image_path is not None:
        image_path.unlink(missing_ok=True)
