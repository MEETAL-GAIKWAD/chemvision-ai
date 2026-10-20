from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.services.molecule_service import molecule_payload_from_smiles


PUBCHEM_PROPERTY_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/"
    "Title,MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI,InChIKey/JSON"
)


def validate_smiles(query: str, name: str | None = None) -> dict:
    return molecule_payload_from_smiles(query.strip(), name)


def search_pubchem(query: str, timeout: float = 6.0) -> list[dict]:
    value = query.strip()
    if not value:
        return []

    url = PUBCHEM_PROPERTY_URL.format(query=quote(value))
    request = Request(url, headers={"User-Agent": "ChemVisionAI/0.1 educational lookup"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return []
        raise RuntimeError(f"PubChem returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("PubChem lookup is unavailable right now.") from exc

    rows = payload.get("PropertyTable", {}).get("Properties", [])
    results = []
    for row in rows[:10]:
        smiles = row.get("CanonicalSMILES") or row.get("IsomericSMILES") or row.get("SMILES") or row.get("ConnectivitySMILES")
        if not smiles:
            continue
        try:
            validated = molecule_payload_from_smiles(smiles, row.get("Title") or value)
        except ValueError:
            continue
        results.append(
            {
                "name": validated["name"],
                "smiles": validated["smiles"],
                "formula": row.get("MolecularFormula") or validated["formula"],
                "molecular_weight": float(row.get("MolecularWeight") or validated["molecular_weight"]),
                "source": "PubChem",
                "identifiers": {
                    "cid": row.get("CID"),
                    "inchi": row.get("InChI"),
                    "inchi_key": row.get("InChIKey"),
                },
            }
        )
    return results


def search_compounds(query: str) -> tuple[list[dict], str | None]:
    try:
        validated = validate_smiles(query, None)
        return [
            {
                "name": validated["name"],
                "smiles": validated["smiles"],
                "formula": validated["formula"],
                "molecular_weight": validated["molecular_weight"],
                "source": "RDKit SMILES",
                "identifiers": {},
            }
        ], None
    except ValueError:
        pass

    try:
        return search_pubchem(query), None
    except RuntimeError as exc:
        return [], str(exc)
