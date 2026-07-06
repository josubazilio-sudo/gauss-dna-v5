from datetime import datetime, timezone


class ReportGenerator:
    def generate(self, audit_id: str, scope: str, results: dict) -> str:
        lines = [
            "=== Relatorio de Auditoria ===",
            f"ID: {audit_id}",
            f"Data: {datetime.now(timezone.utc).isoformat()}",
            f"Escopo: {scope}",
            f"Resultado: {results['status']}",
        ]
        if results.get("violations"):
            lines.append(f"Nao conformidades ({len(results['violations'])}):")
            for v in results["violations"]:
                lines.append(f"  - {v}")
        return "\n".join(lines)
