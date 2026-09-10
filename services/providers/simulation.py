"""Side-effect-free provider used by local development and release verification."""
from services.providers.base import ProviderAdapter, ProviderResult


class SimulationProvider(ProviderAdapter):
    name = "Simulation"

    def execute(self, *, action, payload) -> ProviderResult:
        external_id = f"sim_action_{action['id']}"
        return ProviderResult(
            outcome="CONFIRMED",
            external_id=external_id,
            detail=(
                "Simulation provider confirmed the action. No external system "
                "was contacted and no customer-facing side effect occurred."
            ),
        )
