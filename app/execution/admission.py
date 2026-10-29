from app.core.config import kill_switch_enabled
from app.execution.router import Strategy, rejection_reason


def order_block_reason(strategy: Strategy, action: str) -> str | None:
    """One admission rule for the webhook and the order API.

    Direction comes from the strategy registry. The kill switch is the stop
    that still applies after a valid action. dry_run stays on the webhook:
    the virtual machine is the live executor.
    """
    mismatch = rejection_reason(strategy, action)
    if mismatch is not None:
        return mismatch
    if kill_switch_enabled():
        return "KILL_SWITCH"
    return None
