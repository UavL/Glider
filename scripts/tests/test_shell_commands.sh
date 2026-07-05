#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_file_contains() {
    local path="$1"
    local pattern="$2"
    local label="$3"

    if ! grep -Eq "$pattern" "$path"; then
        fail "$label: '$path' does not contain '$pattern'"
    fi
}

shell_c="$REPO_ROOT/fw/User/shell/shell.c"
shell_cmds_c="$REPO_ROOT/fw/User/shell/shell_cmds.c"

assert_file_contains "$shell_c" "SHELL_FUNC\\( shell_setres \\);" "setres handler declaration"
assert_file_contains "$shell_c" "SHELL_HELP\\( setres \\);" "setres help declaration"
assert_file_contains "$shell_c" "\\{ \"setres\", shell_setres \\}" "setres command registration"
assert_file_contains "$shell_c" "SHELL_INFO\\( setres \\)" "setres help registration"
assert_file_contains "$shell_cmds_c" "const char shell_help_setres\\[\\]" "setres help text"
assert_file_contains "$shell_cmds_c" "void shell_setres\\( shell_context_t \\*ctx, int argc, char \\*\\*argv \\)" "setres implementation"
assert_file_contains "$shell_cmds_c" "config_apply_display_timing" "setres applies generated timing"
assert_file_contains "$shell_cmds_c" "config_save\\(\\)" "setres saves generated config"

echo "PASS: shell command registrations"
