#!/usr/bin/env python3
"""Configuration management for telegram-bot-autotest.

Manages credentials stored in ~/.telegram-bot-autotest/.env
Modes: --check, --set, --get
All output is JSON for Claude to parse.
"""

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".telegram-bot-autotest"
ENV_FILE = CONFIG_DIR / ".env"

REQUIRED_KEYS = ["TG_API_ID", "TG_API_HASH", "TG_PHONE"]
OPTIONAL_KEYS = ["TG_SESSION_PATH"]
ALL_KEYS = REQUIRED_KEYS + OPTIONAL_KEYS


def ensure_dotenv():
    try:
        from dotenv import dotenv_values, set_key
        return dotenv_values, set_key
    except ImportError:
        print(json.dumps({
            "ok": False,
            "error": "python-dotenv not installed. Run: pip3 install python-dotenv"
        }))
        sys.exit(1)


def cmd_check():
    """Check if all required config values are present."""
    dotenv_values, _ = ensure_dotenv()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists():
        print(json.dumps({
            "ok": False,
            "configured": False,
            "missing": REQUIRED_KEYS,
            "present": [],
            "message": "No .env file found. Please set configuration first."
        }))
        sys.exit(1)

    values = dotenv_values(ENV_FILE)
    present = [k for k in ALL_KEYS if values.get(k)]
    missing = [k for k in REQUIRED_KEYS if not values.get(k)]

    if missing:
        print(json.dumps({
            "ok": False,
            "configured": False,
            "missing": missing,
            "present": present,
            "message": f"Missing required config: {', '.join(missing)}"
        }))
        sys.exit(1)

    print(json.dumps({
        "ok": True,
        "configured": True,
        "missing": [],
        "present": present,
        "message": "All required configuration is present."
    }))


def cmd_set(args):
    """Write config values to .env file."""
    _, set_key = ensure_dotenv()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists():
        ENV_FILE.touch(mode=0o600)

    updates = {}
    if args.api_id:
        updates["TG_API_ID"] = args.api_id
    if args.api_hash:
        updates["TG_API_HASH"] = args.api_hash
    if args.phone:
        updates["TG_PHONE"] = args.phone
    if args.session_path:
        updates["TG_SESSION_PATH"] = args.session_path

    if not updates:
        print(json.dumps({
            "ok": False,
            "error": "No values provided to set."
        }))
        sys.exit(1)

    for key, value in updates.items():
        set_key(str(ENV_FILE), key, value)

    # Restrict file permissions
    os.chmod(ENV_FILE, 0o600)

    print(json.dumps({
        "ok": True,
        "updated": list(updates.keys()),
        "message": f"Updated {len(updates)} config value(s)."
    }))


def cmd_get(args):
    """Read config values from .env file."""
    dotenv_values, _ = ensure_dotenv()

    if not ENV_FILE.exists():
        print(json.dumps({
            "ok": False,
            "error": "No .env file found."
        }))
        sys.exit(1)

    values = dotenv_values(ENV_FILE)

    if args.key:
        val = values.get(args.key)
        if val is None:
            print(json.dumps({
                "ok": False,
                "error": f"Key '{args.key}' not found."
            }))
            sys.exit(1)
        print(json.dumps({
            "ok": True,
            "key": args.key,
            "value": val
        }))
    else:
        # Return all keys (mask sensitive values)
        result = {}
        for k in ALL_KEYS:
            v = values.get(k)
            if v and k in ("TG_API_HASH",):
                result[k] = v[:4] + "..." + v[-4:] if len(v) > 8 else "***"
            elif v:
                result[k] = v
        print(json.dumps({
            "ok": True,
            "config": result
        }))


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Autotest Config Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Check if config is complete")

    set_p = sub.add_parser("set", help="Set config values")
    set_p.add_argument("--api-id", dest="api_id")
    set_p.add_argument("--api-hash", dest="api_hash")
    set_p.add_argument("--phone", dest="phone")
    set_p.add_argument("--session-path", dest="session_path")

    get_p = sub.add_parser("get", help="Get config values")
    get_p.add_argument("--key", help="Specific key to retrieve")

    # Support legacy --check/--set/--get flags
    parser.add_argument("--check", action="store_true", help="(legacy) Check config")
    parser.add_argument("--set", action="store_true", help="(legacy) Set config")
    parser.add_argument("--get", action="store_true", help="(legacy) Get config")
    parser.add_argument("--api-id", dest="api_id_legacy")
    parser.add_argument("--api-hash", dest="api_hash_legacy")
    parser.add_argument("--phone", dest="phone_legacy")
    parser.add_argument("--session-path", dest="session_path_legacy")
    parser.add_argument("--key", dest="key_legacy")

    args = parser.parse_args()

    # Handle legacy flag style
    if args.check or args.command == "check":
        cmd_check()
    elif args.set or args.command == "set":
        # Merge legacy args
        class SetArgs:
            api_id = getattr(args, 'api_id', None) or getattr(args, 'api_id_legacy', None)
            api_hash = getattr(args, 'api_hash', None) or getattr(args, 'api_hash_legacy', None)
            phone = getattr(args, 'phone', None) or getattr(args, 'phone_legacy', None)
            session_path = getattr(args, 'session_path', None) or getattr(args, 'session_path_legacy', None)
        cmd_set(SetArgs())
    elif args.get or args.command == "get":
        class GetArgs:
            key = getattr(args, 'key', None) or getattr(args, 'key_legacy', None)
        cmd_get(GetArgs())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
