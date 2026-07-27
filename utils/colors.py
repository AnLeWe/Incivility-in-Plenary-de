# measurement/colors.py
#
# Project-wide color scheme for NormErosionGerParl.
#
# NSC type palette: Paul Tol's "muted" qualitative scheme — established in
# academic data visualization, CVD-safe by design, print-friendly.
# Reference: https://personal.sron.nl/~pault/#sec:qualitative
#
# Party palette: German political convention colors (CDU=black, SPD=red, etc.).
# Convention overrides CVD-safety — LABELS ARE MANDATORY on every mark.
# FDP's gold (#C89A00) is a real-world party-convention color, not a style pick —
# it stays fixed regardless of the brand anchors below.
#
# Brand anchors from Anna's global dataviz skill (categorical slots 1 and 4):
#   NAVY  #2a78d6  — government/executive, brand highlight
#   GOLD  #eda100  — general accent

# ── NSC event types (Tol muted) ──────────────────────────────────────────────
# Order matches Paul Tol's recommended sequence for maximum CVD separation.
# Always pair with visible direct labels.

NSC_TYPE_COLORS = {
    # Primary types (by frequency)
    "Beifall":      "#117733",  # green  — applause (positive)
    "Zwischenruf":  "#332288",  # indigo — general interjection (neutral/serious)
    "Zuruf":        "#CC6677",  # rose   — verbal call-out (attention)
    "Heiterkeit":   "#DDCC77",  # sand   — amusement (light/warm)
    "Zustimmung":   "#44AA99",  # teal   — agreement (calm)
    "Unruhe":       "#999933",  # olive  — disorder (murky)
    "Widerspruch":  "#882255",  # wine   — opposition (dark)
    "Ausruf":       "#88CCEE",  # cyan   — exclamation (open)
    # Aliases / compound types → nearest semantic slot
    "Lachen":       "#DDCC77",  # = Heiterkeit slot
    "Gelächter":    "#DDCC77",  # = Heiterkeit slot
    "Gegenruf":     "#882255",  # = Widerspruch slot
    "Unmut":        "#999933",  # = Unruhe slot
    "Wortmeldung":  "#44AA99",  # = Zustimmung/procedural slot
    "Glocke":       "#DDDDDD",  # Tol pale grey — bell/procedure (non-interjection)
    # Non-interjection types (filtered in analysis but kept for completeness)
    "glocke":       "#DDDDDD",
    "Prozedural":   "#DDDDDD",
    "mislabelled":  "#DDDDDD",
    "noise":        "#DDDDDD",
    "unknown":      "#DDDDDD",
}

# Tol muted slot order (use this sequence when building a legend or scale)
NSC_TYPE_ORDER = [
    "Beifall", "Zwischenruf", "Zuruf", "Heiterkeit",
    "Zustimmung", "Unruhe", "Widerspruch", "Ausruf",
]

# ── Party / affiliation colors ────────────────────────────────────────────────
# Convention-based. LABELS MANDATORY — no CVD guarantee as a full set.

AFFILIATION_COLORS = {
    # Institutional (anchor colors)
    "gov":  "#2a78d6",  # Government/executive — brand navy (dataviz skill slot 1)
    "pre":  "#3A3A3A",  # Presiding officer — dark gray
    "ind":  "#808080",  # Independent / fraktionslos
    "oth":  "#B8B8B8",  # Other / unspecified
    # Major parties (StateParl canonical codes)
    "cdu":  "#2A2A2A",  # CDU — near-black (party convention)
    "csu":  "#0076B6",  # CSU — Bavarian blue
    "spd":  "#E3001B",  # SPD — official red
    "grn":  "#46962B",  # GRÜNE — official green
    "fdp":  "#C89A00",  # FDP — official party gold (convention, not style)
    "lin":  "#BE3064",  # LINKE — magenta-red
    "pds":  "#BE3064",  # PDS — same as LINKE (historical predecessor)
    "afd":  "#009DE0",  # AfD — official light blue
    "bsw":  "#6B2E9E",  # BSW — purple
    # Minor parties
    "pir":  "#F35B1C",  # PIRATEN — orange
    "frw":  "#4A8B6F",  # Freie Wähler — teal (official orange conflicts with FDP)
    "ssw":  "#002147",  # SSW — dark navy
    "npd":  "#5C1A1A",  # NPD — very dark maroon
    "bag":  "#808080",  # other minor parties
    "bbr":  "#808080",
    # Canonical party name aliases (long form)
    "CDU":          "#2A2A2A",
    "CSU":          "#0076B6",
    "SPD":          "#E3001B",
    "GRÜNE":        "#46962B",
    "FDP":          "#C89A00",
    "LINKE":        "#BE3064",
    "AfD":          "#009DE0",
    "BSW":          "#6B2E9E",
    "PIRATEN":      "#F35B1C",
    "FW":           "#4A8B6F",
    "SSW":          "#002147",
    "FRAKTIONSLOS": "#808080",
}

# Affiliation display order (for legends)
AFFILIATION_ORDER = [
    "gov", "pre",
    "cdu", "csu", "spd", "grn", "fdp", "lin", "pds", "afd", "bsw",
    "pir", "frw", "ssw", "npd",
    "ind", "oth",
]

# ── Sequential ramp (Blues — Anna's global dataviz skill) ────────────────────
SEQ_BLUES = {
    100: "#cde2fb",
    150: "#b7d3f6",
    200: "#9ec5f4",
    250: "#86b6ef",
    300: "#6da7ec",
    350: "#5598e7",
    400: "#3987e5",
    450: "#2a78d6",
    500: "#256abf",
    550: "#1c5cab",
    600: "#184f95",
    650: "#104281",
    700: "#0d366b",
}

# ── Anchor / brand (dataviz skill categorical slots 1 & 4) ────────────────────
NAVY = "#2a78d6"   # primary — government, headings, key highlights
GOLD = "#eda100"   # secondary — general accent (FDP keeps its own convention gold above)

# ── Chart chrome ──────────────────────────────────────────────────────────────
CHROME = {
    "surface_light":  "#fcfcfb",
    "surface_dark":   "#1a1a19",
    "ink_primary":    "#0b0b0b",
    "ink_secondary":  "#52514e",
    "ink_muted":      "#898781",
    "gridline":       "#e1e0d9",
    "baseline":       "#c3c2b7",
}


def nsc_type_color(nsc_type: str, fallback: str = "#DDDDDD") -> str:
    """Return the hex color for an nsc_type value (or fallback if unknown)."""
    return NSC_TYPE_COLORS.get(nsc_type, fallback)


def affiliation_color(affiliation: str, fallback: str = "#808080") -> str:
    """Return the hex color for an affiliation code (or fallback if unknown)."""
    return AFFILIATION_COLORS.get(affiliation, fallback)
