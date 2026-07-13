import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import _resumir_motivos_sem_sinal


def _sig(rejection_reasons):
    return SimpleNamespace(rejection_reasons=rejection_reasons)


class TestResumirMotivosSemSinal(unittest.TestCase):
    """Regressao: quando report.signals nao esta vazio mas TODO sinal foi
    pre-rejeitado internamente pelo ScannerEngine (exaustao, consenso
    multi-TF insuficiente — ver ENGINE/scanner/scanner_engine.py linhas
    ~276-285 e ~340-351), main.py gravava sempre o rotulo generico
    "Nenhum sinal" no diagnostico, mesmo com o motivo real disponivel em
    signal.rejection_reasons. Isso nao muda nenhum criterio de aprovacao,
    so a fidelidade do dado registrado."""

    def test_empty_signals_list_returns_generic_label(self):
        primario, secundarios, decisao = _resumir_motivos_sem_sinal([])
        self.assertEqual(primario, "Nenhum sinal")
        self.assertEqual(secundarios, [])
        self.assertEqual(decisao, "Rejected: no signals generated")

    def test_signals_without_any_rejection_reason_returns_generic_label(self):
        signals = [_sig([]), _sig([])]
        primario, secundarios, decisao = _resumir_motivos_sem_sinal(signals)
        self.assertEqual(primario, "Nenhum sinal")

    def test_signals_all_prerejected_surface_real_reason(self):
        signals = [
            _sig(["Exaustao detectada (score=45): rsi_extremo_long"]),
            _sig(["Exaustao detectada (score=45): rsi_extremo_long"]),
            _sig(["Consenso multi-TF insuficiente (0.42 < 0.6)"]),
        ]
        primario, secundarios, decisao = _resumir_motivos_sem_sinal(signals)
        self.assertNotEqual(primario, "Nenhum sinal")
        self.assertEqual(primario, "Exaustao detectada (score=45): rsi_extremo_long")
        self.assertIn("Consenso multi-TF insuficiente (0.42 < 0.6)", secundarios)
        self.assertEqual(decisao, f"Rejected: {primario}")

    def test_duplicate_reasons_are_deduplicated_in_secondary(self):
        signals = [
            _sig(["Consenso multi-TF insuficiente (0.42 < 0.6)"]),
            _sig(["Consenso multi-TF insuficiente (0.42 < 0.6)"]),
            _sig(["Consenso multi-TF insuficiente (0.42 < 0.6)"]),
        ]
        primario, secundarios, decisao = _resumir_motivos_sem_sinal(signals)
        self.assertEqual(secundarios.count("Consenso multi-TF insuficiente (0.42 < 0.6)"), 1)

    def test_mixed_signals_some_with_some_without_reasons(self):
        """Se ALGUM sinal nao tem rejection_reasons, o loop principal de
        main.py nunca chegaria a este branch 'else' (all_decisions nao
        estaria vazio) — mas a funcao em si deve continuar robusta."""
        signals = [_sig([]), _sig(["Exaustao detectada (score=30): rsi_baixo"])]
        primario, secundarios, decisao = _resumir_motivos_sem_sinal(signals)
        self.assertEqual(primario, "Exaustao detectada (score=30): rsi_baixo")


if __name__ == "__main__":
    unittest.main()
