#!/usr/bin/env bash
# Environment check and dependency installation for telegram-bot-autotest.
# Outputs JSON status.

set -euo pipefail

CONFIG_DIR="$HOME/.telegram-bot-autotest"
SESSIONS_DIR="$CONFIG_DIR/sessions"
REPORTS_DIR="$CONFIG_DIR/reports"

json_ok() {
    echo "{\"ok\":true,\"python\":\"$1\",\"pip\":\"$2\",\"telethon\":\"$3\",\"dotenv\":\"$4\",\"message\":\"Environment ready.\"}"
}

json_error() {
    echo "{\"ok\":false,\"error\":\"$1\"}"
    exit 1
}

# Check python3
if ! command -v python3 &>/dev/null; then
    json_error "python3 not found. Please install Python 3.8+."
fi

PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')

# Check pip3
if ! command -v pip3 &>/dev/null; then
    # Try python3 -m pip
    if ! python3 -m pip --version &>/dev/null; then
        json_error "pip3 not found. Please install pip3."
    fi
    PIP_CMD="python3 -m pip"
else
    PIP_CMD="pip3"
fi

PIP_VER=$($PIP_CMD --version 2>&1 | awk '{print $2}')

# Install telethon if needed
TELETHON_VER=""
if python3 -c "import telethon" &>/dev/null; then
    TELETHON_VER=$(python3 -c "import telethon; print(telethon.__version__)" 2>/dev/null || echo "installed")
else
    $PIP_CMD install telethon -q 2>/dev/null
    if python3 -c "import telethon" &>/dev/null; then
        TELETHON_VER=$(python3 -c "import telethon; print(telethon.__version__)" 2>/dev/null || echo "installed")
    else
        json_error "Failed to install telethon."
    fi
fi

# Install python-dotenv if needed
DOTENV_VER=""
if python3 -c "from dotenv import dotenv_values" &>/dev/null; then
    DOTENV_VER=$(python3 -c "from importlib.metadata import version; print(version('python-dotenv'))" 2>/dev/null || echo "installed")
else
    $PIP_CMD install python-dotenv -q 2>/dev/null
    if python3 -c "from dotenv import dotenv_values" &>/dev/null; then
        DOTENV_VER=$(python3 -c "from importlib.metadata import version; print(version('python-dotenv'))" 2>/dev/null || echo "installed")
    else
        json_error "Failed to install python-dotenv."
    fi
fi

# Create runtime directories
mkdir -p "$SESSIONS_DIR" "$REPORTS_DIR"
chmod 700 "$CONFIG_DIR"

json_ok "$PYTHON_VER" "$PIP_VER" "$TELETHON_VER" "$DOTENV_VER"
