import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from audit_models import AuditResult

def test_audit_result_structure():
    """Verifica se todos os campos obrigatórios existem e possuem tipos corretos."""
    res = AuditResult(ativo="BTCUSDT", cycle_id=1)
    
    assert isinstance(res.ativo, str)
    assert isinstance(res.cycle_id, int)
    assert res.schema_version == "1.0"
    assert res.engine_version == "V6.1"
    print("OK: Estrutura e tipos validados.")
    
def test_validation_logic():
    """Valida se objetos válidos passam e incompletos falham."""
    # Caso válido
    res = AuditResult(ativo="BTCUSDT", cycle_id=1)
    assert res.validate() is True
    
    # Caso inválido (simulando falha)
    res_invalid = AuditResult(ativo=None, cycle_id=None)
    try:
        res_invalid.validate()
        assert False, "Deveria ter falhado na validação"
    except ValueError:
        print("OK: Validação de integridade confirmada.")

def test_serialization_roundtrip():
    """Valida to_dict e from_dict (preservação de dados)."""
    orig = AuditResult(ativo="ETHUSDT", quality=0.85, lista_de_bloqueadores=["ADX"])
    data = orig.to_dict()
    reconstructed = AuditResult.from_dict(data)
    
    assert orig == reconstructed
    assert reconstructed.quality == 0.85
    print("OK: Serialização Roundtrip confirmada.")

def test_performance():
    """Mede o tempo de criação, validação e serialização."""
    start = time.perf_counter()
    
    for _ in range(1000):
        res = AuditResult(ativo="SOLUSDT", quality=0.9, consensus=0.8)
        res.validate()
        data = res.to_dict()
        
    end = time.perf_counter()
    avg_time = (end - start) / 1000
    
    print(f"OK: Performance: {avg_time * 1000:.4f} ms por objeto.")

    assert avg_time < 0.001 # Deve ser extremamente rápido

def run_all_tests():
    try:
        test_audit_result_structure()
        test_validation_logic()
        test_serialization_roundtrip()
        test_performance()
        print("\n--- RELATÓRIO DE TESTES: SUCESSO ---")
        print("Total de testes: 4")
        print("Aprovados: 4")
        print("Reprovados: 0")
    except Exception as e:
        print(f"\n--- RELATÓRIO DE TESTES: FALHA ---")
        print(f"Erro: {e}")

if __name__ == "__main__":
    run_all_tests()
