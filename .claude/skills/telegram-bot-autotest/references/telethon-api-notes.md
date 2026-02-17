# Telethon API Quick Reference

## Client Setup

```python
from telethon import TelegramClient

client = TelegramClient('session_name', api_id, api_hash)
await client.connect()
```

## Authentication

```python
# Check if authorized
await client.is_user_authorized()

# Send code
result = await client.send_code_request(phone)
# result.phone_code_hash needed for sign_in

# Sign in with code
await client.sign_in(phone=phone, code=code, phone_code_hash=hash)

# 2FA
from telethon.errors import SessionPasswordNeededError
try:
    await client.sign_in(...)
except SessionPasswordNeededError:
    await client.sign_in(password=password)

# Get own info
me = await client.get_me()
```

## Bot Info

```python
from telethon.tl.functions.users import GetFullUserRequest

full = await client(GetFullUserRequest(bot_entity))
# full.full_user.bot_info.description
# full.full_user.bot_info.commands -> [BotCommand(command, description)]
```

## Sending Messages

```python
# Simple send
await client.send_message(entity, 'text')

# Conversation mode (preferred)
async with client.conversation(entity, timeout=10) as conv:
    await conv.send_message('/start')
    response = await conv.get_response()
```

## Reading Messages

```python
# Get recent messages from a chat
async for msg in client.iter_messages(entity, limit=10):
    print(msg.text)
    # msg.reply_markup -> inline/reply keyboard
    # msg.media -> attached media
```

## Inline Button Click

```python
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

result = await client(GetBotCallbackAnswerRequest(
    peer=bot_entity,
    msg_id=message_id,
    data=button_data_bytes,
))
# result.message - callback answer text
# result.alert - if True, should be shown as alert
# result.url - if present, a URL to open
```

## Reply Markup Types

```python
from telethon.tl.types import (
    ReplyInlineMarkup,      # Inline buttons (under message)
    ReplyKeyboardMarkup,    # Reply keyboard (bottom of screen)
    ReplyKeyboardHide,      # Hide reply keyboard
    ReplyKeyboardForceReply,# Force reply
)
```

## Button Types

```python
from telethon.tl.types import (
    KeyboardButtonCallback,           # Callback data button
    KeyboardButtonUrl,                # URL button
    KeyboardButtonSwitchInline,       # Switch to inline mode
    KeyboardButtonRequestPhone,       # Share phone number
    KeyboardButtonRequestGeoLocation, # Share location
    KeyboardButton,                   # Simple text button (reply keyboard)
)
```

## Common Errors

```python
from telethon.errors import (
    FloodWaitError,           # Rate limited, e.seconds to wait
    PhoneCodeInvalidError,    # Wrong SMS code
    SessionPasswordNeededError,# 2FA required
    MessageIdInvalidError,    # Message no longer exists
    BotResponseTimeoutError,  # Bot didn't answer callback in time
    UserNotParticipantError,  # Not in the chat
)
```

## Entity Resolution

```python
# By username
entity = await client.get_entity('@BotFather')

# By ID
entity = await client.get_entity(12345)

# Input entity (more efficient)
entity = await client.get_input_entity('@BotFather')
```
