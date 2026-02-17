#!/usr/bin/env python3
"""Telegram login and session management.

Modes:
  --check              Check if session is valid
  --login              Send verification code
  --verify --code=XXX  Verify SMS code
  --verify --password=X  2FA password verification

All output is JSON.
Exit codes: 0=success, 1=expected failure, 2=unexpected error
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure parent dir is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """Load config from .env file."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return None, "python-dotenv not installed"

    env_file = Path.home() / ".telegram-bot-autotest" / ".env"
    if not env_file.exists():
        return None, "Config file not found. Run config.py --set first."

    values = dotenv_values(env_file)
    api_id = values.get("TG_API_ID")
    api_hash = values.get("TG_API_HASH")
    phone = values.get("TG_PHONE")

    if not all([api_id, api_hash, phone]):
        missing = []
        if not api_id:
            missing.append("TG_API_ID")
        if not api_hash:
            missing.append("TG_API_HASH")
        if not phone:
            missing.append("TG_PHONE")
        return None, f"Missing config: {', '.join(missing)}"

    session_path = values.get("TG_SESSION_PATH")
    if not session_path:
        session_path = str(Path.home() / ".telegram-bot-autotest" / "sessions" / "tg_user")

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "phone": phone,
        "session_path": session_path,
    }, None


def get_client(config):
    """Create a Telethon client."""
    from telethon import TelegramClient

    session_dir = os.path.dirname(config["session_path"])
    os.makedirs(session_dir, exist_ok=True)

    client = TelegramClient(
        config["session_path"],
        config["api_id"],
        config["api_hash"],
    )
    return client


# Store phone_code_hash between --login and --verify calls
HASH_FILE = Path.home() / ".telegram-bot-autotest" / "sessions" / ".phone_code_hash"


async def cmd_check(config):
    """Check if current session is authorized."""
    client = get_client(config)
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        if authorized:
            me = await client.get_me()
            print(json.dumps({
                "ok": True,
                "authorized": True,
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone,
                },
                "message": f"Logged in as {me.first_name} (@{me.username or 'N/A'})"
            }))
        else:
            print(json.dumps({
                "ok": True,
                "authorized": False,
                "message": "Session exists but not authorized. Please login."
            }))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "authorized": False,
            "error": str(e),
            "message": "Failed to check session."
        }))
        sys.exit(2)
    finally:
        await client.disconnect()


async def cmd_login(config):
    """Send verification code to phone."""
    client = get_client(config)
    try:
        await client.connect()

        # Check if already authorized
        if await client.is_user_authorized():
            me = await client.get_me()
            print(json.dumps({
                "ok": True,
                "already_authorized": True,
                "message": f"Already logged in as {me.first_name} (@{me.username or 'N/A'})"
            }))
            return

        result = await client.send_code_request(config["phone"])

        # Save phone_code_hash for verification step
        HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        HASH_FILE.write_text(result.phone_code_hash)
        os.chmod(HASH_FILE, 0o600)

        print(json.dumps({
            "ok": True,
            "code_sent": True,
            "phone": config["phone"],
            "message": f"Verification code sent to {config['phone']}. Use --verify --code=XXXXX to complete login."
        }))
    except Exception as e:
        error_type = type(e).__name__
        print(json.dumps({
            "ok": False,
            "error": str(e),
            "error_type": error_type,
            "message": f"Failed to send code: {e}"
        }))
        sys.exit(2)
    finally:
        await client.disconnect()


async def cmd_verify(config, code=None, password=None):
    """Verify SMS code or 2FA password."""
    from telethon.errors import (
        PhoneCodeInvalidError,
        SessionPasswordNeededError,
    )

    client = get_client(config)
    try:
        await client.connect()

        if code:
            # Verify SMS code
            if not HASH_FILE.exists():
                print(json.dumps({
                    "ok": False,
                    "error": "No pending login found. Run --login first.",
                }))
                sys.exit(1)

            phone_code_hash = HASH_FILE.read_text().strip()

            try:
                await client.sign_in(
                    phone=config["phone"],
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
            except PhoneCodeInvalidError:
                print(json.dumps({
                    "ok": False,
                    "error": "Invalid verification code.",
                    "error_type": "PhoneCodeInvalidError",
                    "message": "The code you entered is incorrect. Please try again."
                }))
                sys.exit(1)
            except SessionPasswordNeededError:
                print(json.dumps({
                    "ok": False,
                    "needs_2fa": True,
                    "error_type": "SessionPasswordNeededError",
                    "message": "Two-factor authentication is enabled. Please provide your 2FA password with --verify --password=YOUR_PASSWORD"
                }))
                sys.exit(1)

        elif password:
            # 2FA password verification
            try:
                await client.sign_in(password=password)
            except Exception as e:
                print(json.dumps({
                    "ok": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "message": f"2FA verification failed: {e}"
                }))
                sys.exit(1)
        else:
            print(json.dumps({
                "ok": False,
                "error": "Provide --code or --password"
            }))
            sys.exit(1)

        # Success - get user info
        me = await client.get_me()

        # Clean up hash file
        if HASH_FILE.exists():
            HASH_FILE.unlink()

        print(json.dumps({
            "ok": True,
            "authorized": True,
            "user": {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            },
            "message": f"Successfully logged in as {me.first_name} (@{me.username or 'N/A'})"
        }))
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Verification failed: {e}"
        }))
        sys.exit(2)
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Telegram Login Manager")
    parser.add_argument("--check", action="store_true", help="Check session status")
    parser.add_argument("--login", action="store_true", help="Send verification code")
    parser.add_argument("--verify", action="store_true", help="Verify code or 2FA password")
    parser.add_argument("--code", help="SMS verification code")
    parser.add_argument("--password", help="2FA password")

    args = parser.parse_args()

    config, error = load_config()
    if error:
        print(json.dumps({"ok": False, "error": error}))
        sys.exit(1)

    if args.check:
        asyncio.run(cmd_check(config))
    elif args.login:
        asyncio.run(cmd_login(config))
    elif args.verify:
        asyncio.run(cmd_verify(config, code=args.code, password=args.password))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
