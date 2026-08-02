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

assert_file_contains "$shell_c" "SHELL_FUNC\\( shell_caster \\);" "caster handler declaration"
assert_file_contains "$shell_c" "SHELL_HELP\\( caster \\);" "caster help declaration"
assert_file_contains "$shell_c" "\\{ \"caster\", shell_caster \\}" "caster command registration"
assert_file_contains "$shell_c" "SHELL_INFO\\( caster \\)" "caster help registration"
assert_file_contains "$shell_cmds_c" "const char shell_help_caster\\[\\]" "caster help text"
assert_file_contains "$shell_cmds_c" "void shell_caster\\(shell_context_t \\*ctx, int argc, char \\*\\*argv\\)" "caster implementation"
assert_file_contains "$shell_cmds_c" "caster_set_mono_frames" "caster frames writes the drive length"
assert_file_contains "$shell_cmds_c" "caster_get_mono_frames" "caster frames reads back the drive length"

# The caster/damage commands live behind the diagnostic-shell symbol; make sure
# they were added inside that block rather than to the always-on command set.
if ! awk '/#ifdef GLIDER_DIAGNOSTIC_SHELL/{d=1} /#endif/{d=0} d && /\{ "caster", shell_caster \}/{found=1} END{exit !found}' "$shell_c"; then
    fail "caster command registration is not inside GLIDER_DIAGNOSTIC_SHELL"
fi

echo "PASS: shell command registrations"
