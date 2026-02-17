# telegram-bot-autotest

A Claude Code plugin/skill that automatically tests Telegram bots by logging in as a personal account and exploring all bot features.

## Features

- Auto-discover bot commands, inline buttons, and reply keyboards
- 6-phase exploration: /start → /help → inline buttons → reply keyboard → registered commands → common commands
- Structured JSON report output
- Session persistence (login once, reuse session)
- Safety limits: 1s delay, max 20 buttons, no URL/phone/geo clicks

## Install

```
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

Or from marketplace:

```
/plugin marketplace add wenyaohuicom/telegram-bot-autotest
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

## Usage

After installation, simply tell Claude:

> "Test the Telegram bot @BotFather"

Claude will automatically:
1. Check environment and dependencies
2. Verify Telegram credentials (ask if missing)
3. Handle login flow (send code → verify)
4. Run the bot exploration
5. Generate a human-readable feature summary

## Requirements

- Python 3.8+
- Telegram API credentials from https://my.telegram.org

## License

MIT
