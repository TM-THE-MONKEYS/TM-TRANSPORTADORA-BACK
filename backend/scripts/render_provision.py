"""Provision tm-transportadora-api on Render via REST API.

Requires RENDER_API_KEY in environment. Never commit secrets.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.render.com/v1"
REPO = "https://github.com/TM-THE-MONKEYS/TM-TRANSPORTADORA-BACK"


def _load_local_env() -> None:
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env.render")
    if not os.path.isfile(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _request(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get("RENDER_API_KEY", "").strip()
    if not token:
        print("RENDER_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    _load_local_env()
    owners = _request("GET", "/owners")
    if not owners:
        print("No Render owners found", file=sys.stderr)
        sys.exit(1)
    owner_id = owners[0]["owner"]["id"]
    print(f"owner_id={owner_id}")

    existing = _request("GET", f"/services?ownerId={owner_id}&name=tm-transportadora-api")
    for item in existing:
        svc = item.get("service", item)
        if svc.get("name") == "tm-transportadora-api":
            print(f"service_exists id={svc['id']} url={svc.get('serviceDetails', {}).get('url', 'pending')}")
            print(json.dumps(svc, indent=2))
            return

    secret_key = os.environ.get("SECRET_KEY", "").strip()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    database_url_sync = os.environ.get("DATABASE_URL_SYNC", "").strip()
    supabase_anon = os.environ.get("SUPABASE_ANON_KEY", "").strip()

    if not all([secret_key, database_url, supabase_anon]):
        print("Set SECRET_KEY, DATABASE_URL, DATABASE_URL_SYNC, SUPABASE_ANON_KEY in env", file=sys.stderr)
        sys.exit(1)

    env_vars = [
        {"key": "APP_ENV", "value": "production"},
        {"key": "APP_DEBUG", "value": "false"},
        {"key": "WEB_CONCURRENCY", "value": "1"},
        {"key": "ALLOW_TENANT_REGISTRATION", "value": "false"},
        {"key": "LOG_LEVEL", "value": "INFO"},
        {"key": "LOG_FORMAT", "value": "json"},
        {"key": "RATE_LIMIT_PER_MINUTE", "value": "60"},
        {"key": "RATE_LIMIT_AUTH_PER_MINUTE", "value": "10"},
        {"key": "REDIS_URL", "value": "redis://127.0.0.1:6379/0"},
        {"key": "CELERY_BROKER_URL", "value": "redis://127.0.0.1:6379/0"},
        {"key": "CELERY_RESULT_BACKEND", "value": "redis://127.0.0.1:6379/1"},
        {"key": "SUPABASE_URL", "value": "https://jkdkspbcqnfrweanmhpp.supabase.co"},
        {
            "key": "CORS_ORIGINS",
            "value": '["https://tm-transportadora.vercel.app","https://tm-transportadora-julinhohgrs-projects.vercel.app"]',
        },
        {"key": "SECRET_KEY", "value": secret_key},
        {"key": "DATABASE_URL", "value": database_url},
        {"key": "DATABASE_URL_SYNC", "value": database_url_sync or database_url},
        {"key": "SUPABASE_ANON_KEY", "value": supabase_anon},
    ]

    payload = {
        "type": "web_service",
        "name": "tm-transportadora-api",
        "ownerId": owner_id,
        "repo": REPO,
        "branch": "main",
        "autoDeploy": "yes",
        "rootDir": "backend",
        "serviceDetails": {
            "runtime": "docker",
            "plan": "free",
            "region": "virginia",
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "dockerfilePath": "./docker/Dockerfile",
                "dockerContext": ".",
            },
        },
        "envVars": env_vars,
    }

    result = _request("POST", "/services", payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
