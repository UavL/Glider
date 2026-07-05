#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST=""
USER_NAME="ise"
SOURCE_DIR="$ROOT_DIR/Caster"
OUT_DIR="$ROOT_DIR/build/caster-ise-vm"
REMOTE_WORKDIR="~/caster_ise_build"
SHARED_FOLDER=""
VARIANTS=("8bit-mono")
SSH_PASSWORD="${GLIDER_ISE_VM_PASSWORD:-xilinx}"
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
  --variant VARIANT       Build variant: 8bit-mono, 8bit-k3, 16bit-mono, or
                          16bit-k3. Default: 8bit-mono
  --variants LIST         Comma-separated build variants. When more than one
                          variant is listed, --out receives one subdirectory
                          per variant.
  --ssh-password PASSWORD SSH password passed through sshpass. Default: xilinx
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

split_variants() {
    local value="$1"
    IFS=',' read -r -a VARIANTS <<<"$value"
    [[ "${#VARIANTS[@]}" -gt 0 ]] || die "--variants requires at least one variant"
}

variant_list_for_shell() {
    local first=1
    local variant

    for variant in "${VARIANTS[@]}"; do
        if [[ "$first" -eq 0 ]]; then
            printf ' '
        fi
        printf '%s' "$variant"
        first=0
    done
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
    --variant)
        [[ $# -ge 2 ]] || die "--variant requires a value"
        VARIANT="$2"
        VARIANTS=("$2")
        shift 2
        ;;
    --variants)
        [[ $# -ge 2 ]] || die "--variants requires a value"
        split_variants "$2"
        shift 2
        ;;
    --ssh-password)
        [[ $# -ge 2 ]] || die "--ssh-password requires a value"
        SSH_PASSWORD="$2"
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
for variant in "${VARIANTS[@]}"; do
    case "$variant" in
        8bit-mono|8bit-k3|16bit-mono|16bit-k3) ;;
        *) die "unknown Caster build variant: $variant" ;;
    esac
done

if [[ "$DRY_RUN" -eq 0 && -n "$SSH_PASSWORD" ]] && ! command -v sshpass >/dev/null 2>&1; then
    die "sshpass is required for password-based ISE VM access"
fi

SSH_CMD=(ssh)
SCP_CMD=(scp)
if [[ -n "$SSH_PASSWORD" ]]; then
    SSH_CMD=(sshpass -p "$SSH_PASSWORD" ssh)
    SCP_CMD=(sshpass -p "$SSH_PASSWORD" scp)
fi

REMOTE="$USER_NAME@$HOST"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
REMOTE_RUN_DIR="$REMOTE_WORKDIR/run-$RUN_ID"

if [[ -n "$SHARED_FOLDER" ]]; then
    [[ "${#VARIANTS[@]}" -eq 1 ]] || die "--shared-folder supports one --variant at a time"
    REMOTE_CASTER_DIR="${SHARED_FOLDER%/}/Caster"
    REMOTE_CMD="cd $(quote "$REMOTE_CASTER_DIR")/rtl/spartan6/par && ./build.sh $(quote "${VARIANTS[0]}")"
    run_cmd "${SSH_CMD[@]}" "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_CMD"
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

run_cmd "${SSH_CMD[@]}" "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p $(quote "$REMOTE_RUN_DIR")"
run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$ARCHIVE" "$REMOTE:$REMOTE_RUN_DIR/caster-src.tar.gz"

REMOTE_RUN_DIR_Q="$(quote "$REMOTE_RUN_DIR")"
REMOTE_VARIANTS_Q="$(quote "$(variant_list_for_shell)")"
MULTI_VARIANT=0
if [[ "${#VARIANTS[@]}" -gt 1 ]]; then
    MULTI_VARIANT=1
fi
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
variants=$REMOTE_VARIANTS_Q
multi_variant=$MULTI_VARIANT
first_variant=\${variants%% *}
./write_build_config.sh "\$first_variant" ../../build_config.vh
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
    for variant in \$variants; do
        if [ "\$multi_variant" -eq 1 ]; then
            variant_out=$REMOTE_RUN_DIR_Q/out/\$variant
        else
            variant_out=$REMOTE_RUN_DIR_Q/out
    fi
    mkdir -p "\$variant_out"
    if [ "\$multi_variant" -eq 1 ]; then
        cp $REMOTE_RUN_DIR_Q/out/ipcore.log "\$variant_out/ipcore.log" 2>/dev/null || true
    fi
        printf 'CoreGen failed with status %s\n' "\$ipcore_status" > "\$variant_out/build.log"
        printf '%s\n' "\$ipcore_status" > "\$variant_out/build.status"
        rm -rf "\$variant_out/reports"
        mkdir -p "\$variant_out/reports"
        tar -czf "\$variant_out/reports.tar.gz" -C "\$variant_out" reports
    done
    ./clean.sh >/dev/null 2>&1 || true
    exit 0
fi
for variant in \$variants; do
    if [ "\$multi_variant" -eq 1 ]; then
        variant_out=$REMOTE_RUN_DIR_Q/out/\$variant
    else
        variant_out=$REMOTE_RUN_DIR_Q/out
    fi
    mkdir -p "\$variant_out"
    if [ "\$multi_variant" -eq 1 ]; then
        cp $REMOTE_RUN_DIR_Q/out/ipcore.log "\$variant_out/ipcore.log"
    fi
    ./clean.sh >/dev/null 2>&1 || true
    set +e
    ./ise_flow.sh "\$variant" > "\$variant_out/build.log" 2>&1
    build_status=\$?
    set -e
    if [ -f top.bit ]; then
        cp top.bit "\$variant_out/fpga.bit"
    fi
    printf '%s\n' "\$build_status" > "\$variant_out/build.status"
    rm -rf "\$variant_out/reports"
    mkdir -p "\$variant_out/reports"
    for f in ise_flow_results.txt top.syr top_xst.xrpt top.bld top_ngdbuild.xrpt top_map.map top_map.mrp top_map.xrpt top_summary.xml top_usage.xml top.par top_pad.csv top_pad.txt top_par.xrpt top.twx top.bgn top.twr top.drc top_bitgen.xwbt usage_statistics_webtalk.html webtalk.log par_usage_statistics.html; do
        if [ -f "\$f" ]; then
            cp "\$f" "\$variant_out/reports/"
        fi
    done
    tar -czf "\$variant_out/reports.tar.gz" -C "\$variant_out" reports
done
./clean.sh >/dev/null 2>&1 || true
exit 0
REMOTE_BUILD_EOF
)
run_cmd "${SSH_CMD[@]}" "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_BUILD_CMD"

for variant in "${VARIANTS[@]}"; do
    variant_out="$OUT_DIR"
    remote_out="$REMOTE_RUN_DIR/out"
    if [[ "$MULTI_VARIANT" -eq 1 ]]; then
        variant_out="$OUT_DIR/$variant"
        remote_out="$REMOTE_RUN_DIR/out/$variant"
    fi
    mkdir -p "$variant_out"
    run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$REMOTE:$remote_out/ipcore.log" "$variant_out/ipcore.log"
    run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$REMOTE:$remote_out/build.log" "$variant_out/build.log"
    run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$REMOTE:$remote_out/build.status" "$variant_out/build.status"
    run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$REMOTE:$remote_out/reports.tar.gz" "$variant_out/reports.tar.gz"

    if [[ "$DRY_RUN" -eq 0 ]]; then
        BUILD_STATUS="$(cat "$variant_out/build.status")"
        if [[ "$BUILD_STATUS" != "0" ]]; then
            die "Caster ISE build failed with status $BUILD_STATUS; see $variant_out/build.log and $variant_out/reports.tar.gz"
        fi
    fi

    run_cmd "${SCP_CMD[@]}" "${SCP_OPTS[@]}" "$REMOTE:$remote_out/fpga.bit" "$variant_out/fpga.bit"
done

echo "Caster ISE VM build output: $OUT_DIR"
