#!/usr/bin/env bash
set -euo pipefail

# Claude H-H v1.0 installer
# Usage: bash install.sh
# Or:    curl -sSL https://raw.githubusercontent.com/penguinliao/claude-hh/main/install.sh | bash

INSTALL_DIR="${CLAUDE_HH_DIR:-$HOME/.claude-hh}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Claude H-H v1.0 to $INSTALL_DIR ..."

mkdir -p "$INSTALL_DIR/claude_hh"
mkdir -p "$INSTALL_DIR/hooks"
mkdir -p "$INSTALL_DIR/prompts"
mkdir -p "$INSTALL_DIR/hermes"

cp -r "$REPO_DIR/claude_hh/." "$INSTALL_DIR/claude_hh/"
cp -r "$REPO_DIR/hooks/." "$INSTALL_DIR/hooks/"
cp -r "$REPO_DIR/prompts/." "$INSTALL_DIR/prompts/"
cp -r "$REPO_DIR/hermes/." "$INSTALL_DIR/hermes/"

ALIAS_LINE="alias harness=\"PYTHONPATH=$INSTALL_DIR python3 -m claude_hh.pipeline\""

add_alias() {
  local rc="$1"
  if [[ -f "$rc" ]] && grep -q "alias harness=" "$rc" 2>/dev/null; then
    echo "  (alias already in $rc, skipping)"
    return
  fi
  printf "\n# Claude H-H\n%s\n" "$ALIAS_LINE" >> "$rc"
  echo "  Added alias to $rc"
}

[[ -f "$HOME/.zshrc" ]]  && add_alias "$HOME/.zshrc"
[[ -f "$HOME/.bashrc" ]] && add_alias "$HOME/.bashrc"

echo ""
echo "Claude H-H v1.0 installed to $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "  1. source ~/.zshrc   (or open a new terminal)"
echo "  2. cd your-project"
echo "  3. harness init"
echo "  4. harness start \"your task description\""
echo ""
echo "See examples/sample_spec.md for how to write a good spec."
