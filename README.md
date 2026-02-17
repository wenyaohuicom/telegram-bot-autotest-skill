# telegram-bot-autotest

[English](#english) | [中文](#中文)

---

## English

A Claude Code plugin/skill that automatically tests Telegram bots by logging in as a personal account and exploring all bot features.

### Features

- Auto-discover bot commands, inline buttons, and reply keyboards
- 6-phase exploration: `/start` → `/help` → inline buttons → reply keyboard → registered commands → common commands
- Structured JSON report output
- Session persistence (login once, reuse session)
- Safety limits: 1s delay between interactions, max 20 buttons, no URL/phone/geo clicks

### Install

```
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

Or from marketplace:

```
/plugin marketplace add wenyaohuicom/telegram-bot-autotest
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

### Usage

After installation, simply tell Claude:

> "Test the Telegram bot @BotFather"

Claude will automatically:

1. Check environment and dependencies
2. Verify Telegram credentials (ask if missing)
3. Handle login flow (send code → verify)
4. Run the bot exploration
5. Generate a human-readable feature summary

### Requirements

- Python 3.8+
- Telegram API credentials from https://my.telegram.org

### License

MIT

---

## 中文

一个 Claude Code 插件/技能，以 Telegram 个人账号登录，自动化测试指定的 Telegram Bot，探索其全部功能并生成结构化报告。

### 功能特性

- 自动发现 Bot 命令、Inline 按钮、Reply 键盘
- 6 阶段探索流程：`/start` → `/help` → Inline 按钮点击 → Reply 键盘按钮 → 注册命令 → 常见命令探测
- 结构化 JSON 报告输出
- Session 持久化（登录一次，后续复用）
- 安全限制：交互间隔 1 秒、最多点击 20 个按钮、不点击 URL/电话/位置类按钮

### 安装

```
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

或从 marketplace 安装：

```
/plugin marketplace add wenyaohuicom/telegram-bot-autotest
/plugin install telegram-bot-autotest@telegram-bot-autotest
```

### 使用方法

安装后，直接对 Claude 说：

> "测试一下 @BotFather 这个 Bot"

Claude 会自动执行：

1. 检查环境与依赖
2. 检查 Telegram API 凭证（缺少则向你询问）
3. 处理登录流程（发送验证码 → 输入验证码）
4. 运行 Bot 自动探索
5. 生成可读的功能总结报告

### 环境要求

- Python 3.8+
- Telegram API 凭证（从 https://my.telegram.org 获取）

### 许可证

MIT
