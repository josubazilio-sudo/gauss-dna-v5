from ..scanner.scanner_config import CONFLUENCE_FILTERS as SCANNER_CONFLUENCE_FILTERS, CONFLUENCE_TOTAL as SCANNER_CONFLUENCE_TOTAL

CONFLUENCE_FILTERS = SCANNER_CONFLUENCE_FILTERS
CONFLUENCE_TOTAL = SCANNER_CONFLUENCE_TOTAL

CONFLUENCE_LATERAL_FILTERS = ["bos", "choch", "adx"]

QUALITY_TIERS = {
    "ELITE": {"min_score": 90, "label": "ELITE"},
    "DIAMANTE": {"min_score": 80, "label": "DIAMANTE"},
    "OURO": {"min_score": 70, "label": "OURO"},
    "PRATA": {"min_score": 60, "label": "PRATA"},
    "BRONZE": {"min_score": 45, "label": "BRONZE"},
    "REJEITADO": {"min_score": 0, "label": "REJEITADO"},
}
