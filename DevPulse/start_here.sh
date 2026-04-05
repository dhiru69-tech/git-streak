#!/usr/bin/env bash
# DevPulse — One-Click Installer
# Works on: Linux, macOS, Termux (Android)
# Usage: bash start_here.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

R='\033[91m'; G='\033[92m'; Y='\033[93m'
B='\033[94m'; C='\033[96m'; W='\033[97m'
DIM='\033[2m'; RST='\033[0m'; BOLD='\033[1m'

ok()   { echo -e "  ${G}ok${RST}  $1"; }
fail() { echo -e "  ${R}!!${RST}  $1"; }
info() { echo -e "  ${B}->${RST}  $1"; }
warn() { echo -e "  ${Y}! ${RST}  $1"; }
step() { echo -e "\n  ${BOLD}$1${RST}"; }

# Detect environment
IS_TERMUX=false
IS_MAC=false
IS_LINUX=false
[[ -n "${PREFIX}" && "${PREFIX}" == *"termux"* ]] && IS_TERMUX=true
[[ "$(uname)" == "Darwin" ]]                       && IS_MAC=true
[[ "$(uname)" == "Linux" && "$IS_TERMUX" == false ]] && IS_LINUX=true

echo -e "
${C}  ============================================================
   DevPulse — One-Click Installer
   Everything will be installed automatically
  ============================================================${RST}
"

# ════════════════════════════════════════════════════
# STEP 1 — Python
# ════════════════════════════════════════════════════
step "[1/5] Checking Python..."

PYTHON_CMD=""
for cmd in python3 python python3.11 python3.10 python3.9; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
            PYTHON_CMD="$cmd"
            ok "Python: $($cmd --version 2>&1)"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    warn "Python 3.8+ not found. Installing..."
    if $IS_TERMUX; then
        pkg install python -y
        PYTHON_CMD="python"
    elif $IS_MAC; then
        if command -v brew &>/dev/null; then
            brew install python@3.11
            PYTHON_CMD="python3.11"
        else
            info "Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install python@3.11
            PYTHON_CMD="python3.11"
        fi
    elif $IS_LINUX; then
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip
            PYTHON_CMD="python3"
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
            PYTHON_CMD="python3"
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python python-pip
            PYTHON_CMD="python3"
        else
            fail "Cannot auto-install Python. Visit: https://python.org"
            exit 1
        fi
    fi
    ok "Python installed: $($PYTHON_CMD --version 2>&1)"
fi

# ════════════════════════════════════════════════════
# STEP 2 — Git
# ════════════════════════════════════════════════════
step "[2/5] Checking Git..."

if command -v git &>/dev/null; then
    ok "$(git --version)"
else
    warn "Git not found. Installing..."
    if $IS_TERMUX; then
        pkg install git -y
    elif $IS_MAC; then
        brew install git
    elif $IS_LINUX; then
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y git
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y git
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm git
        fi
    fi
    ok "$(git --version)"
fi

# ════════════════════════════════════════════════════
# STEP 3 — Python packages
# ════════════════════════════════════════════════════
step "[3/5] Installing Python packages..."

install_pkg() {
    local pkg="$1"
    local name="${pkg%%>=*}"
    name="${name%%==*}"

    if $PYTHON_CMD -c "import $name" 2>/dev/null; then
        ok "$name already installed"
        return
    fi
    info "Installing $pkg..."
    # Try multiple methods until one works
    $PYTHON_CMD -m pip install "$pkg" --quiet 2>/dev/null ||
    $PYTHON_CMD -m pip install "$pkg" --quiet --break-system-packages 2>/dev/null ||
    $PYTHON_CMD -m pip install "$pkg" --quiet --user 2>/dev/null || true

    if $PYTHON_CMD -c "import $name" 2>/dev/null; then
        ok "$name installed"
    else
        warn "$name install uncertain — continuing anyway"
    fi
}

# Termux has different package names
if $IS_TERMUX; then
    pkg install python-psutil -y 2>/dev/null || install_pkg "psutil>=5.9.0"
else
    install_pkg "psutil>=5.9.0"
fi
# anthropic is optional — only if user wants it
# install_pkg "anthropic>=0.18.0"

# ════════════════════════════════════════════════════
# STEP 4 — Git identity
# ════════════════════════════════════════════════════
step "[4/5] Checking git identity..."

GIT_NAME=$(git config --global user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config --global user.email 2>/dev/null || echo "")

if [[ -z "$GIT_NAME" ]]; then
    printf "       Your name for git commits: "
    read -r GIT_NAME
    git config --global user.name "$GIT_NAME"
fi
if [[ -z "$GIT_EMAIL" ]]; then
    printf "       Your email for git commits: "
    read -r GIT_EMAIL
    git config --global user.email "$GIT_EMAIL"
fi
ok "Identity: $GIT_NAME <$GIT_EMAIL>"

# ════════════════════════════════════════════════════
# STEP 5 — Launch DevPulse
# ════════════════════════════════════════════════════
step "[5/5] Launching DevPulse..."
echo -e "  ${DIM}The interactive menu will guide you through everything else.${RST}\n"

$PYTHON_CMD "$SCRIPT_DIR/cli.py"

echo -e "
${G}  ============================================================
   DevPulse is set up!
   Next time run:  $PYTHON_CMD cli.py
  ============================================================${RST}
"
