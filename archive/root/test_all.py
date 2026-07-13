import pytest
import sys
from pathlib import Path

# Adiciona o root do projeto ao sys.path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

def run_all_tests():
    # Executa todos os testes na pasta TESTS com cobertura
    args = [
        "TESTS/",
        "-v",
        "--cov=ENGINE",
        "--cov-report=term-missing",
        "--cov-fail-under=95"
    ]
    
    print(f"Iniciando bateria de testes em: {root}")
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print("\n[SUCESSO] Todos os testes passaram e cobertura atingida.")
    else:
        print(f"\n[FALHA] Testes retornaram código: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    run_all_tests()
