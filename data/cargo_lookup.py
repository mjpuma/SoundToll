"""
Cargo ID to commodity lookup, port standardization, and passage-commodity expansion.

Requires:
- cargoes_regs.csv or ladingen.csv from STRO 2.0 Figshare
- Fixed Port City & Cargo Mappings.xlsx with Cargo and fixed_port_mappings sheets

Commodity standardization follows the 4OCEANS / Sound Toll reference workflow
(https://github.com/emileDesmaili/4OCEANS/tree/main/soundtoll):
- cargo_eda.ipynb: exact merge of cargoes_regs.commodity to a mapping table (original_commodity -> standardized_name).
- soundtoll_old.Rmd: read.table(ladingen, sep=";"); str_trim(tolower(soort));
  stri_trans_general(..., "Latin-ASCII") for normalized joins; case_when regex patterns for English labels.

There are no .py files in that repo; logic above is ported from those notebooks/Rmd.

Compound raw lading strings (e.g. "hvede og rug", "salt, sukker") are split and each token
is standardized; get_cargo_lookup returns one cargo_id -> list of English labels.
"""

import ast
import re
import unicodedata
from pathlib import Path

import pandas as pd

# Default paths (relative to project root)
DEFAULT_LADINGEN_PATH = "data/ladingen.csv"
DEFAULT_CARGOES_REGS_PATH = "data/cargoes_regs.csv"
DEFAULT_MAPPINGS_PATH = "Fixed Port City & Cargo Mappings.xlsx"
DEFAULT_COMMODITY_MASTER_PATH = "data/commodity_master.csv"


def _latin_ascii_normalize(s: str) -> str:
    """
    Approximate R stringi::stri_trans_general(x, "Latin-ASCII") for Nordic text.

    Used like soundtoll_old.Rmd does on standardised_commodity before joining.
    """
    if not s:
        return ""
    # Decompose and drop combining marks (accents on Latin letters)
    nfd = unicodedata.normalize("NFD", s)
    out = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Characters that do not decompose (e.g. ø, æ, å)
    repl = {
        "ø": "o",
        "Ø": "O",
        "æ": "ae",
        "Æ": "Ae",
        "å": "aa",
        "Å": "Aa",
        "ð": "d",
        "þ": "th",
        "œ": "oe",
        "Œ": "Oe",
        "ß": "ss",
    }
    for a, b in repl.items():
        out = out.replace(a, b)
    return out


def _prepare_soort_for_match(raw: str) -> str:
    """Trim, lowercase, strip trailing noise like ' -' (common in STRO exports)."""
    s = str(raw).strip()
    s = re.sub(r"\s*-\s*$", "", s).strip()
    return s.lower()


# Split mixed cargoes: "hvede og rug", "salt, sukker", "a / b"
_SPLIT_MIXED_RE = re.compile(
    r"\s+og\s+|,|;|\s*/\s*|\s*&\s*|\s+\+\s+",
    re.I,
)


def _split_mixed_raw_commodity(raw: str) -> list[str]:
    """Return token strings for each good in a compound lading (Danish 'og' = and)."""
    s = str(raw).strip()
    if not s or s == "-":
        return []
    parts = _SPLIT_MIXED_RE.split(s)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [s]


# Regex case_when rules from soundtoll_old.Rmd (order = first match wins; specific before broad).
# Ported from R str_detect(soort, regex(..., ignore_case=TRUE)).
# Input is lowercased in _standardize_one_raw_commodity (Unicode ø/æ/å preserved).
# CRITICAL: Linseed (hørfrø) before any rule that matches plain "hør"; fiin/ord hør before \bhør\b;
# fyrre bjelk* before bjelk*; skudeplank* before plank*.
_REGEX_COMMODITY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sukker|sucker|raff|raat|sukker etc\.", re.I), "Sugar"),
    (re.compile(r"bomuld|bomuldsgarn|bom\.\s*garn", re.I), "Cotton"),
    (re.compile(r"tobak|toback", re.I), "Tobacco"),
    (re.compile(r"caffe|kaffe", re.I), "Coffee"),
    (re.compile(r"indigo", re.I), "Indigo"),
    (re.compile(r"peber", re.I), "Pepper"),
    (re.compile(r"riis|ris", re.I), "Rice"),
    (re.compile(r"stokfiskholt|stokf\.\s*holt", re.I), "Stockfish"),
    (re.compile(r"svedsker", re.I), "Prunes"),
    (re.compile(r"blauholt|blue wood|logwood", re.I), "Logwood (Dye)"),
    (re.compile(r"kiøbmandskaber|kjøbmandskaber|krammerie", re.I), "Merchandise"),
    (re.compile(r"krap", re.I), "Madder (Dye Plant)"),
    (re.compile(r"hamp", re.I), "Hemp"),
    (re.compile(r"staal", re.I), "Steel"),
    (re.compile(r"ballast", re.I), "Ballast"),
    # Wheat flour / meal before plain "hvede" (substring "hvede" would else swallow hvedemel)
    (re.compile(r"hvedemel|hvede\s*mel|hveedemel", re.I), "Wheat flour"),
    (
        re.compile(
            r"\bhvede\b|\bhveede\b|\bhuede\b|\bwheat\b|\bweizen\b|\bfroment\b",
            re.I,
        ),
        "Wheat",
    ),
    (re.compile(r"tælle|taelle", re.I), "Tallow"),
    (re.compile(r"erter", re.I), "Peas"),
    (re.compile(r"sild", re.I), "Herring"),
    (re.compile(r"byg", re.I), "Barley"),
    # Salt (high-frequency unmatched)
    (re.compile(r"salt|saltt|s[ao]lt\b", re.I), "Salt"),
    # Timber — beams (specific compound before stem)
    (
        re.compile(
            r"fyrre\s+bjelk|fyrre\s+bielk|furu.*bjelk|eg.*bjelk|bielk|bjelk|bjælk",
            re.I,
        ),
        "Timber beams",
    ),
    # Timber — planks / boards (skudeplank* before plank*)
    (
        re.compile(
            r"skudeplanker|skude.*plank|ord\.?\s*bræder|bræder|breder|braeder|planker|planck",
            re.I,
        ),
        "Planks",
    ),
    # Timber — split / specialty
    (
        re.compile(
            r"clapholt|klapholt|claphholt|splitholt|split.*holt|lægter|laegter|pr\.?\s*dehler|\bdehler\b",
            re.I,
        ),
        "Split timber",
    ),
    # Flax tow (before dressed flax / linseed)
    (re.compile(r"blaar|bl[aå]r\b", re.I), "Flax tow"),
    # hørfrø / ASCII mangling — MUST precede plain hør (flax)
    (re.compile(r"h[oø]rfr[oø]e?|horfroe|horfr", re.I), "Linseed"),
    # Flax dressed (fiin hør, ord. hør before standalone hør)
    (
        re.compile(
            r"fiin\s*h[oø]r|ord\.?\s*h[oø]r|^h[oø]r\s|h[oø]r$|\bh[oø]r\b",
            re.I,
        ),
        "Flax",
    ),
    (re.compile(r"staver|staves", re.I), "Staves"),
    (re.compile(r"jern", re.I), "Iron"),
    # Coal / charcoal
    (re.compile(r"\bkul\b|kul$|^kul\s|steenkul|træ.*kul", re.I), "Coal"),
    # Ash / potash
    (
        re.compile(
            r"\basche\b|\baske\b|asch$|aschen|pot.*ash|pott?aske",
            re.I,
        ),
        "Ash/Potash",
    ),
    # Wine
    (re.compile(r"\bviin\b|\bvin\b|wein|wijn", re.I), "Wine"),
    # Malt
    (re.compile(r"\bmalt\b|maltt", re.I), "Malt"),
    # Rye: ruug / rueg / word "rug" (substring "rug" does not match "ruug")
    (re.compile(r"ruug|rueg|\brug\b", re.I), "Rye"),
    (re.compile(r"ost", re.I), "Cheese"),
]


def _regex_standardize_commodity(soort_lower: str) -> str | None:
    """Apply R case_when-style rules to lowercased soort."""
    for pat, label in _REGEX_COMMODITY_RULES:
        if pat.search(soort_lower):
            return label
    return None


# Standard English labels from regex / Excel -> review taxonomy (build_commodity_master)
_COMMODITY_CATEGORY_BY_LABEL_LOWER: dict[str, str] = {
    "rye": "GRAIN",
    "wheat": "GRAIN",
    "wheat flour": "GRAIN",
    "barley": "GRAIN",
    "malt": "GRAIN",
    "salt": "SALT",
    "coal": "COAL",
    "linseed": "LINSEED",
    "timber beams": "TIMBER",
    "planks": "TIMBER",
    "split timber": "TIMBER",
    "staves": "TIMBER",
    "flax": "TEXTILE_RAW",
    "flax tow": "TEXTILE_RAW",
    "hemp": "TEXTILE_RAW",
    "cotton": "TEXTILE_RAW",
    "iron": "METALS",
    "steel": "METALS",
    "herring": "PROVISIONS",
    "cheese": "PROVISIONS",
    "stockfish": "PROVISIONS",
    "prunes": "PROVISIONS",
    "tallow": "PROVISIONS",
    "peas": "PROVISIONS",
    "wine": "ALCOHOL",
    "sugar": "COLONIAL",
    "tobacco": "COLONIAL",
    "coffee": "COLONIAL",
    "pepper": "COLONIAL",
    "indigo": "COLONIAL",
    "rice": "COLONIAL",
    "ash/potash": "POTASH",
    "logwood (dye)": "OTHER",
    "merchandise": "OTHER",
    "madder (dye plant)": "OTHER",
    "ballast": "OTHER",
}


def standard_category_for_label(label: str, match_status: str | None = None) -> str:
    """
    Broad taxonomy bucket for a standardized commodity label (used by commodity_master.csv).

    Based on standard_label text; UNKNOWN when unmatched or Unknown.
    """
    if match_status == "unmatched" or not (label or "").strip() or str(label).strip() == "Unknown":
        return "UNKNOWN"
    key = str(label).strip().lower()
    return _COMMODITY_CATEGORY_BY_LABEL_LOWER.get(key, "OTHER")


def _build_excel_commodity_map(cargo_df: pd.DataFrame) -> dict[str, str]:
    """
    Build lookup: multiple keys per row (lowercase raw, latin-ascii lowercase raw)
    -> English translation when present.
    Mirrors exact-merge keys after normalization like 4OCEANS cargo_eda + Latin-ASCII keys.
    """
    raw_col = "cargo names in dataset"
    trans_col = "translations"
    out: dict[str, str] = {}
    for _, r in cargo_df.iterrows():
        raw = str(r[raw_col]).strip() if pd.notna(r[raw_col]) else ""
        if not raw or raw == "-":
            continue
        trans = r[trans_col] if pd.notna(r[trans_col]) else None
        if trans is None or str(trans).strip() == "" or str(trans).lower() == "nan":
            standard = None
        else:
            standard = str(trans).strip()
        if not standard:
            continue
        for key in {_prepare_soort_for_match(raw), _latin_ascii_normalize(raw).lower()}:
            if key:
                out[key] = standard
    return out


def _display_commodity(standard: str) -> str:
    """Normalize casing for labels (Excel translations may be lowercase 'staves')."""
    if not standard:
        return standard
    if standard.islower():
        return standard.title()
    return standard


def _standardize_one_raw_commodity(
    raw: str,
    excel_map: dict[str, str],
) -> str:
    """Excel (incl. Latin-ASCII key) then regex rules from R; else title-case raw."""
    raw_clean = str(raw).strip()
    if not raw_clean or raw_clean == "-":
        return "Unknown"

    soort = _prepare_soort_for_match(raw_clean)
    if not soort:
        return "Unknown"

    # Exact / normalized keys (cargo_eda style merge + Latin-ASCII variant)
    if soort in excel_map:
        return _display_commodity(excel_map[soort])
    lat = _latin_ascii_normalize(soort).lower()
    if lat in excel_map:
        return _display_commodity(excel_map[lat])

    # R case_when regex on lowercased soort
    rx = _regex_standardize_commodity(soort)
    if rx is not None:
        return _display_commodity(rx)

    # Fallback: display
    return soort.title()


def _normalize_reviewed(val) -> bool:
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except TypeError:
        pass
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("", "nan"):
        return False
    return s in ("true", "1", "yes", "y", "t", "x")


def _lookup_master_raw(raw: str, master_map: dict[str, str]) -> str | None:
    """Return standard_label from master if raw matches any normalized key."""
    s = str(raw).strip()
    if not s:
        return None
    for k in (s, _prepare_soort_for_match(s), _latin_ascii_normalize(s).lower()):
        if k and k in master_map:
            return master_map[k]
    return None


def _labels_from_master_standard_label(std: str) -> list[str]:
    """Split compound expert labels on ; or |."""
    std = str(std).strip()
    if not std:
        return ["Unknown"]
    if re.search(r"[;|]", std):
        parts = re.split(r"[;|]", std)
        return [p.strip() for p in parts if p.strip()]
    return [std]


def load_commodity_master_map(path: str | Path) -> dict[str, str]:
    """
    Load authoritative raw -> standard_label from commodity_master.csv.

    Rows where reviewed is truthy OR match_status == excel_exact are included.
    """
    path = Path(path)
    if not path.exists():
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "raw_commodity" not in df.columns or "standard_label" not in df.columns:
        return {}
    out: dict[str, str] = {}
    for _, r in df.iterrows():
        raw = str(r["raw_commodity"]).strip()
        if not raw or raw.lower() == "nan":
            continue
        reviewed = r.get("reviewed", "")
        ms = str(r.get("match_status", "")).strip().lower()
        if not _normalize_reviewed(reviewed) and ms != "excel_exact":
            continue
        std = str(r["standard_label"]).strip()
        if not std:
            continue
        for k in {raw, _prepare_soort_for_match(raw), _latin_ascii_normalize(raw).lower()}:
            if k:
                out[k] = std
    return out


def _standardize_raw_to_commodities(
    raw: str,
    excel_map: dict[str, str],
    master_map: dict[str, str] | None = None,
) -> list[str]:
    """One or more standard labels: master CSV (if hit) else split + Excel/regex per token."""
    if master_map:
        hit = _lookup_master_raw(raw, master_map)
        if hit is not None:
            return _labels_from_master_standard_label(hit)
    parts = _split_mixed_raw_commodity(raw)
    if not parts:
        return ["Unknown"]
    labels = [_standardize_one_raw_commodity(p, excel_map) for p in parts]
    out: list[str] = []
    for lb in labels:
        if lb not in out:
            out.append(lb)
    return out if out else ["Unknown"]


def _part_matched_excel_or_regex(part: str, excel_map: dict[str, str]) -> bool:
    """Whether a single token maps via Excel/Latin or regex."""
    raw_clean = str(part).strip()
    if not raw_clean or raw_clean == "-":
        return True
    soort = _prepare_soort_for_match(raw_clean)
    if not soort:
        return True
    if soort in excel_map or _latin_ascii_normalize(soort).lower() in excel_map:
        return True
    return _regex_standardize_commodity(soort) is not None


def get_cargo_lookup(
    ladingen_path: str | Path | None = None,
    cargoes_regs_path: str | Path | None = None,
    mappings_path: str | Path | None = None,
    commodity_master_path: str | Path | None = None,
) -> dict[int, list[str]]:
    """
    Build cargo_id -> list of standard commodity labels (mixed lading split into multiple goods).

    If data/commodity_master.csv exists (or ``commodity_master_path``), rows with
    reviewed==True or match_status==excel_exact override regex for that raw string.

    Uses cargoes_regs.csv (sep=';', utf-8) like 4OCEANS cargo_eda.ipynb.
    """
    ladingen_path = Path(ladingen_path or DEFAULT_LADINGEN_PATH)
    cargoes_regs_path = Path(cargoes_regs_path or DEFAULT_CARGOES_REGS_PATH)
    mappings_path = Path(mappings_path or DEFAULT_MAPPINGS_PATH)

    if not mappings_path.exists():
        raise FileNotFoundError(f"Mappings file not found: {mappings_path}")

    cargo_to_raw: dict[int, str] = {}

    if cargoes_regs_path.exists():
        df = pd.read_csv(cargoes_regs_path, sep=";", usecols=["cargo_id", "commodity"], low_memory=False, encoding="utf-8")
        cargo_to_raw = dict(zip(df["cargo_id"].astype(int), df["commodity"].astype(str).str.strip()))
    elif ladingen_path.exists():
        sample = pd.read_csv(ladingen_path, nrows=1, encoding="utf-8")
        commodity_col = "soort" if "soort" in sample.columns else "commodity"
        if commodity_col not in sample.columns:
            raise ValueError(f"ladingen must have 'soort' or 'commodity'. Found: {list(sample.columns)}")
        ladingen = pd.read_csv(ladingen_path, usecols=[commodity_col], encoding="utf-8", low_memory=False)
        ladingen["cargo_id"] = ladingen.index
        cargo_to_raw = dict(zip(ladingen["cargo_id"], ladingen[commodity_col].astype(str).str.strip()))
    else:
        raise FileNotFoundError(
            f"Neither ladingen.csv nor cargoes_regs.csv found. "
            "Download cargoes_regs.csv from https://figshare.com/articles/dataset/STRO_2_0_-_Re-engineered_data_from_Sound_Toll_Registers_Online/27176202"
        )

    cargo_df = pd.read_excel(mappings_path, sheet_name="Cargo", header=0)
    excel_map = _build_excel_commodity_map(cargo_df)

    cmp_path = Path(
        commodity_master_path
        if commodity_master_path is not None
        else Path(__file__).resolve().parent / "commodity_master.csv"
    )
    master_map: dict[str, str] = {}
    if cmp_path.exists():
        master_map = load_commodity_master_map(cmp_path)

    n_master = 0
    result: dict[int, list[str]] = {}
    for cid, raw in cargo_to_raw.items():
        if master_map and _lookup_master_raw(raw, master_map) is not None:
            n_master += 1
        result[int(cid)] = _standardize_raw_to_commodities(
            raw, excel_map, master_map if master_map else None
        )

    if cmp_path.exists():
        n_fb = len(cargo_to_raw) - n_master
        print(
            f"  commodity_master.csv: {len(master_map):,} lookup keys; "
            f"{n_master:,} cargo_ids via master (reviewed or excel_exact); "
            f"{n_fb:,} via Excel+regex fallback"
        )
    return result


def commodity_unmatched_frequency(
    cargoes_regs_path: str | Path | None = None,
    mappings_path: str | Path | None = None,
) -> tuple[pd.DataFrame, int]:
    """
    Raw commodity strings that match neither Excel (with Latin-ASCII key) nor R regex rules.

    Returns (top 20 by row count, n_unique_unmapped).
    """
    cargoes_regs_path = Path(cargoes_regs_path or DEFAULT_CARGOES_REGS_PATH)
    mappings_path = Path(mappings_path or DEFAULT_MAPPINGS_PATH)
    df = pd.read_csv(cargoes_regs_path, sep=";", usecols=["commodity"], low_memory=False, encoding="utf-8")
    cargo_df = pd.read_excel(mappings_path, sheet_name="Cargo", header=0)
    excel_map = _build_excel_commodity_map(cargo_df)

    def _still_unmapped(raw: str) -> bool:
        raw = str(raw).strip()
        if not raw or raw == "-":
            return False
        for part in _split_mixed_raw_commodity(raw):
            if not _part_matched_excel_or_regex(part, excel_map):
                return True
        return False

    df = df.copy()
    df["_u"] = df["commodity"].map(_still_unmapped)
    unmatched = df.loc[df["_u"], "commodity"].astype(str).str.strip()
    vc = unmatched.value_counts().head(20)
    out = vc.reset_index()
    out.columns = ["raw_commodity", "row_count"]
    n_unique = df.loc[df["_u"], "commodity"].astype(str).str.strip().nunique()
    return out, int(n_unique)


def get_port_mapping(
    mappings_path: str | Path | None = None,
) -> dict[str, str]:
    """
    Build variant -> fixed_city mapping from fixed_port_mappings sheet.

    Returns
    -------
    dict[str, str]
        For each variant in cities column, maps to fixed_city.
    """
    mappings_path = Path(mappings_path or DEFAULT_MAPPINGS_PATH)
    if not mappings_path.exists():
        raise FileNotFoundError(f"Mappings file not found: {mappings_path}")

    df = pd.read_excel(mappings_path, sheet_name="fixed_port_mappings", header=0)
    result = {}
    for _, r in df.iterrows():
        fixed = str(r["fixed_city"]).strip() if pd.notna(r["fixed_city"]) else ""
        if not fixed:
            continue
        cities_str = r["cities"] if pd.notna(r["cities"]) else ""
        for v in str(cities_str).split(","):
            v = v.strip()
            if v:
                result[v] = fixed
        result[fixed] = fixed  # fixed_city maps to itself
    return result


def standardize_ports(
    df: pd.DataFrame,
    port_mapping: dict[str, str] | None = None,
    mappings_path: str | Path | None = None,
    cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Replace port names with standardized fixed_city.

    Parameters
    ----------
    df : pd.DataFrame
        Data with departure, destination (or cols).
    port_mapping : dict | None
        variant -> fixed_city. If None, loaded from mappings_path.
    mappings_path : str | Path | None
        Path to Excel mappings file.
    cols : list[str] | None
        Columns to standardize. Default: ["departure", "destination"].

    Returns
    -------
    pd.DataFrame
        Copy of df with port columns standardized.
    """
    out = df.copy()
    cols = cols or ["departure", "destination"]
    if port_mapping is None:
        port_mapping = get_port_mapping(mappings_path)

    for col in cols:
        if col not in out.columns:
            continue
        def _map_port(x):
            if pd.isna(x) or str(x).strip() in ("", "nan"):
                return x
            s = str(x).strip()
            return port_mapping.get(s, s)
        out[col] = out[col].apply(_map_port)
    return out


def _parse_cargo_ids(val) -> list[int]:
    """Parse cargo_ids from string like '[2122447, 2012249]' or '[]' to list of ints."""
    if pd.isna(val) or val is None:
        return []
    s = str(val).strip()
    if not s or s in ("[]", "nan"):
        return []
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [int(x) for x in parsed if x is not None and str(x).isdigit()]
        if isinstance(parsed, (int, float)):
            return [int(parsed)]
    except (ValueError, SyntaxError):
        # Fallback: extract numbers
        nums = re.findall(r"\d+", s)
        return [int(n) for n in nums]
    return []


def expand_passages_to_commodities(
    df: pd.DataFrame,
    cargo_lookup: dict[int, list[str]] | None = None,
    ladingen_path: str | Path | None = None,
    cargoes_regs_path: str | Path | None = None,
    mappings_path: str | Path | None = None,
    commodity_master_path: str | Path | None = None,
    cargo_ids_col: str = "cargo_ids",
    drop_empty_cargo: bool = True,
) -> pd.DataFrame:
    """
    Explode rows: one row per (passage, commodity). Full passage count per commodity.

    Parameters
    ----------
    df : pd.DataFrame
        Data with cargo_ids column.
    cargo_lookup : dict | None
        cargo_id -> list of standard commodities (mixed lading yields multiple). If None, built from ladingen + mappings.
    ladingen_path, cargoes_regs_path, mappings_path : str | Path | None
        Paths for building cargo_lookup when not provided.
    commodity_master_path : str | Path | None
        Optional path to data/commodity_master.csv (human-verified overrides).
    cargo_ids_col : str
        Column name for cargo_ids.
    drop_empty_cargo : bool
        If True, drop rows with no cargo_ids. Else assign "No_cargo".

    Returns
    -------
    pd.DataFrame
        Exploded data with commodity column. Same passage info duplicated per commodity.
    """
    if cargo_lookup is None:
        cargo_lookup = get_cargo_lookup(
            ladingen_path=ladingen_path,
            cargoes_regs_path=cargoes_regs_path,
            mappings_path=mappings_path,
            commodity_master_path=commodity_master_path,
        )

    rows = []
    for idx, r in df.iterrows():
        cargo_ids = _parse_cargo_ids(r.get(cargo_ids_col))
        if not cargo_ids:
            if not drop_empty_cargo:
                row = r.to_dict()
                row["commodity"] = "No_cargo"
                rows.append(row)
            continue

        commodities = set()
        for cid in cargo_ids:
            if cid in cargo_lookup:
                for comm in cargo_lookup[cid]:
                    commodities.add(comm)
            # else: skip unknown cargo_id
        if not commodities:
            if not drop_empty_cargo:
                row = r.to_dict()
                row["commodity"] = "Unknown"
                rows.append(row)
            continue

        for comm in commodities:
            row = r.to_dict()
            row["commodity"] = comm
            rows.append(row)

    return pd.DataFrame(rows)

