"""Workflow : texte brut -> anonymisation locale -> LLM -> réidentification locale."""
from app.domain.models import Analysis
from app.domain.ports import Anonymizer, FleetRepository, LLMClient
from app.domain.rules import risk_level
from app.infrastructure.ai.llm import SYSTEM_PROMPT


class AnalyzeReport:
    def __init__(self, repo: FleetRepository, anonymizer: Anonymizer, llm: LLMClient):
        self.repo, self.anonymizer, self.llm = repo, anonymizer, llm

    def _context(self, asset_id: int) -> str:
        lines = []
        for r in self.repo.risk_ranking():
            if r.id == asset_id:
                lines.append(f"Indicateurs {r.plate} ({r.label}) : risque {r.risk_score}/100 "
                             f"({risk_level(r.risk_score)}), {r.failures_12m} pannes/12 mois, "
                             f"ratio de dérive des intervalles de panne {r.drift_ratio}.")
        for a in self.repo.supply_alerts():
            if a.asset_id == asset_id:
                lines.append(f"Pièce {a.part_ref} ({a.part_label}) due à {a.due_km} km, statut {a.status}, "
                             f"{a.days_left_to_order} j avant date limite de commande maritime.")
        return "\n".join(lines)

    def __call__(self, asset_id: int | None, text: str) -> Analysis:
        text = text.strip()
        if not text and asset_id:
            text = self.repo.latest_report(asset_id) or ""
        if not text:
            raise ValueError("Aucun compte-rendu à analyser.")
        raw = text + (f"\n\n{self._context(asset_id)}" if asset_id else "")
        anon = self.anonymizer.anonymize(raw)                       # 1. masquage local
        answer = self.llm.complete(SYSTEM_PROMPT, anon.text)        # 2. seul l'anonymisé sort
        return Analysis(raw, anon.text, SYSTEM_PROMPT, answer,      # 3. réidentification locale
                        self.anonymizer.restore(answer), anon.used, self.anonymizer.engine)
