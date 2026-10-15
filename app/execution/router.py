from dataclasses import dataclass
from pathlib import Path

import yaml

from app.venues import asset_class_of, enabled_venues

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "strategies.yml"


class RegistryRejection(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Deployment:
    venue: str
    size_quote: float
    enabled: bool = True


@dataclass(frozen=True)
class Strategy:
    strategy_id: str
    symbol: str
    size_quote: float
    venue: str = "mexc_spot"
    side: str = ""
    deployments: tuple[Deployment, ...] = ()

    def __post_init__(self) -> None:
        deployments = self.deployments
        if not deployments:
            deployments = (Deployment(self.venue, float(self.size_quote), True),)
        object.__setattr__(self, "deployments", tuple(deployments))
        enabled = [item for item in self.deployments if item.enabled]
        primary = enabled[0] if enabled else self.deployments[0]
        object.__setattr__(self, "venue", primary.venue)
        object.__setattr__(self, "size_quote", float(primary.size_quote))
        if self.side == "":
            object.__setattr__(self, "side", _default_side(self.deployments))

    def bound(self, deployment: Deployment) -> "Strategy":
        return Strategy(
            self.strategy_id,
            self.symbol,
            deployment.size_quote,
            deployment.venue,
            self.side,
            (deployment,),
        )


def load_strategies(path: Path | None = None) -> dict[str, Strategy]:
    if path is None:
        path = REGISTRY_PATH
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RegistryRejection("strategy registry is invalid")
    strategies: dict[str, Strategy] = {}
    for strategy_id, raw in loaded.items():
        if not isinstance(strategy_id, str) or not isinstance(raw, dict):
            raise RegistryRejection("strategy registry is invalid")
        strategies[strategy_id] = _strategy(strategy_id, raw)
    _reject_mixed_directions(strategies)
    return strategies


def route(strategy_id: str, symbol: str) -> Strategy:
    strategy = load_strategies().get(strategy_id)
    if strategy is None:
        raise RegistryRejection("strategy_id is not registered")
    if symbol != strategy.symbol:
        raise RegistryRejection("symbol does not match")
    return strategy


def targets_for(strategy: Strategy, action: str) -> tuple[Deployment, ...]:
    return tuple(
        deployment
        for deployment in strategy.deployments
        if deployment.enabled and _accepts(strategy.side, deployment.venue, action)
    )


def rejection_reason(strategy: Strategy, action: str) -> str | None:
    if targets_for(strategy, action):
        return None
    enabled = [deployment for deployment in strategy.deployments if deployment.enabled]
    if not enabled:
        return "strategy has no enabled deployment"
    kinds = {asset_class_of(deployment.venue) for deployment in enabled}
    if action in ("SHORT", "COVER"):
        if kinds == {"spot"}:
            return f"{action} is not accepted for a spot strategy"
        if strategy.side == "long":
            return f"{action} is not accepted for a long strategy"
        return f"{action} is not accepted for this strategy"
    if action in ("BUY", "SELL", "STOP"):
        if "spot" not in kinds:
            return f"{action} is not accepted for a futures strategy"
        return f"{action} is not accepted for a short strategy"
    if action in ("LONG", "FLAT"):
        if strategy.side == "short":
            return f"{action} is not accepted for a short strategy"
        if "futures" not in kinds:
            return f"{action} is not accepted for a spot strategy"
    return f"{action} is not accepted for this strategy"


def _strategy(strategy_id: str, raw: dict) -> Strategy:
    symbol = raw.get("symbol")
    if not isinstance(symbol, str):
        raise RegistryRejection("strategy registry is invalid")
    if "side" not in raw:
        raise RegistryRejection("side is required")
    side = raw.get("side")
    if side not in ("long", "short"):
        raise RegistryRejection("strategy registry is invalid")
    if "deployments" in raw:
        if "size_quote" in raw or "venue" in raw:
            raise RegistryRejection("strategy registry is invalid")
        rows = raw.get("deployments")
        if not isinstance(rows, list) or not rows:
            raise RegistryRejection("strategy registry is invalid")
        deployments = tuple(_deployment(row) for row in rows)
        if len({item.venue for item in deployments}) != len(deployments):
            raise RegistryRejection("strategy registry is invalid")
    else:
        deployments = (_deployment(raw),)
    strategy = Strategy(strategy_id, symbol, deployments[0].size_quote, deployments[0].venue, side, deployments)
    if strategy.side == "short" and any(asset_class_of(item.venue) != "futures" for item in strategy.deployments):
        raise RegistryRejection("a short strategy cannot deploy to a spot venue")
    return strategy


def _deployment(raw: object) -> Deployment:
    if not isinstance(raw, dict):
        raise RegistryRejection("strategy registry is invalid")
    venue = raw.get("venue", "mexc_spot")
    size_quote = raw.get("size_quote")
    enabled = raw.get("enabled", True)
    if (
        not isinstance(venue, str)
        or venue not in enabled_venues()
        or isinstance(size_quote, bool)
        or not isinstance(size_quote, (int, float))
        or size_quote <= 0
        or not isinstance(enabled, bool)
    ):
        raise RegistryRejection("strategy registry is invalid")
    return Deployment(venue, float(size_quote), enabled)


def _default_side(deployments: tuple[Deployment, ...]) -> str:
    if deployments and all(asset_class_of(item.venue) == "futures" for item in deployments):
        return "short"
    return "long"


def _accepts(side: str, venue: str, action: str) -> bool:
    kind = asset_class_of(venue)
    if side == "short":
        return kind == "futures" and action in ("SHORT", "COVER")
    if side == "long" and kind == "spot":
        return action in ("BUY", "SELL", "STOP")
    if side == "long" and kind == "futures":
        return action in ("LONG", "FLAT")
    return False


def _reject_mixed_directions(strategies: dict[str, Strategy]) -> None:
    sides: dict[tuple[str, str], str] = {}
    for strategy in strategies.values():
        for deployment in strategy.deployments:
            key = (deployment.venue, strategy.symbol)
            previous = sides.get(key)
            if previous is not None and previous != strategy.side:
                raise RegistryRejection(f"{strategy.symbol} on {deployment.venue} cannot mix long and short")
            sides[key] = strategy.side
