# ---------------------------------------------------------------------------
# Regras de Compliance — todas ativaveis/desativaveis
# ---------------------------------------------------------------------------

ENABLE_MAX_POSITIONS = True
MAX_POSITIONS = 5

ENABLE_MAX_DAILY_OPERATIONS = True
MAX_DAILY_OPERATIONS = 10

ENABLE_MAX_DAILY_RISK = True
MAX_DAILY_RISK = 1000.0

ENABLE_MAX_DAILY_DRAWDOWN = True
MAX_DAILY_DRAWDOWN = 500.0

ENABLE_MAX_WEEKLY_DRAWDOWN = True
MAX_WEEKLY_DRAWDOWN = 1500.0

ENABLE_MAX_MONTHLY_DRAWDOWN = True
MAX_MONTHLY_DRAWDOWN = 3000.0

ENABLE_MAX_EXPOSURE_PER_ASSET = True
MAX_EXPOSURE_PER_ASSET = 0.30

ENABLE_MAX_EXPOSURE_PER_SECTOR = True
MAX_EXPOSURE_PER_SECTOR = 0.50

ENABLE_MAX_EXPOSURE_PER_DIRECTION = True
MAX_EXPOSURE_PER_DIRECTION = 0.70

ENABLE_MAX_CORRELATION = True
MAX_CORRELATION = 0.80

ENABLE_MAX_LEVERAGE = True
MAX_LEVERAGE = 3.0

ENABLE_TRADING_HOURS = True
TRADING_HOURS_START = 8
TRADING_HOURS_END = 18

ENABLE_CIRCUIT_BREAKER = True

ENABLE_HIGH_VOLATILITY_BLOCK = True

ENABLE_MACRO_EVENT_BLOCK = True

# ---------------------------------------------------------------------------
# Pesos para calculo do compliance score
# ---------------------------------------------------------------------------

COMPLIANCE_PERFECT = 1.0
COMPLIANCE_PENALTY_PER_RULE = 0.15
COMPLIANCE_MIN = 0.0
