def execute_order(strategy, action: str, client_order_id: str, exit_bar_close_ms: int | None):
    if strategy.venue == "arcus":
        from app.execution.arcus_remote import execute_arcus_remote

        return execute_arcus_remote(strategy, action, client_order_id)
    if strategy.venue in ("mexc_futures", "mexc_spot"):
        from app.execution.mexc_remote import execute_mexc_remote

        return execute_mexc_remote(strategy, action, client_order_id, exit_bar_close_ms)
    raise RuntimeError("venue has no order adapter")
