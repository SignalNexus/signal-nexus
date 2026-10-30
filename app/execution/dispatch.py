def execute_order(strategy, action: str, client_order_id: str, exit_bar_close_ms: int | None):
    from app.execution.venue_port import RESERVED_VENUE_IDS
    from app.execution.venue_remote import execute_venue_remote, hands_off

    if hands_off() and strategy.venue not in RESERVED_VENUE_IDS:
        return execute_venue_remote(strategy, action, client_order_id)
    if strategy.venue == "arcus":
        from app.execution.arcus_remote import execute_arcus_remote

        return execute_arcus_remote(strategy, action, client_order_id)
    if strategy.venue in ("mexc_futures", "mexc_spot"):
        from app.execution.mexc_remote import execute_mexc_remote

        return execute_mexc_remote(strategy, action, client_order_id, exit_bar_close_ms)
    from app.execution.venue_port import port_for

    port = port_for(strategy.venue)
    if port is None:
        raise RuntimeError("venue has no order adapter")
    return port.execute(strategy, action, client_order_id)
