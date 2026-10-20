"""
Molecule service for ChemVision AI.

Builds per-molecule atom/bond/3-D coordinate data from SMILES using RDKit.

Each molecule record returned by molecule_from_smiles() contains:
  id           – unique string id
  name         – display name
  formula      – molecular formula (e.g. "CH4")
  smiles       – canonical SMILES
  molecular_weight – float, g/mol
  atoms        – list of {id, element, position: [x,y,z]}
  bonds        – list of {from, to, order}
"""

import math
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Element meta (used by frontend renderer)
# ─────────────────────────────────────────────────────────────────────────────
ELEMENT_NAMES = {
    "H":  "hydrogen",
    "O":  "oxygen",
    "C":  "carbon",
    "N":  "nitrogen",
    "Na": "sodium",
    "Cl": "chlorine",
    "S":  "sulfur",
    "P":  "phosphorus",
    "F":  "fluorine",
    "Br": "bromine",
}

# Core builder
# ─────────────────────────────────────────────────────────────────────────────

def _rdkit_molecule(smiles: str, name: str | None = None) -> dict[str, Any] | None:
    """Try to build molecule data using RDKit. Returns None if unavailable."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    except Exception:
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    # Molecular weight from plain (no-H) molecule first
    mw = round(Descriptors.ExactMolWt(mol), 3)
    formula_plain = rdMolDescriptors.CalcMolFormula(mol)

    # Add explicit Hs for 3-D embedding
    mol_h = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol_h, randomSeed=0xC0FFEE) != 0:
        # A 2-D depiction must never be mislabeled as a 3-D conformer.
        return None

    try:
        if AllChem.UFFHasAllMoleculeParams(mol_h):
            AllChem.UFFOptimizeMolecule(mol_h, maxIters=200)
        elif AllChem.MMFFHasAllMoleculeParams(mol_h):
            AllChem.MMFFOptimizeMolecule(mol_h, maxIters=200)
    except Exception:
        # Keep the valid embedded conformer if force-field optimization is
        # unavailable for this otherwise supported structure.
        pass

    conf = mol_h.GetConformer()
    atoms = []
    for atom in mol_h.GetAtoms():
        symbol = atom.GetSymbol()
        pos = conf.GetAtomPosition(atom.GetIdx())
        atoms.append({
            "id": f"a{atom.GetIdx()}",
            "element": ELEMENT_NAMES.get(symbol, symbol.lower()),
            "position": [round(pos.x, 3), round(pos.y, 3), round(pos.z, 3)],
        })

    bonds = []
    for bond in mol_h.GetBonds():
        bonds.append({
            "from": f"a{bond.GetBeginAtomIdx()}",
            "to":   f"a{bond.GetEndAtomIdx()}",
            "order": bond.GetBondTypeAsDouble(),
            "type": str(bond.GetBondType()),
        })

    formula = rdMolDescriptors.CalcMolFormula(mol_h)
    return {
        "formula": formula,
        "name": name or formula_plain,
        "molecular_weight": mw,
        "atoms": atoms,
        "bonds": bonds,
    }


def molecule_from_smiles(
    smiles: str,
    name: str | None = None,
    index: int = 0,
    coefficient: int = 1,
) -> dict[str, Any] | None:
    """
    Return a complete molecule record for the given SMILES.
    Uses RDKit geometry only. Unsupported structures are omitted instead of
    being shown with hand-authored coordinates that could imply false accuracy.
    """
    molecule = _rdkit_molecule(smiles, name)
    if molecule is None:
        return None

    molecule["id"]          = f"mol-{index}-{molecule['formula'].lower()}"
    molecule["smiles"]      = smiles
    molecule["coefficient"] = coefficient
    return molecule


def build_visualization_data(reaction: dict[str, Any]) -> dict[str, Any]:
    """
    Build the full visualization_data dict from a COMMON_REACTIONS entry.
    Includes per-molecule atoms, bonds, coords, weight, and coefficient.
    """
    smiles        = reaction.get("smiles") or {}
    reactant_names = reaction.get("reactants") or []
    product_names  = reaction.get("products") or []
    coefficients   = reaction.get("coefficients") or {}
    r_coeff = coefficients.get("reactants", [])
    p_coeff = coefficients.get("products", [])

    reactants = []
    for idx, smile in enumerate(smiles.get("reactants", [])):
        name  = reactant_names[idx] if idx < len(reactant_names) else None
        coeff = r_coeff[idx] if idx < len(r_coeff) else 1
        mol   = molecule_from_smiles(smile, name, idx, coeff)
        if mol:
            reactants.append(mol)

    products = []
    for idx, smile in enumerate(smiles.get("products", [])):
        name  = product_names[idx] if idx < len(product_names) else None
        coeff = p_coeff[idx] if idx < len(p_coeff) else 1
        mol   = molecule_from_smiles(smile, name, idx + 20, coeff)
        if mol:
            products.append(mol)

    expected_count = len(smiles.get("reactants", [])) + len(smiles.get("products", []))
    complete = len(reactants) + len(products) == expected_count

    return {
        "engine": "rdkit" if complete and expected_count else "unavailable",
        "molecules": {
            "reactants": reactants,
            "products":  products,
        },
        "layout": {
            "note": (
                "Educational ball-and-stick view. "
                "Animation shows reaction stages, not molecular dynamics."
            ),
            "reactantSpread": max(2.2, math.sqrt(max(len(reactants), 1)) * 1.8),
            "productSpread":  max(1.8, math.sqrt(max(len(products),  1)) * 1.6),
        },
    }


def molecule_payload_from_smiles(smiles: str, name: str | None = None) -> dict[str, Any]:
    """
    Validate a SMILES string and return metadata plus 3-D visualization data.
    Unlike reaction fallback rendering, invalid standalone molecules are rejected.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
    except Exception as exc:
        raise ValueError("RDKit is required for molecule validation.") from exc

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES structure.")

    canonical = Chem.MolToSmiles(mol, canonical=True)
    formula = rdMolDescriptors.CalcMolFormula(mol)
    molecular_weight = round(Descriptors.MolWt(mol), 3)
    display_name = name.strip() if name and name.strip() else "Unknown or unverified compound"
    molecule = molecule_from_smiles(canonical, display_name, 0, 1)
    if molecule is None:
        raise ValueError("Could not generate 3-D coordinates for this molecule.")

    return {
        "name": display_name,
        "smiles": canonical,
        "formula": formula,
        "molecular_weight": molecular_weight,
        "visualization_data": {
            "engine": "rdkit",
            "molecules": {"reactants": [molecule], "products": []},
            "layout": {
                "note": "Validated standalone molecule generated from RDKit.",
                "reactantSpread": 2.2,
                "productSpread": 1.8,
            },
        },
    }
