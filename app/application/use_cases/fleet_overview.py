from app.domain.models import RiskRow, SupplyAlert
from app.domain.ports import FleetRepository


class FleetOverview:
    def __init__(self, repo: FleetRepository):
        self.repo = repo

    def __call__(self) -> tuple[list[RiskRow], list[SupplyAlert]]:
        return self.repo.risk_ranking(), self.repo.supply_alerts()
