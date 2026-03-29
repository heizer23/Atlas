"""
Run CalendarConnector locally (no Docker required).
Loads secrets from 01_System/secrets.env and config from 01_System/config.env,
then starts uvicorn on CALENDAR_CONNECTOR_PORT (default 8021).
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT         = Path(__file__).parent.parent.parent
SECRETS_ENV       = REPO_ROOT / "01_System" / "secrets.env"
CONFIG_ENV        = REPO_ROOT / "01_System" / "config.env"
PLATFORM_PACKAGES = REPO_ROOT / "02_Platform" / "packages"

# Make platform packages importable (mirrors Docker PYTHONPATH)
existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = str(PLATFORM_PACKAGES) + (os.pathsep + existing if existing else "")


def load_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    if CONFIG_ENV.exists():
        load_env(CONFIG_ENV)
        print(f"Loaded config from {CONFIG_ENV}")

    if SECRETS_ENV.exists():
        load_env(SECRETS_ENV)
        print(f"Loaded secrets from {SECRETS_ENV}")
    else:
        print(f"Warning: {SECRETS_ENV} not found — relying on existing env vars")

    # Local runs always connect to localhost
    os.environ["ATLAS_PG_HOST"] = "127.0.0.1"
    os.environ.pop("DATABASE_URL", None)

    port = os.environ.get("CALENDAR_CONNECTOR_PORT", "8021")

    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--port", port,
            "--host", "127.0.0.1",
        ],
        cwd=Path(__file__).parent,
    )
