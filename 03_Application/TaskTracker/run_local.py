"""
Run the TaskTracker backend locally.
Loads secrets from 01_System/secrets.env, then starts uvicorn.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT         = Path(__file__).parent.parent.parent
SECRETS_ENV       = REPO_ROOT / "01_System" / "secrets.env"
PLATFORM_PACKAGES = REPO_ROOT / "02_Platform" / "03_ErrorHandling" / "packages"

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

    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--reload",
            "--port", "8001",
        ],
        cwd=Path(__file__).parent,
    )
