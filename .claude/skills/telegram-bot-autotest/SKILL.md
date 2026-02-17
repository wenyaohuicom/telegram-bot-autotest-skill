---
name: telegram-bot-autotest
description: >
  This skill should be used when the user asks to "test a telegram bot",
  "explore a bot's functionality", "autotest a Telegram bot", or
  "check what a bot does". It logs into Telegram as a personal account
  and automatically interacts with the specified bot to discover and
  summarize its features.
---

# Telegram Bot Autotest Skill

You are executing the telegram-bot-autotest skill. Follow these steps precisely.

All scripts are located at: `{{SKILL_DIR}}/scripts/`
Runtime data is stored at: `~/.telegram-bot-autotest/`

## Step 1: Environment Setup

Run the setup script to check dependencies:

```bash
bash {{SKILL_DIR}}/scripts/setup.sh
```

Parse the JSON output. If `ok` is false, show the error to the user and stop.

## Step 2: Check Configuration

```bash
python3 {{SKILL_DIR}}/scripts/config.py --check
```

If configuration is missing (`ok` is false), ask the user for the missing values:

- **TG_API_ID**: Telegram API ID (integer, from https://my.telegram.org)
- **TG_API_HASH**: Telegram API Hash (string, from https://my.telegram.org)
- **TG_PHONE**: Phone number with country code (e.g., +1234567890)

Then save them:

```bash
python3 {{SKILL_DIR}}/scripts/config.py --set --api-id=XXXX --api-hash=XXXX --phone=+XXXX
```

## Step 3: Check Login Status

```bash
python3 {{SKILL_DIR}}/scripts/tg_login.py --check
```

If not authorized (`authorized` is false), execute the login flow:

### 3a. Send verification code

```bash
python3 {{SKILL_DIR}}/scripts/tg_login.py --login
```

Tell the user a verification code has been sent to their Telegram app, and ask them to provide it.

### 3b. Verify the code

```bash
python3 {{SKILL_DIR}}/scripts/tg_login.py --verify --code=XXXXX
```

If the response contains `needs_2fa: true`, ask the user for their 2FA password and run:

```bash
python3 {{SKILL_DIR}}/scripts/tg_login.py --verify --password=XXXXX
```

If `PhoneCodeInvalidError`, ask the user to re-enter the code.

## Step 4: Run Bot Test

Once logged in, run the bot tester with the target bot username:

```bash
python3 {{SKILL_DIR}}/scripts/tg_bot_tester.py @TARGET_BOT --save
```

Replace `@TARGET_BOT` with the bot username the user wants to test.

The `--save` flag saves the report to `~/.telegram-bot-autotest/reports/`.

## Step 5: Generate Summary Report

Parse the JSON output and present a structured summary to the user:

### Report Format

**Bot: @username** - Bot Name
**Description:** (from bot_info)

**Registered Commands:**
- List each command with its description

**Feature Discovery:**

For each phase that returned data:
1. **/start response** - Summarize what the bot says on start
2. **/help response** - Summarize help text
3. **Inline Buttons** - List discovered buttons and what they do
4. **Reply Keyboard** - List keyboard options and their effects
5. **Registered Commands** - Results of each command
6. **Additional Commands** - Any common commands that worked

**Statistics:**
- Total interactions / Successful / Timeouts / Errors

**Observations:**
- Note any interesting patterns (e.g., "bot has a rich menu system", "bot supports multiple languages")
- Flag any errors or unusual behavior

## Error Handling

- If any script returns exit code 2, an unexpected error occurred. Show the error JSON to the user.
- If the bot test encounters a `FloodWaitError`, inform the user they need to wait before retrying.
- If a specific command times out, note it in the report but continue testing.

## Important Notes

- Never share or display the user's API credentials in the output.
- The test only reads from the bot; it does not share phone, location, or click URL buttons.
- Inline button exploration is limited to depth 1 and max 20 buttons for safety.
- There is a 1-second delay between interactions to avoid rate limiting.
