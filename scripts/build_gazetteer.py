#!/usr/bin/env python3
"""Regenerate backend/investigatecelra/data/gazetteer.json.

The gazetteer is the controlled vocabulary that replaces a named-entity model.
Keeping it in one generator script makes provenance and edits obvious: add a
line here, re-run, and the whole pipeline recognises the new entity.

    python scripts/build_gazetteer.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "backend" / "investigatecelra" / "data" / "gazetteer.json"

# ---------------------------------------------------------------------------
# name | aliases (| separated) | subtype
# ---------------------------------------------------------------------------
COMPANIES = """
Pfizer||big_pharma
Novartis||big_pharma
Roche|Genentech|big_pharma
AstraZeneca|AZ|big_pharma
Merck & Co|Merck|MSD|big_pharma
GSK|GlaxoSmithKline|big_pharma
Sanofi||big_pharma
Eli Lilly|Lilly|big_pharma
Bristol Myers Squibb|BMS|Bristol-Myers Squibb|big_pharma
Johnson & Johnson|J&J|Janssen|big_pharma
AbbVie||big_pharma
Amgen||big_pharma
Gilead Sciences|Gilead|big_pharma
Novo Nordisk||big_pharma
Takeda||big_pharma
Bayer||big_pharma
Boehringer Ingelheim||big_pharma
Daiichi Sankyo||big_pharma
Astellas||big_pharma
Eisai||big_pharma
Biogen||biotech
Vertex Pharmaceuticals|Vertex|biotech
Regeneron||biotech
Moderna||biotech
BioNTech||biotech
Alnylam||biotech
Ionis Pharmaceuticals|Ionis|biotech
BeiGene||biotech
Legend Biotech||biotech
Arcus Biosciences|Arcus|biotech
Revolution Medicines||biotech
Nuvalent||biotech
Insmed||biotech
Apellis||biotech
argenx||biotech
Zealand Pharma||biotech
Structure Therapeutics||biotech
Viking Therapeutics||biotech
CRISPR Therapeutics||biotech
Intellia Therapeutics|Intellia|biotech
Beam Therapeutics|Beam|biotech
Prime Medicine||biotech
Sarepta Therapeutics|Sarepta|biotech
Recursion Pharmaceuticals|Recursion|ai_discovery
Exscientia||ai_discovery
Insilico Medicine|Insilico|ai_discovery
Isomorphic Labs||ai_discovery
Schrodinger|Schrödinger|ai_discovery
Relay Therapeutics|Relay|ai_discovery
Iambic Therapeutics|Iambic|ai_discovery
Genesis Therapeutics||ai_discovery
Chai Discovery||ai_discovery
Cradle Bio||ai_discovery
BenevolentAI||ai_discovery
Tempus AI|Tempus|data_analytics
Certara||data_analytics
Simulations Plus||data_analytics
IQVIA||cro_data
Clarivate||cro_data
Elsevier||cro_data
Veeva Systems|Veeva|cro_data
Medidata||cro_data
Dotmatics||cro_data
Benchling||cro_data
Parexel||cro
ICON plc|ICON|cro
Charles River Laboratories|Charles River|cro
Evotec||cro
WuXi AppTec|WuXi|cdmo
Lonza||cdmo
Samsung Biologics||cdmo
Illumina||omics
Oxford Nanopore||omics
10x Genomics||omics
Olink||omics
SomaLogic||omics
Guardant Health|Guardant|diagnostics
Natera||diagnostics
Foundation Medicine||diagnostics
Exact Sciences||diagnostics
Excelra||internal
"""

TARGETS = """
EGFR
KRAS|KRAS G12C|KRAS G12D
HER2|ERBB2
PD-1|PD1|pembrolizumab target
PD-L1|PDL1
CTLA-4|CTLA4
BTK
JAK1|JAK2|JAK
ALK
BRAF
MEK|MEK1
CDK4/6|CDK4|CDK6
CDK7
PARP
VEGF|VEGFR
TNF-alpha|TNF
IL-23|IL23
IL-17|IL17
IL-4R|IL4R
TSLP
GLP-1|GLP1
GIP
amylin
SGLT2
PCSK9
Lp(a)|lipoprotein(a)
Factor XI|FXI
Complement C5|C5
Complement C3|C3
BCMA
CD19
CD20
CD3
CD47
Claudin 18.2|CLDN18.2
TROP2
Nectin-4
FGFR
MET|c-Met
RET
NTRK
PI3K|PIK3CA
AKT
mTOR
STING
TIGIT
LAG-3|LAG3
SHP2
SOS1
menin|KMT2A
PRMT5|MTAP
WRN
HIF-2alpha|HIF-2α
KAT6A
LRRK2
tau|MAPT
amyloid beta|amyloid-beta|Abeta
TREM2
alpha-synuclein
huntingtin|HTT
dystrophin
CFTR
FcRn
BAFF
CGRP
"""

INDICATIONS = """
non-small cell lung cancer|NSCLC|oncology
small cell lung cancer|SCLC|oncology
breast cancer|oncology
colorectal cancer|CRC|oncology
pancreatic cancer|oncology
prostate cancer|oncology
ovarian cancer|oncology
gastric cancer|oncology
bladder cancer|urothelial carcinoma|oncology
melanoma|oncology
hepatocellular carcinoma|HCC|oncology
glioblastoma|GBM|oncology
multiple myeloma|oncology
acute myeloid leukaemia|AML|acute myeloid leukemia|oncology
chronic lymphocytic leukaemia|CLL|oncology
diffuse large B-cell lymphoma|DLBCL|oncology
obesity|cardiometabolic
type 2 diabetes|T2D|cardiometabolic
MASH|NASH|cardiometabolic
heart failure|HFpEF|cardiometabolic
chronic kidney disease|CKD|cardiometabolic
hypertension|cardiometabolic
ATTR amyloidosis|cardiometabolic
hypercholesterolaemia|hypercholesterolemia|cardiometabolic
ulcerative colitis|immunology
Crohn's disease|Crohns disease|immunology
inflammatory bowel disease|IBD|immunology
rheumatoid arthritis|RA|immunology
psoriasis|immunology
atopic dermatitis|immunology
systemic lupus erythematosus|lupus|SLE|immunology
myasthenia gravis|immunology
asthma|respiratory
COPD|respiratory
idiopathic pulmonary fibrosis|IPF|respiratory
bronchiectasis|respiratory
Alzheimer's disease|Alzheimers disease|neuroscience
Parkinson's disease|Parkinsons disease|neuroscience
amyotrophic lateral sclerosis|ALS|neuroscience
multiple sclerosis|neuroscience
Huntington's disease|Huntingtons disease|neuroscience
major depressive disorder|MDD|neuroscience
schizophrenia|neuroscience
epilepsy|neuroscience
sickle cell disease|SCD|rare
haemophilia A|hemophilia A|rare
haemophilia B|hemophilia B|rare
Duchenne muscular dystrophy|DMD|rare
cystic fibrosis|rare
spinal muscular atrophy|SMA|rare
geographic atrophy|ophthalmology
diabetic macular oedema|diabetic macular edema|ophthalmology
age-related macular degeneration|AMD|ophthalmology
"""

MODALITIES = """
small molecule
monoclonal antibody|mAb
bispecific antibody|bispecific
antibody-drug conjugate|ADC
CAR-T|CAR T-cell
TCR-T
mRNA vaccine|mRNA therapeutic
siRNA|RNAi
antisense oligonucleotide|ASO
AAV gene therapy|gene therapy
base editing
prime editing
CRISPR
targeted protein degrader|PROTAC|degrader
molecular glue
peptide therapeutic
radioligand therapy|radiopharmaceutical
allogeneic cell therapy|cell therapy
oncolytic virus
microbiome therapeutic
"""

TECHNOLOGIES = """
artificial intelligence|AI|machine learning
generative chemistry|de novo design
knowledge graph|graph database
multiomics|multi-omics
single-cell sequencing|scRNA-seq
spatial transcriptomics
proteomics
metabolomics
real-world evidence|RWE|real-world data
digital twin|in silico trial
federated learning
laboratory automation|self-driving lab
DNA-encoded library|DEL
cryo-EM
molecular dynamics|free energy perturbation|FEP
structure-activity relationship|SAR
biomarker discovery|companion diagnostic
FAIR data|data harmonisation|data harmonization
drug repurposing|drug repositioning
"""


# ---------------------------------------------------------------------------
# Core coverage set: the companies the desk queries the trial registry and
# literature for on every refresh. Name -> primary listing ticker.
# Tickers are public listing identifiers, used only as display labels.
# ---------------------------------------------------------------------------
CORE_COVERAGE = {
    "Johnson & Johnson": "JNJ",
    "Eli Lilly": "LLY",
    "AbbVie": "ABBV",
    "Merck & Co": "MRK",
    "Novo Nordisk": "NVO",
    "AstraZeneca": "AZN",
    "Roche": "ROG.SW",
    "Novartis": "NVS",
    "Pfizer": "PFE",
    "Sanofi": "SNY",
    "Amgen": "AMGN",
    "GSK": "GSK",
    "Bristol Myers Squibb": "BMY",
    "Gilead Sciences": "GILD",
    "Boehringer Ingelheim": "",
    "Takeda": "TAK",
    "Bayer": "BAYN.DE",
    "Vertex Pharmaceuticals": "VRTX",
    "Regeneron": "REGN",
    "Daiichi Sankyo": "4568.T",
    "Astellas": "4503.T",
    "Biogen": "BIIB",
    "Moderna": "MRNA",
    "BioNTech": "BNTX",
    "Eisai": "4523.T",
    "BeiGene": "ONC",
    "Alnylam": "ALNY",
    "argenx": "ARGX",
    "Ionis Pharmaceuticals": "IONS",
    "CRISPR Therapeutics": "CRSP",
}


def parse(block: str, kind: str, has_subtype: bool = False) -> list[dict]:
    out = []
    for line in block.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        subtype = ""
        if has_subtype:
            subtype = parts[-1]
            parts = parts[:-1]
        name = parts[0]
        aliases = [p for p in parts[1:] if p]
        meta: dict = {}
        if kind == "company" and name in CORE_COVERAGE:
            meta["coverage"] = "core"
            if CORE_COVERAGE[name]:
                meta["ticker"] = CORE_COVERAGE[name]
        out.append(
            {
                "id": f"{kind}:{name.lower().replace(' ', '-').replace('&', 'and')}",
                "name": name,
                "kind": kind,
                "subtype": subtype,
                "aliases": aliases,
                "meta": meta,
            }
        )
    return out


def main() -> None:
    entities: list[dict] = []
    entities += parse(COMPANIES, "company", has_subtype=True)
    entities += parse(TARGETS, "target")
    entities += parse(INDICATIONS, "indication", has_subtype=True)
    entities += parse(MODALITIES, "modality")
    entities += parse(TECHNOLOGIES, "technology")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"entities": entities}, indent=1, ensure_ascii=False), encoding="utf-8")
    counts: dict[str, int] = {}
    for e in entities:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    missing = sorted(set(CORE_COVERAGE) - {e["name"] for e in entities})
    if missing:
        raise SystemExit(f"CORE_COVERAGE names absent from COMPANIES: {missing}")
    print(f"wrote {len(entities)} entities -> {OUT}")
    print(f"  core coverage {sum(1 for e in entities if e['meta'].get('coverage') == 'core')}")
    for k, v in sorted(counts.items()):
        print(f"  {k:12s} {v}")


if __name__ == "__main__":
    main()
