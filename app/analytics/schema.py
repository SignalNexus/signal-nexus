from datetime import datetime
from decimal import Decimal

# 画面の種類は受信、拒否、見送り、成功、失敗、再送の破棄。
# 保存する kind は発注側が既に送っている監査名。見送りは 2 種類ある。
# order_planned は発注直前の監査で、6 種類の画面には出さない。
AUDIT_KIND_LABELS = {
    "signal_received": "受信",
    "validation_rejected": "拒否",
    "order_not_sent": "見送り",
    "sell_resend_skipped": "見送り",
    "order_success": "成功",
    "order_failed": "失敗",
    "duplicate_discarded": "再送の破棄",
}
AUDIT_KINDS = (*AUDIT_KIND_LABELS, "order_planned")

_KIND_LIST = ", ".join(f"'{kind}'" for kind in AUDIT_KINDS)

STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS fills (
        trade_id text PRIMARY KEY,
        symbol text NOT NULL,
        side text NOT NULL CHECK (side IN ('buy', 'sell')),
        quantity numeric NOT NULL,
        quote_spent numeric NOT NULL,
        quote_received numeric NOT NULL,
        fee numeric NOT NULL,
        fee_asset text,
        filled_at timestamptz NOT NULL,
        fill_price numeric NOT NULL,
        exchange_order_id text NOT NULL,
        exchange_client_order_id text,
        strategy_name text NOT NULL,
        market text NOT NULL CHECK (market = 'spot'),
        signal_time timestamptz,
        signal_price numeric,
        client_order_id text
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS audits (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        recorded_at timestamptz NOT NULL,
        kind text NOT NULL CHECK (kind IN ({_KIND_LIST})),
        strategy text NOT NULL,
        symbol text NOT NULL,
        reason text NOT NULL
    )
    """,
    """
    ALTER TABLE audits ADD COLUMN IF NOT EXISTS discord_status text NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE audits ADD COLUMN IF NOT EXISTS discord_detail text NOT NULL DEFAULT ''
    """,
    """
    CREATE TABLE IF NOT EXISTS order_links (
        exchange_client_order_id text PRIMARY KEY CHECK (char_length(exchange_client_order_id) = 32),
        client_order_id text NOT NULL CHECK (char_length(client_order_id) > 0),
        signal_time timestamptz,
        signal_price numeric
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingest_status (
        id boolean PRIMARY KEY DEFAULT TRUE CHECK (id),
        succeeded_at timestamptz NOT NULL
    )
    """,
    """
    ALTER TABLE fills ADD COLUMN IF NOT EXISTS fee_asset text
    """,
    """
    ALTER TABLE fills DROP CONSTRAINT IF EXISTS fills_market_check
    """,
    """
    ALTER TABLE fills ADD CONSTRAINT fills_market_check CHECK (market IN ('spot', 'swap'))
    """,
    """
    ALTER TABLE fills ADD COLUMN IF NOT EXISTS venue text NOT NULL DEFAULT 'mexc_spot'
    """,
    """
    ALTER TABLE fills DROP CONSTRAINT IF EXISTS fills_venue_check
    """,
    """
    CREATE TABLE IF NOT EXISTS arcus_lots (
        strategy_id text PRIMARY KEY CHECK (char_length(strategy_id) > 0),
        quantity numeric NOT NULL CHECK (quantity > 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_lots (
        venue text NOT NULL CHECK (char_length(venue) > 0),
        strategy_id text NOT NULL CHECK (char_length(strategy_id) > 0),
        quantity numeric NOT NULL CHECK (quantity > 0),
        PRIMARY KEY (venue, strategy_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_spot_meta (
        strategy_id text PRIMARY KEY CHECK (char_length(strategy_id) > 0),
        symbol text NOT NULL CHECK (char_length(symbol) > 0),
        bought_at_ms bigint NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_sold_exits (
        strategy_id text PRIMARY KEY CHECK (char_length(strategy_id) > 0),
        exit_bar_close_ms bigint NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_lot_applied (
        venue text NOT NULL CHECK (char_length(venue) > 0),
        order_key text NOT NULL CHECK (char_length(order_key) > 0),
        filled numeric NOT NULL CHECK (filled >= 0),
        PRIMARY KEY (venue, order_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_lot_sync (
        venue text PRIMARY KEY CHECK (char_length(venue) > 0),
        synced_at timestamptz NOT NULL
    )
    """,
)


def create_schema(connection) -> None:
    for statement in STATEMENTS:
        connection.execute(statement)
    if connection.execute("SELECT to_regclass('public.arcus_lots')").fetchone()[0] is not None:
        connection.execute(
            """
            INSERT INTO strategy_lots (venue, strategy_id, quantity)
            SELECT 'arcus', strategy_id, quantity FROM arcus_lots
            ON CONFLICT (venue, strategy_id) DO NOTHING
            """
        )


def record_ingest_success(connection, succeeded_at: datetime) -> None:
    connection.execute(
        """
        INSERT INTO ingest_status (id, succeeded_at)
        VALUES (TRUE, %(succeeded_at)s)
        ON CONFLICT (id) DO UPDATE SET succeeded_at = EXCLUDED.succeeded_at
        """,
        {"succeeded_at": succeeded_at},
    )


def load_ingest_succeeded_at(connection) -> datetime | None:
    row = connection.execute("SELECT succeeded_at FROM ingest_status").fetchone()
    if row is None:
        return None
    return row[0]


def insert_fill(
    connection,
    *,
    trade_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    quote_spent: Decimal,
    quote_received: Decimal,
    fee: Decimal,
    filled_at: datetime,
    fill_price: Decimal,
    exchange_order_id: str,
    strategy_name: str,
    fee_asset: str | None = None,
    market: str = "spot",
    exchange_client_order_id: str | None = None,
    signal_time: datetime | None = None,
    signal_price: Decimal | None = None,
    client_order_id: str | None = None,
    venue: str = "mexc_spot",
    ignore_conflict: bool = False,
) -> bool:
    statement = """
        INSERT INTO fills (
            trade_id,
            symbol,
            side,
            quantity,
            quote_spent,
            quote_received,
            fee,
            fee_asset,
            filled_at,
            fill_price,
            exchange_order_id,
            exchange_client_order_id,
            strategy_name,
            market,
            signal_time,
            signal_price,
            client_order_id,
            venue
        )
        VALUES (
            %(trade_id)s,
            %(symbol)s,
            %(side)s,
            %(quantity)s,
            %(quote_spent)s,
            %(quote_received)s,
            %(fee)s,
            %(fee_asset)s,
            %(filled_at)s,
            %(fill_price)s,
            %(exchange_order_id)s,
            %(exchange_client_order_id)s,
            %(strategy_name)s,
            %(market)s,
            %(signal_time)s,
            %(signal_price)s,
            %(client_order_id)s,
            %(venue)s
        )
        """
    if ignore_conflict:
        statement += " ON CONFLICT (trade_id) DO NOTHING"
    inserted = connection.execute(
        statement,
        {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "quote_spent": quote_spent,
            "quote_received": quote_received,
            "fee": fee,
            "fee_asset": fee_asset,
            "filled_at": filled_at,
            "fill_price": fill_price,
            "exchange_order_id": exchange_order_id,
            "exchange_client_order_id": exchange_client_order_id,
            "strategy_name": strategy_name,
            "market": market,
            "signal_time": signal_time,
            "signal_price": signal_price,
            "client_order_id": client_order_id,
            "venue": venue,
        },
    )
    if ignore_conflict and fee_asset:
        connection.execute(
            """
            UPDATE fills
            SET fee_asset = %(fee_asset)s
            WHERE trade_id = %(trade_id)s
              AND fee_asset IS NULL
            """,
            {"trade_id": trade_id, "fee_asset": fee_asset},
        )
    return inserted.rowcount == 1


def insert_audit(
    connection,
    *,
    kind: str,
    strategy: str,
    symbol: str,
    reason: str,
    recorded_at: datetime,
    discord_status: str = "",
    discord_detail: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO audits (
            recorded_at, kind, strategy, symbol, reason, discord_status, discord_detail
        )
        VALUES (
            %(recorded_at)s, %(kind)s, %(strategy)s, %(symbol)s, %(reason)s,
            %(discord_status)s, %(discord_detail)s
        )
        """,
        {
            "recorded_at": recorded_at,
            "kind": kind,
            "strategy": strategy,
            "symbol": symbol,
            "reason": reason,
            "discord_status": discord_status,
            "discord_detail": discord_detail,
        },
    )


def link_order(
    connection,
    *,
    exchange_client_order_id: str,
    client_order_id: str,
    signal_time: datetime | None = None,
    signal_price: Decimal | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO order_links (
            exchange_client_order_id,
            client_order_id,
            signal_time,
            signal_price
        )
        VALUES (
            %(exchange_client_order_id)s,
            %(client_order_id)s,
            %(signal_time)s,
            %(signal_price)s
        )
        ON CONFLICT (exchange_client_order_id) DO UPDATE
        SET client_order_id = EXCLUDED.client_order_id,
            signal_time = COALESCE(EXCLUDED.signal_time, order_links.signal_time),
            signal_price = COALESCE(EXCLUDED.signal_price, order_links.signal_price)
        """,
        {
            "exchange_client_order_id": exchange_client_order_id,
            "client_order_id": client_order_id,
            "signal_time": signal_time,
            "signal_price": signal_price,
        },
    )
    connection.execute(
        """
        UPDATE fills
        SET client_order_id = %(client_order_id)s,
            signal_time = COALESCE(%(signal_time)s, signal_time),
            signal_price = COALESCE(%(signal_price)s, signal_price)
        WHERE exchange_client_order_id = %(exchange_client_order_id)s
        """,
        {
            "exchange_client_order_id": exchange_client_order_id,
            "client_order_id": client_order_id,
            "signal_time": signal_time,
            "signal_price": signal_price,
        },
    )


def load_order_links(connection) -> dict[str, tuple[str, datetime | None, Decimal | None]]:
    rows = connection.execute(
        """
        SELECT exchange_client_order_id, client_order_id, signal_time, signal_price
        FROM order_links
        """
    ).fetchall()
    return {row[0]: (row[1], row[2], row[3]) for row in rows}


def load_fills(connection) -> list[tuple]:
    return connection.execute(
        """
        SELECT
            trade_id,
            symbol,
            side,
            quantity,
            quote_spent,
            quote_received,
            fee,
            filled_at,
            strategy_name,
            client_order_id,
            fill_price,
            fee_asset,
            venue,
            exchange_client_order_id
        FROM fills
        ORDER BY filled_at, trade_id
        """
    ).fetchall()


def load_audits(connection) -> list[tuple]:
    return connection.execute(
        """
        SELECT recorded_at, kind, strategy, symbol, reason, discord_status, discord_detail
        FROM audits
        ORDER BY recorded_at, id
        """
    ).fetchall()


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def load_strategy_lots(connection, venue: str) -> dict[str, Decimal]:
    rows = connection.execute(
        "SELECT strategy_id, quantity FROM strategy_lots WHERE venue = %(venue)s",
        {"venue": venue},
    ).fetchall()
    return {row[0]: _decimal(row[1]) for row in rows}


def save_strategy_lot(connection, venue: str, strategy_id: str, quantity: Decimal) -> None:
    if quantity <= 0:
        connection.execute(
            "DELETE FROM strategy_lots WHERE venue = %(venue)s AND strategy_id = %(strategy_id)s",
            {"venue": venue, "strategy_id": strategy_id},
        )
        return
    connection.execute(
        """
        INSERT INTO strategy_lots (venue, strategy_id, quantity)
        VALUES (%(venue)s, %(strategy_id)s, %(quantity)s)
        ON CONFLICT (venue, strategy_id) DO UPDATE SET quantity = EXCLUDED.quantity
        """,
        {"venue": venue, "strategy_id": strategy_id, "quantity": quantity},
    )


def load_applied_fill(connection, venue: str, order_key: str) -> Decimal:
    row = connection.execute(
        """
        SELECT filled FROM strategy_lot_applied
        WHERE venue = %(venue)s AND order_key = %(order_key)s
        """,
        {"venue": venue, "order_key": order_key},
    ).fetchone()
    if row is None:
        return Decimal("0")
    return _decimal(row[0])


def save_applied_fill(connection, venue: str, order_key: str, filled: Decimal) -> None:
    connection.execute(
        """
        INSERT INTO strategy_lot_applied (venue, order_key, filled)
        VALUES (%(venue)s, %(order_key)s, %(filled)s)
        ON CONFLICT (venue, order_key) DO UPDATE SET filled = EXCLUDED.filled
        """,
        {"venue": venue, "order_key": order_key, "filled": filled},
    )


def load_spot_meta(connection) -> dict[str, tuple[str, int]]:
    rows = connection.execute("SELECT strategy_id, symbol, bought_at_ms FROM strategy_spot_meta").fetchall()
    return {row[0]: (row[1], int(row[2])) for row in rows}


def save_spot_meta(connection, strategy_id: str, symbol: str, bought_at_ms: int) -> None:
    connection.execute(
        """
        INSERT INTO strategy_spot_meta (strategy_id, symbol, bought_at_ms)
        VALUES (%(strategy_id)s, %(symbol)s, %(bought_at_ms)s)
        ON CONFLICT (strategy_id) DO UPDATE
        SET symbol = EXCLUDED.symbol, bought_at_ms = EXCLUDED.bought_at_ms
        """,
        {"strategy_id": strategy_id, "symbol": symbol, "bought_at_ms": bought_at_ms},
    )


def delete_spot_meta(connection, strategy_id: str) -> None:
    connection.execute(
        "DELETE FROM strategy_spot_meta WHERE strategy_id = %(strategy_id)s",
        {"strategy_id": strategy_id},
    )


def load_sold_exits(connection) -> dict[str, int]:
    rows = connection.execute("SELECT strategy_id, exit_bar_close_ms FROM strategy_sold_exits").fetchall()
    return {row[0]: int(row[1]) for row in rows}


def save_sold_exit(connection, strategy_id: str, exit_bar_close_ms: int) -> None:
    connection.execute(
        """
        INSERT INTO strategy_sold_exits (strategy_id, exit_bar_close_ms)
        VALUES (%(strategy_id)s, %(exit_bar_close_ms)s)
        ON CONFLICT (strategy_id) DO UPDATE SET exit_bar_close_ms = EXCLUDED.exit_bar_close_ms
        """,
        {"strategy_id": strategy_id, "exit_bar_close_ms": exit_bar_close_ms},
    )


def venue_was_synced(connection, venue: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM strategy_lot_sync WHERE venue = %(venue)s",
        {"venue": venue},
    ).fetchone()
    return row is not None


def mark_venue_synced(connection, venue: str, synced_at: datetime) -> None:
    connection.execute(
        """
        INSERT INTO strategy_lot_sync (venue, synced_at)
        VALUES (%(venue)s, %(synced_at)s)
        ON CONFLICT (venue) DO UPDATE SET synced_at = EXCLUDED.synced_at
        """,
        {"venue": venue, "synced_at": synced_at},
    )


def load_arcus_lots(connection) -> dict[str, Decimal]:
    return load_strategy_lots(connection, "arcus")


def save_arcus_lot(connection, strategy_id: str, quantity: Decimal) -> None:
    save_strategy_lot(connection, "arcus", strategy_id, quantity)


def trade_id_constraint_types(connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT c.contype
        FROM pg_catalog.pg_constraint AS c
        JOIN pg_catalog.pg_class AS rel ON rel.oid = c.conrelid
        JOIN pg_catalog.pg_namespace AS nsp ON nsp.oid = rel.relnamespace
        JOIN pg_catalog.pg_attribute AS att
          ON att.attrelid = rel.oid
         AND att.attnum = ANY (c.conkey)
        WHERE nsp.nspname = current_schema()
          AND rel.relname = 'fills'
          AND att.attname = 'trade_id'
          AND c.contype IN ('p', 'u')
        """
    ).fetchall()
    return {row[0] for row in rows}
