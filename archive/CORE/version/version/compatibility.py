"""
Verificador de compatibilidade entre versões.
"""


class Compatibility:
    @staticmethod
    def is_compatible(current: str, required: str) -> bool:
        c_major, c_minor, _ = [int(x) for x in current.split(".")]
        r_major, r_minor, _ = [int(x) for x in required.split(".")]
        return c_major == r_major and c_minor >= r_minor
