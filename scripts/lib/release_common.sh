#!/usr/bin/env bash

RELEASE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_REPO_ROOT="$(cd "$RELEASE_LIB_DIR/../.." && pwd)"

repo_root() {
    echo "$RELEASE_REPO_ROOT"
}

log() {
    echo "[$(date +%H:%M:%S)] $*" >&2
}

die() {
    echo "error: $*" >&2
    exit 1
}

quote_arg() {
    local arg="$1"

    if [[ "$arg" =~ ^[A-Za-z0-9_./:=,+@%-]+$ ]]; then
        printf '%s' "$arg"
    else
        printf "'%s'" "${arg//\'/\'\\\'\'}"
    fi
}

format_cmd() {
    local first=1
    local arg

    for arg in "$@"; do
        if [[ "$first" -eq 0 ]]; then
            printf ' '
        fi
        quote_arg "$arg"
        first=0
    done
}

run_cmd() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        local rendered
        rendered="$(format_cmd "$@")"
        echo "+ $rendered" >&2
        if [[ -n "${RELEASE_DRY_RUN_LOG:-}" ]]; then
            echo "$rendered" >>"$RELEASE_DRY_RUN_LOG"
        fi
        return 0
    fi

    log "+ $(format_cmd "$@")"
    "$@"
}

run_logged_step() {
    local label="$1"
    local logfile="$2"
    shift 2

    mkdir -p "$(dirname "$logfile")"
    log "Starting $label; log: $logfile"
    printf '[%s] + %s\n' "$(date +%H:%M:%S)" "$(format_cmd "$@")" >"$logfile"
    if [[ "${DRY_RUN:-0}" == "1" && -n "${RELEASE_DRY_RUN_LOG:-}" ]]; then
        format_cmd "$@" >>"$RELEASE_DRY_RUN_LOG"
        printf '\n' >>"$RELEASE_DRY_RUN_LOG"
    fi

    set +e
    "$@" 2>&1 | tee -a "$logfile"
    local status="${PIPESTATUS[0]}"
    set -e

    if [[ "$status" -ne 0 ]]; then
        die "$label failed; see '$logfile'"
    fi
    log "Finished $label"
}

prepare_release_dir() {
    local release_dir="$1"
    local force="${2:-0}"

    if [[ -e "$release_dir" ]]; then
        [[ -d "$release_dir" ]] || die "release output '$release_dir' exists and is not a directory"
        if find "$release_dir" -mindepth 1 -print -quit | grep -q .; then
            if [[ "$force" == "1" ]]; then
                if [[ "${DRY_RUN:-0}" == "1" ]]; then
                    log "+ rm -rf $(quote_arg "$release_dir")"
                else
                    rm -rf "$release_dir"
                fi
            else
                die "release output '$release_dir' already exists and is not empty; pass --force or set RELEASE_FORCE=1"
            fi
        fi
    fi

    mkdir -p "$release_dir"
}

validate_release_version() {
    local version="$1"

    [[ "$version" =~ ^[A-Za-z0-9._+-]+$ ]] || \
        die "invalid version '$version'; use only letters, digits, '.', '_', '+', and '-'"
}

require_cmd() {
    local cmd="$1"
    command -v "$cmd" >/dev/null 2>&1 || die "required command '$cmd' not found"
}

find_first_executable() {
    local root="$1"
    local name="$2"

    [[ -d "$root" ]] || return 1
    find "$root" -type f -name "$name" -perm -111 2>/dev/null | sort | tail -n 1
}

find_stm32cubeide_executable() {
    local candidate
    local ide_path

    if [[ -n "${STM32CUBEIDE_BIN:-}" ]]; then
        if [[ -x "$STM32CUBEIDE_BIN" ]]; then
            echo "$STM32CUBEIDE_BIN"
            return 0
        fi
        command -v "$STM32CUBEIDE_BIN" 2>/dev/null && return 0
        return 1
    fi

    if command -v stm32cubeide >/dev/null 2>&1; then
        command -v stm32cubeide
        return 0
    fi

    for candidate in \
        "$HOME"/st/stm32cubeide* \
        "$HOME"/STM32CubeIDE* \
        /opt/st/stm32cubeide* \
        /opt/STM32CubeIDE*
    do
        [[ -d "$candidate" ]] || continue
        ide_path="$(find_first_executable "$candidate" stm32cubeide || true)"
        if [[ -n "$ide_path" ]]; then
            echo "$ide_path"
            return 0
        fi
    done

    return 1
}

check_submodules() {
    local status
    local path
    local rest

    while read -r status path rest; do
        [[ -n "${status:-}" ]] || continue
        case "$status" in
            -*) die "submodule '$path' is not initialized; run git submodule update --init --recursive" ;;
            +*) die "submodule '$path' is checked out at a different commit than recorded by the superproject" ;;
            U*) die "submodule '$path' has merge conflicts" ;;
        esac
    done < <(git -C "$(repo_root)" submodule status --recursive)
}

ensure_submodules() {
    run_cmd git -C "$(repo_root)" submodule update --init --recursive
    if [[ "${DRY_RUN:-0}" != "1" ]]; then
        check_submodules
    fi
}

write_build_metadata() {
    local output="$1"
    local version="$2"
    local caster_dir
    local build_time

    validate_release_version "$version"
    caster_dir="$(repo_root)/Caster"
    [[ -d "$caster_dir" ]] || die "Caster submodule is missing at '$caster_dir'"
    build_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    {
        echo "version=$version"
        echo "build_time_utc=$build_time"
        echo "glider_revision=$(git -C "$(repo_root)" rev-parse HEAD)"
        echo "caster_revision=$(git -C "$caster_dir" rev-parse HEAD)"
        echo "glider_dirty=$(git -C "$(repo_root)" status --short --untracked-files=no | grep -q . && echo yes || echo no)"
        echo "caster_dirty=$(git -C "$caster_dir" status --short --untracked-files=no | grep -q . && echo yes || echo no)"
    } >"$output"
}
