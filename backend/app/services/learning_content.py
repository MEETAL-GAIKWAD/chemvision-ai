from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Flashcard, QuizChoice, QuizQuestion


FLASHCARDS = [
    {
        "topic": "Chemical bonding",
        "difficulty": "easy",
        "front": "What is an ionic bond?",
        "back": "An ionic bond is the electrostatic attraction between oppositely charged ions formed after electron transfer.",
        "example": "Na transfers one electron to Cl, producing Na+ and Cl- in sodium chloride.",
    },
    {
        "topic": "Chemical bonding",
        "difficulty": "medium",
        "front": "Why does water have a bent molecular shape?",
        "back": "Water has two bonding pairs and two lone pairs around oxygen. Lone-pair repulsion compresses the H-O-H angle to about 104.5 degrees.",
        "example": "VSEPR notation: AX2E2.",
    },
    {
        "topic": "Atomic structure",
        "difficulty": "easy",
        "front": "What does the atomic number represent?",
        "back": "The atomic number is the number of protons in the nucleus. In a neutral atom, it also equals the number of electrons.",
        "example": "Carbon has atomic number 6, so it has 6 protons.",
    },
    {
        "topic": "Periodic table",
        "difficulty": "easy",
        "front": "What trend generally happens to atomic radius across a period from left to right?",
        "back": "Atomic radius generally decreases because nuclear charge increases while added electrons enter the same principal energy level.",
        "example": "Lithium is larger than fluorine in period 2.",
    },
    {
        "topic": "Organic chemistry",
        "difficulty": "medium",
        "front": "What is Markovnikov's rule for addition to an unsymmetrical alkene?",
        "back": "In many electrophilic additions, hydrogen attaches to the alkene carbon that already has more hydrogens, forming the more stable carbocation intermediate.",
        "example": "HBr addition to propene mainly gives 2-bromopropane.",
    },
    {
        "topic": "Inorganic chemistry",
        "difficulty": "medium",
        "front": "What is a ligand in coordination chemistry?",
        "back": "A ligand is an ion or molecule that donates an electron pair to a central metal atom or ion.",
        "example": "NH3 is a ligand in [Cu(NH3)4]2+.",
    },
    {
        "topic": "Physical chemistry",
        "difficulty": "medium",
        "front": "What does activation energy mean?",
        "back": "Activation energy is the minimum energy required for reactants to reach the transition state and form products.",
        "example": "Catalysts lower activation energy by providing an alternative pathway.",
    },
    {
        "topic": "Chemical reactions",
        "difficulty": "easy",
        "front": "What is a combustion reaction?",
        "back": "A combustion reaction is a reaction with oxygen that releases energy, commonly producing oxides such as CO2 and H2O for hydrocarbons.",
        "example": "CH4 + 2O2 -> CO2 + 2H2O.",
    },
    {
        "topic": "Important formulas",
        "difficulty": "easy",
        "front": "What is the mole formula connecting mass and molar mass?",
        "back": "Number of moles equals mass divided by molar mass: n = m / M.",
        "example": "18 g of water is about 1 mol because water's molar mass is about 18 g/mol.",
    },
    {
        "topic": "Chemical reactions",
        "difficulty": "medium",
        "front": "How can you quickly check whether a chemical equation is balanced?",
        "back": "Count atoms of each element on both sides. A balanced equation has the same count for every element and preserves charge when ions are shown.",
        "example": "2H2 + O2 -> 2H2O has 4 H and 2 O atoms on both sides.",
    },
]


QUIZ_QUESTIONS = [
    {
        "topic": "Chemical bonding",
        "difficulty": "easy",
        "prompt": "Which interaction holds Na+ and Cl- together in solid sodium chloride?",
        "choices": ["Metallic bonding", "Electrostatic attraction", "Hydrogen bonding", "London dispersion only"],
        "correct": 1,
        "explanation": "NaCl is ionic. Oppositely charged ions attract through electrostatic forces.",
    },
    {
        "topic": "Atomic structure",
        "difficulty": "easy",
        "prompt": "The atomic number of an element is equal to its number of:",
        "choices": ["Neutrons", "Protons", "Protons plus neutrons", "Valence electrons only"],
        "correct": 1,
        "explanation": "Atomic number is defined by proton count.",
    },
    {
        "topic": "Periodic table",
        "difficulty": "medium",
        "prompt": "Why does electronegativity generally increase across a period?",
        "choices": [
            "Atomic mass decreases",
            "Effective nuclear charge increases",
            "Atoms gain more shells",
            "Metallic character increases",
        ],
        "correct": 1,
        "explanation": "Increasing effective nuclear charge pulls bonding electrons more strongly.",
    },
    {
        "topic": "Organic chemistry",
        "difficulty": "medium",
        "prompt": "Ethanol oxidized strongly under acidic conditions can form:",
        "choices": ["Ethane", "Ethanoic acid", "Ethene", "Ethyl chloride"],
        "correct": 1,
        "explanation": "Primary alcohols can be oxidized through aldehydes to carboxylic acids.",
    },
    {
        "topic": "Chemical reactions",
        "difficulty": "easy",
        "prompt": "Which equation is balanced?",
        "choices": [
            "H2 + O2 -> H2O",
            "2H2 + O2 -> 2H2O",
            "H2 + 2O2 -> H2O",
            "2H2 + 2O2 -> H2O",
        ],
        "correct": 1,
        "explanation": "2H2 + O2 -> 2H2O has four H atoms and two O atoms on each side.",
    },
    {
        "topic": "Important formulas",
        "difficulty": "easy",
        "prompt": "If mass is m and molar mass is M, the number of moles n is:",
        "choices": ["n = M / m", "n = m x M", "n = m / M", "n = m + M"],
        "correct": 2,
        "explanation": "The amount of substance in moles is mass divided by molar mass.",
    },
]


def seed_learning_content(db: Session) -> None:
    if db.scalar(select(Flashcard.id).limit(1)) is None:
        db.add_all(Flashcard(**card) for card in FLASHCARDS)

    if db.scalar(select(QuizQuestion.id).limit(1)) is None:
        for item in QUIZ_QUESTIONS:
            question = QuizQuestion(
                topic=item["topic"],
                difficulty=item["difficulty"],
                prompt=item["prompt"],
                explanation=item["explanation"],
            )
            question.choices = [
                QuizChoice(text=text, is_correct=(idx == item["correct"]))
                for idx, text in enumerate(item["choices"])
            ]
            db.add(question)

    db.commit()
