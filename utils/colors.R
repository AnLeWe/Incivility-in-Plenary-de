# measurement/colors.R
#
# Project-wide color scheme for NormErosionGerParl.
# Source this file: source("measurement/colors.R")
# Usage:  scale_fill_manual(values = NSC_TYPE_COLORS)
#         scale_colour_manual(values = AFFILIATION_COLORS)
#
# NSC types: Paul Tol's "muted" qualitative palette (CVD-safe, print-friendly).
# Parties:   German political convention colors — LABELS MANDATORY.
# Anchors:   NAVY (#152E5D) for gov, GOLD (#C89A00) for FDP / accent.

# ── NSC event type palette (Tol muted) ───────────────────────────────────────

NSC_TYPE_COLORS <- c(
  "Beifall"     = "#117733",  # green
  "Zwischenruf" = "#332288",  # indigo
  "Zuruf"       = "#CC6677",  # rose
  "Heiterkeit"  = "#DDCC77",  # sand
  "Zustimmung"  = "#44AA99",  # teal
  "Unruhe"      = "#999933",  # olive
  "Widerspruch" = "#882255",  # wine
  "Ausruf"      = "#88CCEE",  # cyan
  # Aliases
  "Lachen"      = "#DDCC77",
  "Gelächter"   = "#DDCC77",
  "Gegenruf"    = "#882255",
  "Unmut"       = "#999933",
  "Wortmeldung" = "#44AA99",
  "glocke"      = "#DDDDDD",
  "Prozedural"  = "#DDDDDD",
  "mislabelled" = "#DDDDDD",
  "noise"       = "#DDDDDD",
  "unknown"     = "#DDDDDD"
)

NSC_TYPE_ORDER <- c(
  "Beifall", "Zwischenruf", "Zuruf", "Heiterkeit",
  "Zustimmung", "Unruhe", "Widerspruch", "Ausruf"
)

# ── Affiliation / party palette ───────────────────────────────────────────────
# Convention-based; never use color as the only channel — always label.

AFFILIATION_COLORS <- c(
  # Institutional
  "gov" = "#152E5D",  # navy — government/executive
  "pre" = "#3A3A3A",  # dark gray — presiding officer
  "ind" = "#808080",  # gray — independent
  "oth" = "#B8B8B8",  # light gray — other
  # Major parties
  "cdu" = "#2A2A2A",
  "csu" = "#0076B6",
  "spd" = "#E3001B",
  "grn" = "#46962B",
  "fdp" = "#C89A00",  # gold
  "lin" = "#BE3064",
  "pds" = "#BE3064",
  "afd" = "#009DE0",
  "bsw" = "#6B2E9E",
  # Minor parties
  "pir" = "#F35B1C",
  "frw" = "#4A8B6F",
  "ssw" = "#002147",
  "npd" = "#5C1A1A",
  "bag" = "#808080",
  "bbr" = "#808080"
)

AFFILIATION_ORDER <- c(
  "gov", "pre",
  "cdu", "csu", "spd", "grn", "fdp", "lin", "pds", "afd", "bsw",
  "pir", "frw", "ssw", "npd",
  "ind", "oth"
)

# ── Sequential ramp (Blues — Anna's style) ────────────────────────────────────
# Use with scale_fill_gradient(low = SEQ_BLUES["100"], high = SEQ_BLUES["700"])
# or scale_fill_distiller(palette = "Blues", direction = 1)

SEQ_BLUES <- c(
  "100" = "#cde2fb",
  "200" = "#9ec5f4",
  "300" = "#6da7ec",
  "400" = "#3987e5",
  "450" = "#2a78d6",
  "500" = "#256abf",
  "600" = "#184f95",
  "700" = "#0d366b"
)

# ── Anchors ───────────────────────────────────────────────────────────────────
NAVY <- "#152E5D"
GOLD <- "#C89A00"

# ── ggplot2 convenience scales ────────────────────────────────────────────────
# Requires ggplot2; sourcing this file does NOT load it — call library(ggplot2)
# in your script first.

scale_fill_nsc <- function(...) {
  ggplot2::scale_fill_manual(values = NSC_TYPE_COLORS, ...)
}

scale_colour_nsc <- function(...) {
  ggplot2::scale_colour_manual(values = NSC_TYPE_COLORS, ...)
}

scale_fill_affiliation <- function(...) {
  ggplot2::scale_fill_manual(values = AFFILIATION_COLORS, ...)
}

scale_colour_affiliation <- function(...) {
  ggplot2::scale_colour_manual(values = AFFILIATION_COLORS, ...)
}
