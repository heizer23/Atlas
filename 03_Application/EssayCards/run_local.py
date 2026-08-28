"""
Run the EssayCards backend locally.
Loads secrets from 01_System/secrets.env, then starts uvicorn.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT         = Path(__file__).parent.parent.parent
SECRETS_ENV       = REPO_ROOT / "01_System" / "secrets.env"
PLATFORM_PACKAGES = REPO_ROOT / "02_Platform" / "packages"

# Make platform packages importable in subprocesses (mirrors Docker PYTHONPATH)
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
    if SECRETS_ENV.exists():
        load_env(SECRETS_ENV)
        print(f"Loaded secrets from {SECRETS_ENV}")
    else:
        print(f"Warning: {SECRETS_ENV} not found — relying on existing env vars")

    # Local runs always connect to localhost — override any Docker-targeted host
    os.environ["ATLAS_PG_HOST"] = "127.0.0.1"
    os.environ.pop("DATABASE_URL", None)   # DATABASE_URL takes priority in database.py; remove it for local runs

    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--port", "8024",
        ],
        cwd=Path(__file__).parent,
    )
