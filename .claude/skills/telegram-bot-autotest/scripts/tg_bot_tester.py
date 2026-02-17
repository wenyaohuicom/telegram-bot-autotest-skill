#!/usr/bin/env python3
"""Core Bot Auto-Exploration Engine.

Usage: python3 tg_bot_tester.py @BotUsername [--timeout=10] [--max-buttons=20]

Phases:
  0. Bot info (description, registered commands)
  1. /start
  2. /help
  3. Inline button clicks (depth 1, max 20)
  4. Reply keyboard button presses
  5. Registered commands
  6. Common command probing

Output: Structured JSON report to stdout.
Exit codes: 0=success, 1=expected failure, 2=unexpected error
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config loading (shared with tg_login.py)
# ---------------------------------------------------------------------------

def load_config():
    try:
        from dotenv import dotenv_values
    except ImportError:
        return None, "python-dotenv not installed"

    env_file = Path.home() / ".telegram-bot-autotest" / ".env"
    if not env_file.exists():
        return None, "Config file not found."

    values = dotenv_values(env_file)
    api_id = values.get("TG_API_ID")
    api_hash = values.get("TG_API_HASH")

    if not all([api_id, api_hash]):
        return None, "Missing TG_API_ID or TG_API_HASH"

    session_path = values.get("TG_SESSION_PATH")
    if not session_path:
        session_path = str(Path.home() / ".telegram-bot-autotest" / "sessions" / "tg_user")

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "session_path": session_path,
    }, None


# ---------------------------------------------------------------------------
# Message capture helpers
# ---------------------------------------------------------------------------

INTERACTION_DELAY = 1  # seconds between interactions
COMMON_COMMANDS = ["/settings", "/menu", "/info", "/about", "/status", "/profile", "/language", "/lang"]
UNKNOWN_PATTERNS = [
    "unknown command", "i don't understand", "i don't know that command",
    "unrecognized command", "invalid command", "command not found",
    "не понимаю", "неизвестная команда",
]


def serialize_message(msg):
    """Convert a Telethon message to a JSON-serializable dict."""
    from telethon.tl.types import (
        ReplyInlineMarkup, ReplyKeyboardMarkup,
        KeyboardButtonUrl, KeyboardButtonRequestPhone,
        KeyboardButtonRequestGeoLocation, KeyboardButtonCallback,
        KeyboardButtonSwitchInline,
    )

    data = {
        "id": msg.id,
        "text": msg.text or "",
        "date": msg.date.isoformat() if msg.date else None,
    }

    # Extract inline buttons
    if msg.reply_markup and isinstance(msg.reply_markup, ReplyInlineMarkup):
        buttons = []
        for row in msg.reply_markup.rows:
            row_btns = []
            for btn in row.buttons:
                btn_data = {"text": btn.text, "type": "unknown"}
                if isinstance(btn, KeyboardButtonCallback):
                    btn_data["type"] = "callback"
                    btn_data["data"] = btn.data.decode("utf-8", errors="replace") if btn.data else ""
                elif isinstance(btn, KeyboardButtonUrl):
                    btn_data["type"] = "url"
                    btn_data["url"] = btn.url
                elif isinstance(btn, KeyboardButtonSwitchInline):
                    btn_data["type"] = "switch_inline"
                    btn_data["query"] = btn.query
                elif isinstance(btn, KeyboardButtonRequestPhone):
                    btn_data["type"] = "share_phone"
                elif isinstance(btn, KeyboardButtonRequestGeoLocation):
                    btn_data["type"] = "share_geo"
                else:
                    btn_data["type"] = type(btn).__name__
                row_btns.append(btn_data)
            buttons.append(row_btns)
        data["inline_buttons"] = buttons

    # Extract reply keyboard
    if msg.reply_markup and isinstance(msg.reply_markup, ReplyKeyboardMarkup):
        keyboard = []
        for row in msg.reply_markup.rows:
            row_btns = []
            for btn in row.buttons:
                btn_info = {"text": btn.text}
                if isinstance(btn, KeyboardButtonRequestPhone):
                    btn_info["type"] = "share_phone"
                elif isinstance(btn, KeyboardButtonRequestGeoLocation):
                    btn_info["type"] = "share_geo"
                else:
                    btn_info["type"] = "text"
                row_btns.append(btn_info)
            keyboard.append(row_btns)
        data["reply_keyboard"] = keyboard

    # Media info
    if msg.media:
        data["has_media"] = True
        data["media_type"] = type(msg.media).__name__
    else:
        data["has_media"] = False

    return data


def is_unknown_response(text):
    """Check if the response indicates an unknown command."""
    if not text:
        return False
    text_lower = text.lower()
    return any(p in text_lower for p in UNKNOWN_PATTERNS)


async def send_and_capture(client, bot_entity, text, timeout=10):
    """Send a message and capture bot responses.

    Uses conversation context manager with fallback to manual polling.
    """
    from telethon.errors import TimeoutError as TelethonTimeout

    record = {
        "sent": text,
        "responses": [],
        "error": None,
        "timed_out": False,
    }

    try:
        # Try conversation mode first
        try:
            async with client.conversation(bot_entity, timeout=timeout) as conv:
                await conv.send_message(text)
                await asyncio.sleep(0.5)

                # Collect responses (bot may send multiple messages)
                try:
                    while True:
                        resp = await asyncio.wait_for(conv.get_response(), timeout=3)
                        record["responses"].append(serialize_message(resp))
                except (asyncio.TimeoutError, TelethonTimeout):
                    pass  # No more responses
        except Exception:
            # Fallback: manual send + poll
            await client.send_message(bot_entity, text)
            await asyncio.sleep(min(timeout, 5))

            messages = []
            async for msg in client.iter_messages(bot_entity, limit=5):
                if msg.out:
                    break  # Stop at our own message
                messages.append(msg)

            messages.reverse()
            record["responses"] = [serialize_message(m) for m in messages]
    except asyncio.TimeoutError:
        record["timed_out"] = True
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"

    if not record["responses"] and not record["error"]:
        record["timed_out"] = True

    return record


async def click_inline_button(client, msg_id, bot_entity, button_data, button_text):
    """Click an inline callback button and capture the result."""
    from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
    from telethon.errors import (
        MessageIdInvalidError, BotResponseTimeoutError,
        DataInvalidError,
    )

    record = {
        "button_text": button_text,
        "button_data": button_data,
        "callback_answer": None,
        "new_message": None,
        "edited_message": None,
        "error": None,
    }

    try:
        # Get messages before click for comparison
        pre_msgs = []
        async for m in client.iter_messages(bot_entity, limit=3):
            pre_msgs.append(m.id)

        # Click the button
        try:
            result = await client(GetBotCallbackAnswerRequest(
                peer=bot_entity,
                msg_id=msg_id,
                data=button_data.encode("utf-8") if isinstance(button_data, str) else button_data,
            ))
            if result.message:
                record["callback_answer"] = result.message
            if result.alert:
                record["callback_answer"] = f"[ALERT] {result.message}"
            if result.url:
                record["callback_answer"] = f"[URL] {result.url}"
        except BotResponseTimeoutError:
            record["callback_answer"] = "(no callback answer)"

        # Wait and check for new/edited messages
        await asyncio.sleep(2)

        async for m in client.iter_messages(bot_entity, limit=5):
            if m.out:
                break
            if m.id not in pre_msgs:
                record["new_message"] = serialize_message(m)
                break
            if m.id == msg_id and m.edit_date:
                record["edited_message"] = serialize_message(m)
                break

    except MessageIdInvalidError:
        record["error"] = "MessageIdInvalidError: message no longer exists"
    except DataInvalidError:
        record["error"] = "DataInvalidError: button data invalid"
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"

    return record


# ---------------------------------------------------------------------------
# Main test engine
# ---------------------------------------------------------------------------

async def run_test(bot_username, timeout=10, max_buttons=20):
    """Run the full bot exploration."""
    from telethon import TelegramClient
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.errors import FloodWaitError

    config, error = load_config()
    if error:
        return {"ok": False, "error": error}

    client = TelegramClient(config["session_path"], config["api_id"], config["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        return {"ok": False, "error": "Not authorized. Run tg_login.py --login first."}

    report = {
        "ok": True,
        "bot_username": bot_username,
        "test_started": datetime.now(timezone.utc).isoformat(),
        "bot_info": {},
        "phases": {},
        "statistics": {
            "total_interactions": 0,
            "successful_responses": 0,
            "timeouts": 0,
            "errors": 0,
            "buttons_clicked": 0,
            "commands_tested": 0,
        },
    }

    try:
        # Resolve bot entity
        try:
            bot_entity = await client.get_entity(bot_username)
        except Exception as e:
            await client.disconnect()
            return {"ok": False, "error": f"Cannot find bot '{bot_username}': {e}"}

        # ---------------------------------------------------------------
        # Phase 0: Bot info
        # ---------------------------------------------------------------
        try:
            full_user = await client(GetFullUserRequest(bot_entity))
            bot_info = {
                "id": bot_entity.id,
                "first_name": getattr(bot_entity, "first_name", ""),
                "username": getattr(bot_entity, "username", ""),
                "is_bot": getattr(bot_entity, "bot", False),
                "description": getattr(full_user.full_user, "about", "") or "",
            }

            # Extract bot commands from bot_info
            if hasattr(full_user.full_user, "bot_info") and full_user.full_user.bot_info:
                bi = full_user.full_user.bot_info
                bot_info["description"] = getattr(bi, "description", "") or bot_info["description"]
                if hasattr(bi, "commands") and bi.commands:
                    bot_info["registered_commands"] = [
                        {"command": f"/{c.command}", "description": c.description}
                        for c in bi.commands
                    ]
                else:
                    bot_info["registered_commands"] = []
            else:
                bot_info["registered_commands"] = []

            report["bot_info"] = bot_info
        except Exception as e:
            report["bot_info"] = {"error": f"Failed to get bot info: {e}"}

        # Collect inline buttons and reply keyboard across phases for later exploration
        discovered_inline_buttons = []  # [(msg_id, data_bytes, text)]
        discovered_reply_buttons = []   # [text]

        def collect_buttons(records):
            """Extract buttons from interaction records for later phases."""
            for rec in records:
                for resp in rec.get("responses", []):
                    # Inline buttons
                    for row in resp.get("inline_buttons", []):
                        for btn in row:
                            if btn["type"] == "callback" and btn.get("data"):
                                discovered_inline_buttons.append(
                                    (resp["id"], btn["data"], btn["text"])
                                )
                    # Reply keyboard
                    for row in resp.get("reply_keyboard", []):
                        for btn in row:
                            if btn.get("type") == "text":
                                discovered_reply_buttons.append(btn["text"])

        # ---------------------------------------------------------------
        # Phase 1: /start
        # ---------------------------------------------------------------
        await asyncio.sleep(INTERACTION_DELAY)
        start_rec = await send_and_capture(client, bot_entity, "/start", timeout)
        report["phases"]["start"] = start_rec
        report["statistics"]["total_interactions"] += 1
        report["statistics"]["commands_tested"] += 1
        if start_rec["responses"]:
            report["statistics"]["successful_responses"] += 1
            collect_buttons([start_rec])
        elif start_rec["timed_out"]:
            report["statistics"]["timeouts"] += 1
        elif start_rec["error"]:
            report["statistics"]["errors"] += 1

        # ---------------------------------------------------------------
        # Phase 2: /help
        # ---------------------------------------------------------------
        await asyncio.sleep(INTERACTION_DELAY)
        help_rec = await send_and_capture(client, bot_entity, "/help", timeout)
        report["phases"]["help"] = help_rec
        report["statistics"]["total_interactions"] += 1
        report["statistics"]["commands_tested"] += 1
        if help_rec["responses"]:
            report["statistics"]["successful_responses"] += 1
            collect_buttons([help_rec])
        elif help_rec["timed_out"]:
            report["statistics"]["timeouts"] += 1
        elif help_rec["error"]:
            report["statistics"]["errors"] += 1

        # ---------------------------------------------------------------
        # Phase 3: Click inline buttons (depth 1, max N)
        # ---------------------------------------------------------------
        inline_results = []
        buttons_to_click = discovered_inline_buttons[:max_buttons]
        for msg_id, btn_data, btn_text in buttons_to_click:
            await asyncio.sleep(INTERACTION_DELAY)
            try:
                result = await click_inline_button(
                    client, msg_id, bot_entity, btn_data, btn_text
                )
                inline_results.append(result)
                report["statistics"]["buttons_clicked"] += 1
                report["statistics"]["total_interactions"] += 1
                if result.get("error"):
                    report["statistics"]["errors"] += 1
                else:
                    report["statistics"]["successful_responses"] += 1
            except FloodWaitError as e:
                inline_results.append({
                    "button_text": btn_text,
                    "error": f"FloodWaitError: must wait {e.seconds}s",
                })
                report["statistics"]["errors"] += 1
                break  # Stop on flood
            except Exception as e:
                inline_results.append({
                    "button_text": btn_text,
                    "error": f"{type(e).__name__}: {e}",
                })
                report["statistics"]["errors"] += 1

        report["phases"]["inline_buttons"] = inline_results

        # ---------------------------------------------------------------
        # Phase 4: Reply keyboard buttons
        # ---------------------------------------------------------------
        reply_results = []
        for btn_text in discovered_reply_buttons:
            # Skip phone/geo share buttons (already filtered by type)
            await asyncio.sleep(INTERACTION_DELAY)
            rec = await send_and_capture(client, bot_entity, btn_text, timeout)
            rec["button_label"] = btn_text
            reply_results.append(rec)
            report["statistics"]["total_interactions"] += 1
            report["statistics"]["buttons_clicked"] += 1
            if rec["responses"]:
                report["statistics"]["successful_responses"] += 1
                collect_buttons([rec])
            elif rec["timed_out"]:
                report["statistics"]["timeouts"] += 1
            elif rec["error"]:
                report["statistics"]["errors"] += 1

        report["phases"]["reply_keyboard"] = reply_results

        # ---------------------------------------------------------------
        # Phase 5: Registered commands (skip /start and /help already done)
        # ---------------------------------------------------------------
        reg_commands = report["bot_info"].get("registered_commands", [])
        reg_results = []
        already_tested = {"/start", "/help"}
        for cmd_info in reg_commands:
            cmd = cmd_info["command"]
            if cmd in already_tested:
                continue
            already_tested.add(cmd)

            await asyncio.sleep(INTERACTION_DELAY)
            rec = await send_and_capture(client, bot_entity, cmd, timeout)
            rec["command_description"] = cmd_info.get("description", "")
            reg_results.append(rec)
            report["statistics"]["total_interactions"] += 1
            report["statistics"]["commands_tested"] += 1
            if rec["responses"]:
                report["statistics"]["successful_responses"] += 1
                collect_buttons([rec])
            elif rec["timed_out"]:
                report["statistics"]["timeouts"] += 1
            elif rec["error"]:
                report["statistics"]["errors"] += 1

        report["phases"]["registered_commands"] = reg_results

        # ---------------------------------------------------------------
        # Phase 6: Common commands probing
        # ---------------------------------------------------------------
        probe_results = []
        for cmd in COMMON_COMMANDS:
            if cmd in already_tested:
                continue
            already_tested.add(cmd)

            await asyncio.sleep(INTERACTION_DELAY)
            rec = await send_and_capture(client, bot_entity, cmd, timeout)
            report["statistics"]["total_interactions"] += 1
            report["statistics"]["commands_tested"] += 1

            # Filter out unknown command responses
            first_text = ""
            if rec["responses"]:
                first_text = rec["responses"][0].get("text", "")

            if rec["responses"] and not is_unknown_response(first_text):
                rec["recognized"] = True
                report["statistics"]["successful_responses"] += 1
                probe_results.append(rec)
                collect_buttons([rec])
            else:
                rec["recognized"] = False
                if rec["timed_out"]:
                    report["statistics"]["timeouts"] += 1
                # Still include but mark as unrecognized
                probe_results.append(rec)

        report["phases"]["common_commands"] = probe_results

        report["test_finished"] = datetime.now(timezone.utc).isoformat()

    except FloodWaitError as e:
        report["error"] = f"FloodWaitError: Telegram requires waiting {e.seconds} seconds. Test aborted."
        report["statistics"]["errors"] += 1
    except Exception as e:
        report["error"] = f"{type(e).__name__}: {e}"
        report["statistics"]["errors"] += 1
    finally:
        await client.disconnect()

    return report


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Auto-Tester")
    parser.add_argument("bot", help="Bot username (e.g. @BotFather)")
    parser.add_argument("--timeout", type=int, default=10, help="Response timeout in seconds (default: 10)")
    parser.add_argument("--max-buttons", type=int, default=20, help="Max inline buttons to click (default: 20)")
    parser.add_argument("--save", action="store_true", help="Save report to ~/.telegram-bot-autotest/reports/")

    args = parser.parse_args()

    bot = args.bot
    if not bot.startswith("@"):
        bot = "@" + bot

    report = asyncio.run(run_test(bot, timeout=args.timeout, max_buttons=args.max_buttons))

    # Save report if requested
    if args.save and report.get("ok"):
        reports_dir = Path.home() / ".telegram-bot-autotest" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{bot.lstrip('@')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = reports_dir / filename
        filepath.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        report["saved_to"] = str(filepath)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not report.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
