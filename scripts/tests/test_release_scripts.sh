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
        fail "$label: '$path' does not contain pattern '$pattern'"
    fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_file_contains "$REPO_ROOT/.gitmodules" 'path = Caster' "Caster submodule path"
assert_file_contains "$REPO_ROOT/.gitmodules" 'url = https://gitlab.com/zephray/Caster.git/?' "Caster submodule URL"

fake_bin="$tmpdir/bin"
mkdir -p "$fake_bin"
for tool in stm32cubeide ssh scp; do
    printf '#!/usr/bin/env bash\nexit 0\n' >"$fake_bin/$tool"
    chmod +x "$fake_bin/$tool"
done

release_log="$tmpdir/release.log"
release_root="$tmpdir/release"

(
    export PATH="$fake_bin:$PATH"
    export DRY_RUN=1
    export RELEASE_DRY_RUN_LOG="$release_log"
    export RELEASE_ROOT="$release_root"
    "$REPO_ROOT/scripts/release.sh" --ise-host 192.168.56.101 0.1-task2
)

assert_file_contains "$release_log" "stm32cubeide .*org.eclipse.cdt.managedbuilder.core.headlessbuild .*glider_ec_rtos/Debug" "headless CubeIDE MCU build"
assert_file_contains "$release_log" "git -C .*/Glider submodule update --init --recursive" "recursive submodule update"
assert_file_contains "$release_log" "build_caster_ise_vm.sh --host 192.168.56.101 --source .*/Glider/Caster --out .*/0.1-task2/caster" "Caster VM build from submodule"
assert_file_contains "$release_log" "package_release.sh 0.1-task2 .*/0.1-task2" "release packaging"

metadata="$release_root/0.1-task2/metadata.txt"
[[ -f "$metadata" ]] || fail "release metadata was not generated"
assert_file_contains "$metadata" '^version=0.1-task2$' "metadata version"
assert_file_contains "$metadata" '^glider_revision=[0-9a-f]{40}$' "metadata Glider revision"
assert_file_contains "$metadata" '^caster_revision=[0-9a-f]{40}$' "metadata Caster revision"

no_tool_log="$tmpdir/no-tool-mcu.log"
(
    export PATH="/usr/bin:/bin"
    export DRY_RUN=1
    export RELEASE_DRY_RUN_LOG="$no_tool_log"
    "$REPO_ROOT/scripts/build_mcu.sh" 0.1-task2 "$tmpdir/no-tool-release"
)
assert_file_contains "$no_tool_log" "stm32cubeide .*org.eclipse.cdt.managedbuilder.core.headlessbuild .*glider_ec_rtos/Debug" "dry-run MCU build without STM32CubeIDE installed"

echo "PASS: Glider release dry-run"
