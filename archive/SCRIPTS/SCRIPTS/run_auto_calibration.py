import os
import sys

# Permitir imports da raiz do QuantOS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ENGINE.scanner.auto_calibration import AutoCalibrationEngine

def main():
    print("Iniciando calibração automática de pesos (QuantOS V7.0)...")
    calibrator = AutoCalibrationEngine()
    
    # Rodar no modo simulação para gerar os pesos v7 calibrados
    report = calibrator.calibrate(force_mock=True)
    
    print("\n[SUCESSO] Processo de Calibração Concluído!")
    print("\nRelatório Gerado:\n")
    print(report)

if __name__ == "__main__":
    main()
