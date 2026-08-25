# Shared color constants for EC-KG paper figures.
#
# Palette: colorblind-safe, based on the Okabe-Ito qualitative set.
# Each biolink category group gets ONE color rather than a per-term shade
# gradient — sub-category shading, if needed, should be a lighter/darker
# tint of the group's base color rather than a distinct hue per term.

# ── Biolink category groups ────────────────────────────────────────────────────
GROUPS = [
    ("Molecular / Genetic",  "#0072B2"),
    ("Chemical / Drug",      "#009E73"),
    ("Disease / Phenotype",  "#D55E00"),
    ("Anatomy / Cell",       "#CC79A7"),
    ("Biological Process",   "#E69F00"),
    ("Organism / Taxonomy",  "#6A3D9A"),
    ("Clinical",             "#56B4E9"),
    ("Miscellaneous",        "#666666"),
]

GROUP_COLORS = dict(GROUPS)

NODE_TO_GROUP = {
    "biolink:Gene": "Molecular / Genetic",
    "biolink:Protein": "Molecular / Genetic",
    "biolink:Transcript": "Molecular / Genetic",
    "biolink:GeneFamily": "Molecular / Genetic",
    "biolink:Polypeptide": "Molecular / Genetic",
    "biolink:MicroRNA": "Molecular / Genetic",
    "biolink:RNAProduct": "Molecular / Genetic",
    "biolink:NucleicAcidEntity": "Molecular / Genetic",
    "biolink:GenomicEntity": "Molecular / Genetic",
    "biolink:Exon": "Molecular / Genetic",
    "biolink:SmallMolecule": "Chemical / Drug",
    "biolink:ChemicalEntity": "Chemical / Drug",
    "biolink:Drug": "Chemical / Drug",
    "biolink:MolecularMixture": "Chemical / Drug",
    "biolink:ChemicalMixture": "Chemical / Drug",
    "biolink:ComplexMolecularMixture": "Chemical / Drug",
    "biolink:ChemicalExposure": "Chemical / Drug",
    "biolink:Food": "Chemical / Drug",
    "biolink:MolecularEntity": "Chemical / Drug",
    "biolink:Treatment": "Chemical / Drug",
    "biolink:Disease": "Disease / Phenotype",
    "biolink:PhenotypicFeature": "Disease / Phenotype",
    "biolink:DiseaseOrPhenotypicFeature": "Disease / Phenotype",
    "biolink:PathologicalProcess": "Disease / Phenotype",
    "biolink:BehavioralFeature": "Disease / Phenotype",
    "biolink:AnatomicalEntity": "Anatomy / Cell",
    "biolink:GrossAnatomicalStructure": "Anatomy / Cell",
    "biolink:Cell": "Anatomy / Cell",
    "biolink:CellLine": "Anatomy / Cell",
    "biolink:CellularComponent": "Anatomy / Cell",
    "biolink:BiologicalProcess": "Biological Process",
    "biolink:MolecularActivity": "Biological Process",
    "biolink:Pathway": "Biological Process",
    "biolink:PhysiologicalProcess": "Biological Process",
    "biolink:EnvironmentalProcess": "Biological Process",
    "biolink:Activity": "Biological Process",
    "biolink:BiologicalEntity": "Biological Process",
    "biolink:OrganismTaxon": "Organism / Taxonomy",
    "biolink:PopulationOfIndividualOrganisms": "Organism / Taxonomy",
    "biolink:IndividualOrganism": "Organism / Taxonomy",
    "biolink:Human": "Organism / Taxonomy",
    "biolink:MaterialSample": "Organism / Taxonomy",
    "biolink:LifeStage": "Organism / Taxonomy",
    "biolink:Cohort": "Organism / Taxonomy",
    "biolink:Behavior": "Organism / Taxonomy",
    "biolink:Procedure": "Clinical",
    "biolink:ClinicalAttribute": "Clinical",
    "biolink:ClinicalIntervention": "Clinical",
    "biolink:NamedThing": "Miscellaneous",
    "biolink:PhysicalEntity": "Miscellaneous",
    "biolink:Agent": "Miscellaneous",
    "biolink:Publication": "Miscellaneous",
    "biolink:InformationContentEntity": "Miscellaneous",
    "biolink:Device": "Miscellaneous",
    "biolink:GeographicLocation": "Miscellaneous",
    "biolink:Phenomenon": "Miscellaneous",
    "biolink:Event": "Miscellaneous",
    "biolink:RetrievalSource": "Miscellaneous",
    "biolink:EnvironmentalFeature": "Miscellaneous",
    "biolink:OrganismAttribute": "Miscellaneous",
}

# ── Per-term category colors ───────────────────────────────────────────────────
# Each term takes its group's color directly (see NODE_TO_GROUP above).
CATEGORY_COLORS = {
    term: GROUP_COLORS[group] for term, group in NODE_TO_GROUP.items()
}

_FALLBACK_COLOR = "#aaaaaa"

# ── Upstream source colors ─────────────────────────────────────────────────────
# Brightened variants of the blue / gold / green family, distinguishable from
# the muted category colors above and from each other.
UPSTREAM_SOURCE_COLORS = {
    "ROBOKOP": "#17BECF",
    "RTX-KG2": "#1F77B4",
    "PrimeKG": "#FF7F0E",
}

ML_VALIDATION_MODEL_COLORS = {
    "EC-KG": GROUP_COLORS["Chemical / Drug"],
    "PrimeKG": UPSTREAM_SOURCE_COLORS["PrimeKG"],
    "ROBOKOP KG": UPSTREAM_SOURCE_COLORS["ROBOKOP"],
    "RTX-KG2": UPSTREAM_SOURCE_COLORS["RTX-KG2"],
}

# Venn diagram region colors (RGB midpoint blends of the relevant source colors)
UPSTREAM_REGION_COLORS = {
    "100": UPSTREAM_SOURCE_COLORS["ROBOKOP"],
    "010": UPSTREAM_SOURCE_COLORS["RTX-KG2"],
    "001": UPSTREAM_SOURCE_COLORS["PrimeKG"],
    "110": "#97B980",   # ROBOKOP ∩ RTX-KG2
    "101": "#17B2CB",   # ROBOKOP ∩ PrimeKG
    "011": "#80D04B",   # RTX-KG2 ∩ PrimeKG
    "111": "#64BE87",   # all three
}
