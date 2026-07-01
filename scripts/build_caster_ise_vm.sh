#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST=""
USER_NAME="ise"
SOURCE_DIR="$ROOT_DIR/Caster"
OUT_DIR="$ROOT_DIR/build/caster-ise-vm"
REMOTE_WORKDIR="~/caster_ise_build"
SHARED_FOLDER=""
DRY_RUN="${DRY_RUN:-0}"

SSH_OPTS=(
    -o HostkeyAlgorithms=+ssh-rsa,ssh-dss
    -o ControlMaster=auto
    -o ControlPersist=10m
    -o ControlPath=/tmp/caster-ise-vm-%r@%h:%p
)
SCP_OPTS=(
    -o HostkeyAlgorithms=+ssh-rsa,ssh-dss
    -o ControlMaster=auto
    -o ControlPersist=10m
    -o ControlPath=/tmp/caster-ise-vm-%r@%h:%p
)

usage() {
    cat <<'USAGE'
Usage: scripts/build_caster_ise_vm.sh --host HOST [options]

Build the Caster Spartan-6 bitstream through the official Xilinx ISE 14.7 VM.
The VM's old SSH stack requires:
  -o HostkeyAlgorithms=+ssh-rsa,ssh-dss

Options:
  --host HOST             ISE VM IP address or hostname. Required unless --help is used.
  --user USER             SSH username. Default: ise
  --source PATH           Local Caster source directory. Default: ./Caster
  --out PATH              Local output directory. Default: ./build/caster-ise-vm
  --remote-workdir PATH   Remote staging directory. Default: ~/caster_ise_build
  --shared-folder PATH    Remote path to a shared workspace for quick experiments.
                          When set, the script builds PATH/Caster in place on the VM.
  --dry-run               Print commands instead of running them.
  --help                  Show this help.

The reproducible path copies a source archive to the VM with scp, runs
rtl/spartan6/par/ise_flow.sh remotely, and copies fpga.bit, build.log,
ipcore.log, build.status, and reports.tar.gz back to --out.
USAGE
}

die() {
    echo "error: $*" >&2
    exit 1
}

quote() {
    if [[ "$1" =~ ^[A-Za-z0-9_./:@=+,\~-]+$ ]]; then
        printf '%s' "$1"
    else
        printf "'%s'" "${1//\'/\'\\\'\'}"
    fi
}

print_cmd() {
    printf '%s' "$1"
    shift
    for arg in "$@"; do
        printf ' %s' "$(quote "$arg")"
    done
    printf '\n'
}

run_cmd() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        print_cmd "$@"
    else
        "$@"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
    --host)
        [[ $# -ge 2 ]] || die "--host requires a value"
        HOST="$2"
        shift 2
        ;;
    --user)
        [[ $# -ge 2 ]] || die "--user requires a value"
        USER_NAME="$2"
        shift 2
        ;;
    --source)
        [[ $# -ge 2 ]] || die "--source requires a value"
        SOURCE_DIR="$2"
        shift 2
        ;;
    --out)
        [[ $# -ge 2 ]] || die "--out requires a value"
        OUT_DIR="$2"
        shift 2
        ;;
    --remote-workdir)
        [[ $# -ge 2 ]] || die "--remote-workdir requires a value"
        REMOTE_WORKDIR="$2"
        shift 2
        ;;
    --shared-folder)
        [[ $# -ge 2 ]] || die "--shared-folder requires a value"
        SHARED_FOLDER="$2"
        shift 2
        ;;
    --dry-run)
        DRY_RUN=1
        shift
        ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        die "unknown argument: $1"
        ;;
    esac
done

[[ -n "$HOST" ]] || die "--host is required"

REMOTE="$USER_NAME@$HOST"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
REMOTE_RUN_DIR="$REMOTE_WORKDIR/run-$RUN_ID"

if [[ -n "$SHARED_FOLDER" ]]; then
    REMOTE_CASTER_DIR="${SHARED_FOLDER%/}/Caster"
    REMOTE_CMD="cd $(quote "$REMOTE_CASTER_DIR")/rtl/spartan6/par && ./build.sh"
    run_cmd ssh "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_CMD"
    echo "Shared-folder build leaves artifacts in $REMOTE_CASTER_DIR/rtl/spartan6/par"
    exit 0
fi

[[ -d "$SOURCE_DIR" ]] || die "source directory does not exist: $SOURCE_DIR"
[[ -f "$SOURCE_DIR/rtl/spartan6/par/build.sh" ]] || die "missing Caster build script: $SOURCE_DIR/rtl/spartan6/par/build.sh"

mkdir -p "$OUT_DIR"

ARCHIVE=""
cleanup() {
    if [[ -n "$ARCHIVE" && -f "$ARCHIVE" ]]; then
        rm -f "$ARCHIVE"
    fi
}
trap cleanup EXIT

ARCHIVE="$(mktemp /tmp/caster-src.XXXXXX.tar.gz)"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "tar -C $(quote "$SOURCE_DIR") --exclude .git -czf $(quote "$ARCHIVE") ."
else
    tar -C "$SOURCE_DIR" --exclude .git -czf "$ARCHIVE" .
fi

run_cmd ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p $(quote "$REMOTE_RUN_DIR")"
run_cmd scp "${SCP_OPTS[@]}" "$ARCHIVE" "$REMOTE:$REMOTE_RUN_DIR/caster-src.tar.gz"

REMOTE_RUN_DIR_Q="$(quote "$REMOTE_RUN_DIR")"
REMOTE_BUILD_CMD=$(cat <<REMOTE_BUILD_EOF
set -e
cd $REMOTE_RUN_DIR_Q
mkdir -p src out
tar xzf caster-src.tar.gz -C src
cd src/rtl/spartan6/par
./clean.sh >/dev/null 2>&1 || true
if [ -z "\${XILINX:-}" ]; then
    . /opt/Xilinx/14.7/ISE_DS/settings64.sh
fi
ipcore_status=0
if [ ! -f ../ipcore_dir/vi_fifo.v ] || [ ! -f ../ipcore_dir/bi_fifo.v ] || [ ! -f ../ipcore_dir/bo_fifo.v ] || [ ! -f ../ipcore_dir/chipscope_icon.v ] || [ ! -f ../ipcore_dir/chipscope_ila.v ]; then
    printf '%s\n' 'project open ../caster.xise' 'process run "Regenerate All Cores"' 'exit' > regenerate_cores.tcl
    set +e
    xtclsh regenerate_cores.tcl > $REMOTE_RUN_DIR_Q/out/ipcore.log 2>&1
    ipcore_status=\$?
    set -e
else
    printf '%s\n' 'CoreGen outputs already present' > $REMOTE_RUN_DIR_Q/out/ipcore.log
fi
if [ "\$ipcore_status" -ne 0 ]; then
    printf 'CoreGen failed with status %s\n' "\$ipcore_status" > $REMOTE_RUN_DIR_Q/out/build.log
    printf '%s\n' "\$ipcore_status" > $REMOTE_RUN_DIR_Q/out/build.status
    rm -rf $REMOTE_RUN_DIR_Q/out/reports
    mkdir -p $REMOTE_RUN_DIR_Q/out/reports
    tar -czf $REMOTE_RUN_DIR_Q/out/reports.tar.gz -C $REMOTE_RUN_DIR_Q/out reports
    ./clean.sh >/dev/null 2>&1 || true
    exit 0
fi
set +e
./ise_flow.sh > $REMOTE_RUN_DIR_Q/out/build.log 2>&1
build_status=\$?
set -e
if [ -f top.bit ]; then
    cp top.bit $REMOTE_RUN_DIR_Q/out/fpga.bit
fi
printf '%s\n' "\$build_status" > $REMOTE_RUN_DIR_Q/out/build.status
rm -rf $REMOTE_RUN_DIR_Q/out/reports
mkdir -p $REMOTE_RUN_DIR_Q/out/reports
for f in ise_flow_results.txt top.syr top_xst.xrpt top.bld top_ngdbuild.xrpt top_map.map top_map.mrp top_map.xrpt top_summary.xml top_usage.xml top.par top_pad.csv top_pad.txt top_par.xrpt top.twx top.bgn top.twr top.drc top_bitgen.xwbt usage_statistics_webtalk.html webtalk.log par_usage_statistics.html; do
    if [ -f "\$f" ]; then
        cp "\$f" $REMOTE_RUN_DIR_Q/out/reports/
    fi
done
tar -czf $REMOTE_RUN_DIR_Q/out/reports.tar.gz -C $REMOTE_RUN_DIR_Q/out reports
./clean.sh >/dev/null 2>&1 || true
exit 0
REMOTE_BUILD_EOF
)
run_cmd ssh "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_BUILD_CMD"

run_cmd scp "${SCP_OPTS[@]}" "$REMOTE:$REMOTE_RUN_DIR/out/ipcore.log" "$OUT_DIR/ipcore.log"
run_cmd scp "${SCP_OPTS[@]}" "$REMOTE:$REMOTE_RUN_DIR/out/build.log" "$OUT_DIR/build.log"
run_cmd scp "${SCP_OPTS[@]}" "$REMOTE:$REMOTE_RUN_DIR/out/build.status" "$OUT_DIR/build.status"
run_cmd scp "${SCP_OPTS[@]}" "$REMOTE:$REMOTE_RUN_DIR/out/reports.tar.gz" "$OUT_DIR/reports.tar.gz"

if [[ "$DRY_RUN" -eq 0 ]]; then
    BUILD_STATUS="$(cat "$OUT_DIR/build.status")"
    if [[ "$BUILD_STATUS" != "0" ]]; then
        die "Caster ISE build failed with status $BUILD_STATUS; see $OUT_DIR/build.log and $OUT_DIR/reports.tar.gz"
    fi
fi

run_cmd scp "${SCP_OPTS[@]}" "$REMOTE:$REMOTE_RUN_DIR/out/fpga.bit" "$OUT_DIR/fpga.bit"

echo "Caster ISE VM build output: $OUT_DIR"
