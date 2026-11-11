"""Borhan multi-bot WSGI entry point.

Loads the four original Flask apps under /filter, /fit, /nima and /shop.
Configuration can come from Render Secret File /etc/secrets/bots-config.json,
prefixed host environment variables, or each app's local .env file.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from flask import Flask, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
APPS = ROOT / "apps"
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("borhan.gateway")

# Render Secret Files are mounted at /etc/secrets/<filename>.
# BOTS_CONFIG_PATH can override the path for other hosting providers/local tests.
def _load_bot_config() -> tuple[dict, str | None, str | None]:
    candidates: list[Path] = []
    configured_path = os.getenv("BOTS_CONFIG_PATH", "").strip()
    if configured_path:
        candidates.append(Path(configured_path).expanduser())
    candidates.extend([
        Path("/etc/secrets/bots-config.json"),
        ROOT / "bots-config.json",  # local testing only; keep this file out of GitHub
    ])

    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("top-level JSON value must be an object")
            log.info("Loaded bot configuration file: %s", path.name)
            return data, str(path), None
        except Exception as exc:
            message = f"Could not read {path.name}: {type(exc).__name__}: {exc}"
            log.exception("%s", message)
            return {}, str(path), message

    log.warning("bots-config.json was not found; using prefixed environment variables and apps/*/.env")
    return {}, None, "bots-config.json not found"


BOT_CONFIG, BOT_CONFIG_PATH, BOT_CONFIG_ERROR = _load_bot_config()

# Environment keys consumed by the original projects.
PROJECT_KEYS = {
    "filter": ["BOT_TOKEN", "OWNER_ID", "DATABASE_URL", "WEBHOOK_SECRET", "WEBHOOK_URL"],
    "fit": ["BOT_TOKEN", "OWNER_ID", "WEBHOOK_SECRET", "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY", "PUBLIC_BASE_URL", "SETUP_KEY",
            "COACH_USERNAME", "UPDATE_WORKERS", "AUTO_SET_WEBHOOK", "LOG_LEVEL"],
    "nima": ["BOT_TOKEN", "OWNER_ID", "SUPABASE_URL", "SUPABASE_KEY", "WEBHOOK_URL"],
    "shop": ["BOT_TOKEN", "SUPABASE_URL", "SUPABASE_KEY", "BASE_URL",
             "WEBHOOK_SECRET", "ADMIN_PASSWORD", "ADMIN_IDS", "SHOP_TITLE_FA",
             "SHOP_TITLE_EN", "SUPPORT_USERNAME", "REQUIRED_CHANNEL_ID",
             "REQUIRED_CHANNEL_USERNAME", "CARD_NUMBER", "CARD_HOLDER",
             "ZARINPAL_MERCHANT_ID", "ZARINPAL_CALLBACK_URL", "CURRENCY",
             "STAR_TO_RIAL", "REVIEW_LIMIT", "REPORT_LIMIT",
             "REVIEW_REQUIRES_PURCHASE", "MAX_CART_QTY", "STATE_TTL_MIN",
             "TRIAL_DAYS", "SESSION_SECRET", "BOT_HANDLER_THREADS"],
}

PREFIXES = {"filter": "/filter", "fit": "/fit", "nima": "/nima", "shop": "/shop"}
WEBHOOK_BASE_KEYS = {
    "filter": "WEBHOOK_URL",
    "fit": "PUBLIC_BASE_URL",
    "nima": "WEBHOOK_URL",
    "shop": "BASE_URL",
}


def _as_env_string(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        raise ValueError("environment setting values must be strings or numbers, not objects/lists")
    return str(value).strip()


def _read_project_env(project: str) -> dict[str, str]:
    folder = APPS / project
    raw = dotenv_values(folder / ".env")
    json_values = BOT_CONFIG.get(project, {})
    if not isinstance(json_values, dict):
        raise ValueError(f"bots-config.json section '{project}' must be a JSON object")

    values: dict[str, str] = {}
    for key in PROJECT_KEYS[project]:
        # Priority: host prefixed environment variable > Secret File JSON > app-local .env.
        host_value = os.getenv(f"{project.upper()}_{key}")
        json_value = json_values.get(key)
        dotenv_value = raw.get(key)

        if host_value is not None and host_value.strip() != "":
            value = host_value
        elif key in json_values:
            value = _as_env_string(json_value)
        else:
            value = _as_env_string(dotenv_value)

        if value is not None:
            values[key] = value

    # All bots share the same Render hostname but each has its own URL prefix.
    json_root_url = BOT_CONFIG.get("APP_BASE_URL", "")
    root_url = (os.getenv("APP_BASE_URL") or _as_env_string(json_root_url) or
                os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    if root_url:
        values[WEBHOOK_BASE_KEYS[project]] = root_url + PREFIXES[project]
        # Some original apps fall back to RENDER_EXTERNAL_URL.
        values["RENDER_EXTERNAL_URL"] = root_url + PREFIXES[project]
    return values


@contextmanager
def _project_environment(project: str):
    previous = os.environ.copy()
    try:
        # Remove same-named keys from other projects before injecting this project's values.
        for keys in PROJECT_KEYS.values():
            for key in keys:
                os.environ.pop(key, None)
        for key, value in _read_project_env(project).items():
            os.environ[key] = value
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _import_flask_app(project: str, filename: str, module_name: str):
    project_dir = str(APPS / project)
    sys.path.insert(0, project_dir)
    try:
        spec = importlib.util.spec_from_file_location(module_name, APPS / project / filename)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load {project}/{filename}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        flask_app = getattr(module, "app", None)
        if flask_app is None:
            raise RuntimeError(f"{project} has no Flask app object")
        return module, flask_app
    finally:
        try:
            sys.path.remove(project_dir)
        except ValueError:
            pass


def _unavailable_app(project: str, error: Exception):
    fallback = Flask(f"{project}_unavailable")
    message = f"{project} is not configured or failed to start. Check Secret File bots-config.json, prefixed variables, or apps/{project}/.env."
    log.exception("Project %s failed to load", project, exc_info=error)

    @fallback.route("/", defaults={"path": ""})
    @fallback.route("/<path:path>")
    def unavailable(path):
        return jsonify({"ok": False, "project": project, "error": message}), 503

    return fallback


loaded: dict[str, object] = {}
project_modules: dict[str, object] = {}
project_errors: dict[str, str] = {}

# Shop imports generic modules named bot/config/services/db. Load it first.
LOAD_ORDER = [
    ("shop", "app.py", "borhan_shop_app"),
    ("fit", "app.py", "borhan_fit_app"),
    ("nima", "app.py", "borhan_nima_app"),
    ("filter", "bot.py", "borhan_filter_bot"),
]

for project, filename, module_name in LOAD_ORDER:
    try:
        with _project_environment(project):
            module, flask_app = _import_flask_app(project, filename, module_name)
        project_modules[project] = module
        loaded[project] = flask_app
        log.info("Loaded %s at %s", project, PREFIXES[project])
    except Exception as exc:
        project_errors[project] = f"{type(exc).__name__}: {exc}"
        loaded[project] = _unavailable_app(project, exc)

# Filter's original __main__ block performed these actions.
if "filter" in project_modules:
    try:
        with _project_environment("filter"):
            filter_module = project_modules["filter"]
            filter_module.init_database()
            filter_module.ensure_default_plan()
            if not getattr(filter_module, "_gateway_subscription_checker_started", False):
                threading.Thread(target=filter_module.subscription_checker,
                                 name="filter-subscription-checker", daemon=True).start()
                filter_module._gateway_subscription_checker_started = True
            filter_module.setup_telegram_webhook()
        log.info("Filter bot database initialized and webhook setup attempted")
    except Exception as exc:
        project_errors["filter"] = f"startup {type(exc).__name__}: {exc}"
        loaded["filter"] = _unavailable_app("filter", exc)
        log.exception("Filter bot startup tasks failed")

root_app = Flask("borhan_gateway")

@root_app.get("/")
def index():
    return jsonify({
        "ok": True,
        "service": "Borhan Multi-Bot Gateway",
        "config_file_loaded": bool(BOT_CONFIG_PATH and not BOT_CONFIG_ERROR),
        "projects": {name: {"path": PREFIXES[name], "loaded": name in project_modules and name not in project_errors,
                             "error": project_errors.get(name)} for name in PREFIXES},
    })

@root_app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "borhan-multi-bot-gateway"}), 200

@root_app.get("/status")
def status():
    return jsonify({
        "ok": not bool(project_errors),
        "config_file_loaded": bool(BOT_CONFIG_PATH and not BOT_CONFIG_ERROR),
        "projects": {name: {"path": PREFIXES[name], "loaded": name in project_modules and name not in project_errors,
                             "error": project_errors.get(name)} for name in PREFIXES},
    }), (200 if not project_errors else 503)

mounts = {PREFIXES[name]: loaded[name] for name in PREFIXES}
application = DispatcherMiddleware(root_app, mounts)
