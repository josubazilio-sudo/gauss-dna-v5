"""
Score Normalizer - Módulo para padronização de todas as escalas de pontuação do QuantOS.
Toda conversão de escala deve passar por este módulo.
"""

def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Garante que um valor esteja dentro de um intervalo [min_val, max_val]."""
    return max(min_val, min(value, max_val))

def normalize(value: float, current_min: float, current_max: float) -> float:
    """Normaliza um valor de uma escala [current_min, current_max] para [0.0, 1.0]."""
    if current_max == current_min:
        return 0.0
    normalized = (value - current_min) / (current_max - current_min)
    return clamp(normalized)

def scale_100_to_1(value: float) -> float:
    """Converte escala [0, 100] para [0.0, 1.0]."""
    return clamp(value / 100.0)

def scale_1_to_100(value: float) -> float:
    """Converte escala [0.0, 1.0] para [0, 100]."""
    return clamp(value * 100.0, 0.0, 100.0)

def scale_0_100(value: float, max_val: float = 100.0) -> float:
    """Garante que um valor esteja entre 0 e max_val."""
    return clamp(value, 0.0, max_val)

def invert_score(value: float) -> float:
    """Inverte um score: 1.0 - value, garantindo [0, 1]."""
    return clamp(1.0 - value)
