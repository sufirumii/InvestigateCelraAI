"""Domain lexicons.

Everything the classifier knows lives here as explicit, auditable vocabulary.
No embeddings, no weights learned from data — an analyst can read this file and
predict exactly what the system will do with a given headline.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------
# Each event type carries:
#   label     - display name
#   polarity  - +1 progress, -1 setback, 0 neutral/structural
#   weight    - base newsworthiness for a commercial-intelligence reader (0-1)
#   patterns  - (regex, points) rules. Points accumulate; highest total wins.

EVENT_TYPES: dict[str, dict] = {
    "trial_failure": {
        "label": "Trial Failure",
        "polarity": -1,
        "weight": 1.00,
        "patterns": [
            (r"\bfail(?:ed|s|ure)\b", 3),
            (r"\bdid not (?:meet|achieve|reach)\b", 4),
            (r"\bfailed to (?:meet|achieve|demonstrate|show)\b", 5),
            (r"\bmiss(?:ed|es)? (?:the |its )?primary (?:endpoint|objective)\b", 5),
            (r"\bstatistical(?:ly)? (?:significance )?(?:was )?not (?:met|achieved|reached)\b", 4),
            (r"\bno (?:statistically )?significant (?:difference|benefit|improvement)\b", 4),
            (r"\bfutility\b", 4),
            (r"\btopline .{0,30}\bmiss\b", 4),
        ],
    },
    "program_discontinuation": {
        "label": "Programme Discontinued",
        "polarity": -1,
        "weight": 0.96,
        "patterns": [
            (r"\bdiscontinu(?:e|es|ed|ing|ation)\b", 4),
            (r"\bterminat(?:e|es|ed|ing|ion)\b", 4),
            (r"\bdeprioriti[sz](?:e|ed|ing|ation)\b", 4),
            (r"\bshelv(?:e|ed|ing)\b", 3),
            (r"\bwind(?:ing)? down\b", 3),
            (r"\breturn(?:ed|s)? (?:global )?rights\b", 4),
            (r"\bhand(?:ed|s)? back .{0,20}rights\b", 4),
        ],
    },
    "safety_event": {
        "label": "Safety Signal",
        "polarity": -1,
        "weight": 0.94,
        "patterns": [
            (r"\bclinical hold\b", 5),
            (r"\bsafety (?:signal|concern|finding|issue)\b", 4),
            (r"\bserious adverse event", 4),
            (r"\bgrade [345] (?:toxicit|adverse)", 4),
            (r"\btreatment[- ]related death", 5),
            (r"\bhepatotoxicit|\bcytokine release syndrome\b", 3),
            (r"\bblack[- ]box warning\b", 4),
            (r"\brecall(?:ed|s)?\b", 3),
        ],
    },
    "regulatory_rejection": {
        "label": "Regulatory Setback",
        "polarity": -1,
        "weight": 0.95,
        "patterns": [
            (r"\bcomplete response letter\b|\bCRL\b", 5),
            (r"\brefus(?:e|ed|al) to file\b", 5),
            (r"\bnegative opinion\b", 4),
            (r"\breject(?:s|ed)? (?:the )?(?:application|filing|submission)\b", 4),
            (r"\bwithdraw(?:n|s|al)? (?:the )?(?:application|marketing authori)", 4),
            (r"\badcomm .{0,20}\bvoted? against\b", 4),
        ],
    },
    "restructuring": {
        "label": "Restructuring",
        "polarity": -1,
        "weight": 0.80,
        "patterns": [
            (r"\blay(?:off|offs|ing off)\b", 4),
            (r"\bworkforce reduction\b|\breduc(?:e|ing|ed) (?:its )?(?:headcount|workforce)\b", 4),
            (r"\brestructur(?:e|ed|ing)\b", 3),
            (r"\bcost[- ](?:cutting|reduction) (?:plan|programme|program)\b", 3),
            (r"\bstrategic (?:review|reprioriti)", 3),
            (r"\bcash runway\b", 2),
        ],
    },
    "readout_positive": {
        "label": "Positive Readout",
        "polarity": 1,
        "weight": 0.92,
        "patterns": [
            (r"\bmet (?:the |its )?primary endpoint\b", 5),
            (r"\bstatistically significant\b", 3),
            (r"\bpositive (?:topline|top-line|pivotal|phase)\b", 4),
            (r"\bdemonstrat(?:ed|es) (?:a )?(?:significant|durable|clinically meaningful)\b", 3),
            (r"\bhazard ratio\b", 2),
            (r"\bobjective response rate\b|\bORR\b", 2),
        ],
    },
    "regulatory_approval": {
        "label": "Regulatory Approval",
        "polarity": 1,
        "weight": 0.98,
        "patterns": [
            (r"\bapprov(?:e|es|ed|al|als)\b", 3),
            (r"\bmarketing authori[sz]ation\b", 4),
            (r"\bbreakthrough therapy\b", 3),
            (r"\bfast track (?:designation)?\b", 3),
            (r"\borphan drug designation\b", 3),
            (r"\bpriority review\b", 3),
            (r"\bCHMP positive opinion\b", 4),
            (r"\baccept(?:ed|ance) .{0,25}\b(?:NDA|BLA|MAA|IND)\b", 4),
        ],
    },
    "trial_progress": {
        "label": "Trial Activity",
        "polarity": 1,
        "weight": 0.72,
        "patterns": [
            (r"\bfirst patient (?:dosed|enrolled|in)\b", 4),
            (r"\bdos(?:ed|ing) (?:the )?first\b", 4),
            (r"\bcompleted enrol(?:l)?ment\b", 4),
            (r"\binitiat(?:e|ed|es|ing) (?:a )?(?:phase|pivotal|registrational)", 4),
            (r"\bexpand(?:ed|s|ing) (?:the )?(?:cohort|trial|study)\b", 2),
            (r"\bphase (?:1|2|3|i|ii|iii)\b", 2),
            (r"\binterim analysis\b", 2),
        ],
    },
    "partnership": {
        "label": "Partnership",
        "polarity": 1,
        "weight": 0.85,
        "patterns": [
            (r"\b(?:strategic )?(?:collaboration|partnership)\b", 4),
            (r"\bco[- ]develop(?:ment)?\b", 3),
            (r"\blicens(?:e|ed|ing) (?:agreement|deal)\b", 4),
            (r"\bexclusive (?:global )?(?:rights|licen[cs]e)\b", 3),
            (r"\bmilestone payments?\b", 3),
            (r"\bupfront payment\b", 3),
            (r"\bresearch (?:alliance|agreement)\b", 3),
        ],
    },
    "ma_activity": {
        "label": "M&A",
        "polarity": 0,
        "weight": 0.90,
        "patterns": [
            (r"\bacqui(?:re|res|red|sition)\b", 4),
            (r"\bmerger\b|\bmerge(?:s|d)? with\b", 4),
            (r"\bdefinitive agreement\b", 3),
            (r"\btakeover\b|\btender offer\b", 3),
            (r"\bdivest(?:s|ed|iture)?\b", 3),
        ],
    },
    "financing": {
        "label": "Financing",
        "polarity": 1,
        "weight": 0.70,
        "patterns": [
            (r"\bseries [A-E]\b", 4),
            (r"\bclos(?:ed|es|ing) (?:a )?\$?\d", 3),
            (r"\boversubscribed\b", 3),
            (r"\bIPO\b|\binitial public offering\b", 4),
            (r"\bprivate placement\b|\bfollow[- ]on offering\b", 3),
            (r"\braise[sd]? \$\d", 3),
        ],
    },
    "platform_ai": {
        "label": "AI / Platform",
        "polarity": 1,
        "weight": 0.86,
        "patterns": [
            (r"\bmachine learning\b|\bdeep learning\b", 3),
            (r"\bartificial intelligence\b|\bAI[- ](?:driven|enabled|powered|native)\b", 4),
            (r"\bfoundation model\b|\bgenerative (?:AI|model)\b", 4),
            (r"\bin silico\b", 3),
            (r"\bmultiomics?\b|\bmulti[- ]omics\b", 4),
            (r"\bknowledge graph\b", 4),
            (r"\breal[- ]world (?:data|evidence)\b", 3),
            (r"\bFAIR data\b|\bdata harmoni[sz]ation\b", 3),
        ],
    },
    "repurposing": {
        "label": "Repurposing",
        "polarity": 1,
        "weight": 0.84,
        "patterns": [
            (r"\brepurpos(?:e|ed|ing)\b", 5),
            (r"\brepositioning\b", 4),
            (r"\blabel expansion\b|\bnew indication\b", 4),
            (r"\bsecond(?:ary)? indication\b", 3),
        ],
    },
    "publication": {
        "label": "Publication",
        "polarity": 0,
        "weight": 0.60,
        "patterns": [
            (r"\bpublished in\b", 4),
            (r"\bpeer[- ]reviewed\b", 3),
            (r"\bpreprint\b", 3),
            (r"\bpresented at\b", 3),
            (r"\bposter (?:session|presentation)\b", 2),
        ],
    },
    "ip_patent": {
        "label": "IP & Patent",
        "polarity": 0,
        "weight": 0.66,
        "patterns": [
            (r"\bpatent (?:granted|issued|application|litigation|dispute)\b", 4),
            (r"\bloss of exclusivity\b|\bLOE\b", 4),
            (r"\bbiosimilar\b|\bgeneric entry\b", 3),
            (r"\bparagraph IV\b", 4),
        ],
    },
}

SETBACK_TYPES = {
    "trial_failure",
    "program_discontinuation",
    "safety_event",
    "regulatory_rejection",
    "restructuring",
}

# ---------------------------------------------------------------------------
# Limitation phrases — evidence that a programme has a stated constraint.
# Extracted verbatim (as a sentence) and shown on the Setbacks board.
# ---------------------------------------------------------------------------
LIMITATION_CUES = [
    "however", "although", "despite", "limitation", "limited by", "constrained",
    "small sample", "single-arm", "open-label", "underpowered", "exploratory endpoint",
    "not powered", "did not reach", "remains unclear", "uncertain", "no comparator",
    "attrition", "dropout", "manufacturing challenge", "scale-up", "cold chain",
    "reimbursement", "payer pushback", "pricing pressure", "supply constraint",
    "regulatory uncertainty", "data gap", "missing data", "heterogeneity",
    "off-target", "toxicity", "durability", "narrow therapeutic window",
]

# ---------------------------------------------------------------------------
# Clinical phase ranking — drives commercial impact weighting.
# ---------------------------------------------------------------------------
PHASE_WEIGHTS = {
    "preclinical": 0.30,
    "phase 1": 0.45,
    "phase 1/2": 0.55,
    "phase 2": 0.70,
    "phase 2/3": 0.82,
    "phase 3": 1.00,
    "phase 4": 0.65,
    "registrational": 1.00,
    "pivotal": 0.95,
    "filed": 0.92,
    "approved": 0.90,
}

PHASE_PATTERNS = [
    (r"\bphase\s*(?:iii|3)\b|\bregistrational\b|\bpivotal\b", "phase 3"),
    (r"\bphase\s*(?:ii/iii|2/3)\b", "phase 2/3"),
    (r"\bphase\s*(?:ii|2)\b", "phase 2"),
    (r"\bphase\s*(?:i/ii|1/2)\b", "phase 1/2"),
    (r"\bphase\s*(?:iv|4)\b", "phase 4"),
    (r"\bphase\s*(?:i|1)\b", "phase 1"),
    (r"\bpre[- ]?clinical\b|\bIND[- ]enabling\b", "preclinical"),
]

# ---------------------------------------------------------------------------
# Source tiers — editorial authority weighting (0-1).
# ---------------------------------------------------------------------------
SOURCE_TIERS = {
    "registry": 1.00,      # ClinicalTrials.gov, EU CTIS
    "regulator": 1.00,     # FDA, EMA
    "filing": 0.95,        # SEC EDGAR
    "journal": 0.90,       # PubMed, Nature, Lancet
    "company": 0.80,       # corporate press release
    "trade": 0.72,         # Fierce, Endpoints, BioSpace
    "aggregator": 0.55,
    "unknown": 0.50,
}

# ---------------------------------------------------------------------------
# Stopwords for the extractive summariser / keyword extractor.
# ---------------------------------------------------------------------------
STOPWORDS = set("""
a about above after again against all also am an and any are aren as at be because been
before being below between both but by can cannot could couldn did didn do does doesn doing
don down during each few for from further had hadn has hasn have haven having he her here
hers herself him himself his how i if in into is isn it its itself just ll me more most
mustn my myself no nor not now of off on once only or other ought our ours ourselves out
over own re s same shan she should shouldn so some such t than that the their theirs them
themselves then there these they this those through to too under until up ve very was wasn
we were weren what when where which while who whom why will with won would wouldn y you
your yours yourself yourselves said says say new one two three per across amid via
""".split())

# Terms that make a sentence more likely to be commercially informative.
SALIENT_TERMS = set("""
phase endpoint primary secondary patients enrolled cohort dose regulatory approval fda ema
chmp filing submission partnership licence license milestone upfront royalty acquisition
revenue guidance discontinued terminated failed safety hold biomarker companion diagnostic
indication oncology neurology immunology rare orphan pipeline asset readout topline
survival response rate efficacy tolerability manufacturing supply commercial launch payer
reimbursement market share exclusivity patent biosimilar multiomics genomics proteomics
""".split())
