"""Provider selection boundary.

Only simulation is intentionally available in v11. Real providers must be
introduced through this registry after credentials, compliance controls,
webhook verification, and provider-specific tests exist.
"""
from services.providers.base import ProviderUnavailable
from services.providers.simulation import SimulationProvider


def provider_for(*, action_type: str, mode: str):
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode == "simulation":
        return SimulationProvider()
    raise ProviderUnavailable(
        f"No live provider is configured for {action_type}. Live execution remains locked."
    )
