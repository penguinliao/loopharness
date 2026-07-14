#!/usr/bin/env bash
set -euo pipefail

# LoopHarness v1.4 installer
# Optional overrides: CLAUDE_HH_DIR=/path HARNESS_BIN_DIR=/path
INSTALL_DIR="${CLAUDE_HH_DIR:-${HOME}/.loopharness}"
BIN_DIR="${HARNESS_BIN_DIR:-${HOME}/.local/bin}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing LoopHarness v1.4 to ${INSTALL_DIR} ..."

mkdir -p "${INSTALL_DIR}/claude_hh" "${INSTALL_DIR}/hooks" \
  "${INSTALL_DIR}/prompts" "${INSTALL_DIR}/hermes" "${BIN_DIR}"
cp -R "${REPO_DIR}/claude_hh/." "${INSTALL_DIR}/claude_hh/"
cp -R "${REPO_DIR}/hooks/." "${INSTALL_DIR}/hooks/"
cp -R "${REPO_DIR}/prompts/." "${INSTALL_DIR}/prompts/"
cp -R "${REPO_DIR}/hermes/." "${INSTALL_DIR}/hermes/"
find "${INSTALL_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${INSTALL_DIR}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

{
  printf '%s\n' '#!/usr/bin/env bash'
  printf 'PYTHONPATH=%q exec python3 -m claude_hh.pipeline "$@"\n' "${INSTALL_DIR}"
} > "${BIN_DIR}/harness"
chmod 755 "${BIN_DIR}/harness"

PATH_MARKER="# LoopHarness PATH"
PATH_LINE="export PATH=\"${BIN_DIR}:\$PATH\""

retire_legacy_harness_alias() {
  local rc="$1"
  local temp_rc="${rc}.loopharness.$$"

  cp -p "${rc}" "${temp_rc}"
  awk '
    /^[[:space:]]*alias[[:space:]]+harness=/ &&
      index($0, "python3 -m claude_hh.pipeline") { next }
    { print }
  ' "${rc}" > "${temp_rc}"

  if cmp -s "${rc}" "${temp_rc}"; then
    rm -f "${temp_rc}"
    return
  fi

  mv "${temp_rc}" "${rc}"
  echo "  Retired legacy harness alias in ${rc}"
}

add_path() {
  local rc="$1"
  if grep -Fq "${PATH_MARKER}" "${rc}" 2>/dev/null; then
    echo "  (PATH already configured in ${rc}, skipping)"
    return
  fi
  printf '\n%s\n%s\n' "${PATH_MARKER}" "${PATH_LINE}" >> "${rc}"
  echo "  Added PATH to ${rc}"
}

for shell_rc in "${HOME}/.zshrc" "${HOME}/.bashrc"; do
  if [[ -f "${shell_rc}" ]]; then
    retire_legacy_harness_alias "${shell_rc}"
    add_path "${shell_rc}"
  fi
done

echo ""
echo "LoopHarness v1.4 installed."
echo "Executable: ${BIN_DIR}/harness"
echo "Run: harness -h"
