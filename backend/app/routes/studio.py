from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import SavedMolecule, User
from app.schemas import ChemicalSearchResult, MoleculeRead, MoleculeSaveRequest, MoleculeValidateRequest
from app.services.molecule_lookup import search_compounds, validate_smiles


router = APIRouter(prefix="/api/studio", tags=["molecular studio"])


@router.post("/validate", response_model=MoleculeRead)
def validate_molecule(
    payload: MoleculeValidateRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        data = validate_smiles(payload.query, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {**data, "source": "RDKit", "identifiers": {}}


@router.get("/search", response_model=list[ChemicalSearchResult])
def search_molecules(
    q: str = Query(min_length=1, max_length=160),
    current_user: User = Depends(get_current_user),
):
    results, error = search_compounds(q)
    if error and not results:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error)
    return results


@router.post("/molecules", response_model=MoleculeRead, status_code=status.HTTP_201_CREATED)
def save_molecule(
    payload: MoleculeSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data = validate_smiles(payload.smiles, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    molecule = SavedMolecule(
        user_id=current_user.id,
        name=payload.name.strip(),
        smiles=data["smiles"],
        formula=data["formula"],
        molecular_weight=data["molecular_weight"],
        source=payload.source or "manual",
        identifiers=payload.identifiers or {},
        visualization_data=data["visualization_data"],
    )
    db.add(molecule)
    db.commit()
    db.refresh(molecule)
    return molecule


@router.get("/molecules", response_model=list[MoleculeRead])
def list_saved_molecules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(SavedMolecule)
        .where(SavedMolecule.user_id == current_user.id)
        .order_by(desc(SavedMolecule.created_at), desc(SavedMolecule.id))
    ).all()
