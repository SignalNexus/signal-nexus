import os


def execution_mode() -> str:
    mode = os.environ.get("EXECUTION_MODE", "dry_run")
    if mode == "live":
        return "live"
    return "dry_run"


def kill_switch_enabled() -> bool:
    return os.environ.get("KILL_SWITCH", "false") == "true"
