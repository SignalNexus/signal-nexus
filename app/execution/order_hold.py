"""One in-flight order per client id, and one close per strategy on a venue.

The caller asks the virtual machine before a second send. A working row blocks
that send. A retry row is the same close, continued with the same client id.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

_CLOSING = ("COVER", "FLAT", "SELL", "STOP")
WORKING_FOR = timedelta(minutes=5)
RETRY_FOR = timedelta(minutes=5)


def claim(venue: str, strategy_id: str, action: str, client_order_id: str) -> str:
    from app.execution.strategy_lots import configured, connect

    if not client_order_id or not configured():
        return "start"
    try:
        with connect() as connection:
            from app.analytics.schema import create_schema

            create_schema(connection)
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS order_hold_one_close
                ON order_hold (venue, strategy_id)
                WHERE action IN ('COVER', 'FLAT', 'SELL', 'STOP')
                """
            )
            connection.commit()
            with connection.transaction():
                _drop_stale(connection)
                if action in _CLOSING and _other_close(connection, venue, strategy_id, client_order_id):
                    return "held"
                current = connection.execute(
                    """
                    SELECT state FROM order_hold
                    WHERE venue = %s AND client_order_id = %s
                    FOR UPDATE
                    """,
                    (venue, client_order_id),
                ).fetchone()
                if current is None:
                    connection.execute(
                        """
                        INSERT INTO order_hold (
                            venue, client_order_id, strategy_id, action, state, updated_at
                        ) VALUES (%s, %s, %s, %s, 'working', now())
                        """,
                        (venue, client_order_id, strategy_id, action),
                    )
                    return "start"
                if current[0] == "working":
                    return "held"
                updated = connection.execute(
                    """
                    UPDATE order_hold
                    SET strategy_id = %s, action = %s, state = 'working', updated_at = now()
                    WHERE venue = %s AND client_order_id = %s AND state = 'retry'
                    """,
                    (strategy_id, action, venue, client_order_id),
                )
                return "start" if updated.rowcount == 1 else "held"
    except Exception:
        logger.warning("order hold was not recorded")
        return "start"


def finish(venue: str, client_order_id: str, result) -> None:
    from app.execution.close_retry import unfinished_close
    from app.execution.strategy_lots import configured, connect

    if not client_order_id or not configured():
        return
    try:
        with connect() as connection:
            row = connection.execute(
                "SELECT action FROM order_hold WHERE venue = %s AND client_order_id = %s",
                (venue, client_order_id),
            ).fetchone()
            action = "" if row is None else row[0]
            keep = unfinished_close(action, result.status, result.sent, result.reason or "", 1)
            if keep:
                connection.execute(
                    """
                    UPDATE order_hold
                    SET state = 'retry', updated_at = now()
                    WHERE venue = %s AND client_order_id = %s
                    """,
                    (venue, client_order_id),
                )
            else:
                connection.execute(
                    "DELETE FROM order_hold WHERE venue = %s AND client_order_id = %s",
                    (venue, client_order_id),
                )
            connection.commit()
    except Exception:
        logger.warning("order hold was not finished")


def _drop_stale(connection) -> None:
    connection.execute(
        """
        DELETE FROM order_hold
        WHERE (state = 'working' AND updated_at < now() - %s)
           OR (state = 'retry' AND updated_at < now() - %s)
        """,
        (WORKING_FOR, RETRY_FOR),
    )


def _other_close(connection, venue: str, strategy_id: str, client_order_id: str) -> bool:
    row = connection.execute(
        """
        SELECT client_order_id FROM order_hold
        WHERE venue = %s AND strategy_id = %s AND action = ANY(%s)
        FOR UPDATE
        """,
        (venue, strategy_id, list(_CLOSING)),
    ).fetchone()
    return row is not None and row[0] != client_order_id
