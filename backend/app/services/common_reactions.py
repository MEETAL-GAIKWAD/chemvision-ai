"""
Known reaction library for ChemVision AI.

Each entry has:
  key          – space-separated terms used for text matching (OCR + filename)
  aliases      – additional filename patterns that map to this reaction
  coefficients – stoichiometric coefficients (reactants / products, same order as smiles)
  mol_weights  – approximate molecular weights (reactants then products, same order as smiles)
  plus all the display fields
"""

COMMON_REACTIONS = [
    {
        "key": "methane combustion ch4 o2 co2 h2o natural gas",
        "aliases": ["methane", "ch4", "natural_gas", "combustion_methane"],
        "reaction_name": "Methane Combustion",
        "equation": "CH4 + 2O2 -> CO2 + 2H2O",
        "reaction_type": "Combustion",
        "summary": (
            "Methane burns in oxygen to produce carbon dioxide and water, "
            "releasing energy as heat and light."
        ),
        "mechanism": (
            "Combustion proceeds through radical chain steps at high temperature. "
            "The overall balanced equation conserves atoms and charge."
        ),
        "reactants": ["Methane", "Oxygen"],
        "products": ["Carbon Dioxide", "Water"],
        "coefficients": {"reactants": [1, 2], "products": [1, 2]},
        "conditions": ["Ignition source", "Oxygen-rich environment", "Exothermic"],
        "catalyst": None,
        "temperature": "High temperature / ignition",
        "safety_notes": (
            "Methane is highly flammable. Avoid leaks and open flames "
            "outside controlled laboratory settings."
        ),
        "smiles": {"reactants": ["C", "O=O"], "products": ["O=C=O", "O"]},
    },
    {
        "key": "hydrogen combustion h2 o2 water formation h2o synthesis",
        "aliases": ["hydrogen", "h2", "water_formation", "hydrogen_combustion"],
        "reaction_name": "Hydrogen Combustion",
        "equation": "2H2 + O2 -> 2H2O",
        "reaction_type": "Synthesis / Combustion",
        "summary": (
            "Hydrogen reacts with oxygen to form water, releasing a large "
            "amount of heat. Used in fuel cells and rocket propulsion."
        ),
        "mechanism": (
            "Bonds in H₂ and O₂ break homolytically; new O–H bonds form. "
            "This educational model does not simulate radical chain kinetics."
        ),
        "reactants": ["Hydrogen", "Oxygen"],
        "products": ["Water"],
        "coefficients": {"reactants": [2, 1], "products": [2]},
        "conditions": ["Ignition source", "Oxygen-rich environment", "Exothermic"],
        "catalyst": None,
        "temperature": "Ignition required",
        "safety_notes": (
            "Hydrogen–oxygen mixtures are explosive. "
            "Use only in controlled laboratory demonstrations."
        ),
        "smiles": {"reactants": ["[H][H]", "O=O"], "products": ["O"]},
    },
    {
        "key": "acid base neutralization hcl naoh nacl sodium chloride salt water",
        "aliases": ["hcl_naoh", "acid_base", "neutralization", "hcl", "naoh"],
        "reaction_name": "Acid–Base Neutralization",
        "equation": "HCl + NaOH -> NaCl + H2O",
        "reaction_type": "Neutralization",
        "summary": (
            "Hydrochloric acid and sodium hydroxide react to form sodium "
            "chloride (table salt) and water. A classic neutralization."
        ),
        "mechanism": (
            "H⁺ ions from the acid combine with OH⁻ ions from the base "
            "to form water; Na⁺ and Cl⁻ remain as spectator ions."
        ),
        "reactants": ["Hydrochloric Acid", "Sodium Hydroxide"],
        "products": ["Sodium Chloride", "Water"],
        "coefficients": {"reactants": [1, 1], "products": [1, 1]},
        "conditions": ["Aqueous solution", "Room temperature"],
        "catalyst": None,
        "temperature": "Room temperature",
        "safety_notes": (
            "Strong acids and bases are corrosive. "
            "Wear gloves and eye protection when handling."
        ),
        "smiles": {
            "reactants": ["Cl", "[Na+].[OH-]"],
            "products": ["[Na+].[Cl-]", "O"],
        },
    },
    {
        "key": "esterification acetic acid ethanol ethyl acetate fischer",
        "aliases": ["esterification", "ethyl_acetate", "fischer", "acetic_acid_ethanol"],
        "reaction_name": "Fischer Esterification",
        "equation": "CH3COOH + C2H5OH -> CH3COOC2H5 + H2O",
        "reaction_type": "Esterification",
        "summary": (
            "Acetic acid and ethanol form ethyl acetate and water under "
            "acid-catalysed conditions (Fischer esterification)."
        ),
        "mechanism": (
            "A carboxylic acid reacts with an alcohol through acid-catalysed "
            "nucleophilic acyl substitution at the carbonyl carbon."
        ),
        "reactants": ["Acetic Acid", "Ethanol"],
        "products": ["Ethyl Acetate", "Water"],
        "coefficients": {"reactants": [1, 1], "products": [1, 1]},
        "conditions": ["Acid catalyst", "Reflux", "Equilibrium reaction"],
        "catalyst": "Sulfuric acid (trace)",
        "temperature": "Warm / reflux (~78 °C)",
        "safety_notes": (
            "Ethyl acetate and ethanol are flammable. "
            "Concentrated acids are corrosive."
        ),
        "smiles": {
            "reactants": ["CC(=O)O", "CCO"],
            "products": ["CC(=O)OCC", "O"],
        },
    },
    {
        "key": "ethanol oxidation acetic acid alcohol oxidation",
        "aliases": ["ethanol_oxidation", "alcohol_oxidation"],
        "reaction_name": "Ethanol Oxidation",
        "equation": "CH3CH2OH + 2[O] -> CH3COOH + H2O",
        "reaction_type": "Oxidation",
        "summary": (
            "Ethanol is oxidised to acetic acid by a suitable oxidising "
            "agent, passing through an aldehyde intermediate."
        ),
        "mechanism": (
            "The alcohol is first oxidised to acetaldehyde (ethanal), then "
            "further oxidised to acetic acid."
        ),
        "reactants": ["Ethanol", "Oxidising Agent"],
        "products": ["Acetic Acid", "Water"],
        "coefficients": {"reactants": [1, 2], "products": [1, 1]},
        "conditions": ["Oxidising reagent", "Acidic conditions"],
        "catalyst": None,
        "temperature": "Depends on oxidising agent",
        "safety_notes": (
            "Many oxidisers are hazardous. Follow reagent-specific safety guidance."
        ),
        "smiles": {"reactants": ["CCO"], "products": ["CC(=O)O", "O"]},
    },
    {
        "key": "decomposition water electrolysis hydrogen oxygen",
        "aliases": ["electrolysis", "water_decomposition", "water_electrolysis"],
        "reaction_name": "Water Electrolysis",
        "equation": "2H2O -> 2H2 + O2",
        "reaction_type": "Decomposition",
        "summary": (
            "Water is split into hydrogen and oxygen gases by passing "
            "an electric current through it."
        ),
        "mechanism": (
            "At the cathode, water is reduced to hydrogen gas. "
            "At the anode, water is oxidised to oxygen gas."
        ),
        "reactants": ["Water"],
        "products": ["Hydrogen", "Oxygen"],
        "coefficients": {"reactants": [2], "products": [2, 1]},
        "conditions": ["Electric current", "Aqueous solution"],
        "catalyst": None,
        "temperature": "Room temperature",
        "safety_notes": (
            "Hydrogen and oxygen produced together form an explosive mixture. "
            "Ensure adequate ventilation."
        ),
        "smiles": {"reactants": ["O"], "products": ["[H][H]", "O=O"]},
    },
]
