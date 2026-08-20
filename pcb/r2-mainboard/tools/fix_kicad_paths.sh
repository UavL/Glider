#!/usr/bin/env bash
# Repair KiCad's global footprint library table and its path variables.
#
# WHY THIS EXISTS -- docs/layout.md §9.
#
# `~/.config/kicad/10.0/fp-lib-table` held a single entry pointing at
#   /tmp/.mount_kicadremp4722615889122143643/share/kicad/template/fp-lib-table
# an AppImage mount point: a directory that exists only while an AppImage is
# running, under a name that changes every launch. It was written once from
# inside a running AppImage and has resolved to nothing ever since, which is why
# `Update PCB from Schematic` reported 305 missing footprints -- every one of
# them from a stock library, while every project-relative `footprints:` and
# `r2:` footprint resolved. It is also standing ask 3: the 305
# `footprint_link_issues` in every ERC run since WP1 are this same fault.
#
# KiCad now runs from an extracted AppDir via `AppRun`, so the paths are stable
# and can simply be written out absolutely -- which is what the *symbol* table
# already does, and why symbols never broke.
#
# It also sets KICAD10_FOOTPRINT_DIR and KICAD10_3DMODEL_DIR, which were unset
# (`kicad_common.json` had `"vars": null`). The second is the larger half of the
# empty 3D viewer: every stock footprint references its model through it.
#
# Safe to re-run. Backs up anything it replaces, and refuses to run while KiCad
# is open, because KiCad rewrites these files on exit and would undo the fix.

set -euo pipefail

KIROOT="${KIROOT:-$HOME/Apps/kicad-10.0.4}"
CFG="${CFG:-$HOME/.config/kicad/10.0}"
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '  %s\n' "$*"; }
die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# --- refuse to race KiCad ----------------------------------------------------
# Check the process NAME, not a command-line pattern: `pgrep -f` happily
# matches this script's own invocation and would refuse to ever run.
if pgrep -x kicad >/dev/null 2>&1; then
    die "KiCad is running. It rewrites these files on exit, so close it first."
fi

# --- locate the install ------------------------------------------------------
SHARE=""
for c in "$KIROOT/share/kicad" "$KIROOT/usr/share/kicad"; do
    [ -d "$c/footprints" ] && [ -d "$c/3dmodels" ] && { SHARE="$c"; break; }
done
[ -n "$SHARE" ] || die "no KiCad share dir with footprints+3dmodels under $KIROOT"
TEMPLATE="$SHARE/template/fp-lib-table"
[ -f "$TEMPLATE" ] || die "no template table at $TEMPLATE"
[ -d "$CFG" ] || die "no KiCad config dir at $CFG"

echo "KiCad share : $SHARE"
echo "config      : $CFG"
echo

# --- 1. the footprint library table -----------------------------------------
echo "1. fp-lib-table"
if [ -f "$CFG/fp-lib-table" ]; then
    cp -p "$CFG/fp-lib-table" "$CFG/fp-lib-table.bak-$STAMP"
    say "backed up -> fp-lib-table.bak-$STAMP"
    if grep -q '/tmp/\.mount_' "$CFG/fp-lib-table"; then
        say "confirmed: the old table points at a dead AppImage mount"
    fi
fi
sed "s|\${KICAD10_FOOTPRINT_DIR}|$SHARE/footprints|g" "$TEMPLATE" > "$CFG/fp-lib-table.new"

# every path it names must exist, or we have moved the problem rather than fixed it
missing=0
while IFS= read -r uri; do
    [ -d "$uri" ] || { printf '     MISSING %s\n' "$uri"; missing=$((missing+1)); }
done < <(grep -o '(uri "[^"]*"' "$CFG/fp-lib-table.new" | sed 's/(uri "//;s/"$//')
total=$(grep -c '(lib ' "$CFG/fp-lib-table.new")
[ "$missing" -eq 0 ] || die "$missing of $total library paths do not exist -- not installing"
mv "$CFG/fp-lib-table.new" "$CFG/fp-lib-table"
say "installed: $total libraries, all paths verified"

# --- 2. the path variables ---------------------------------------------------
echo
echo "2. path variables in kicad_common.json"
COMMON="$CFG/kicad_common.json"
if [ -f "$COMMON" ]; then
    cp -p "$COMMON" "$COMMON.bak-$STAMP"
    say "backed up -> kicad_common.json.bak-$STAMP"
else
    echo '{}' > "$COMMON"
fi
SHARE="$SHARE" python3 - "$COMMON" <<'PY'
import json, os, sys
p = sys.argv[1]
share = os.environ["SHARE"]
d = json.load(open(p))
env = d.setdefault("environment", {})
vars_ = env.get("vars") or {}          # it was literally null, not {}
vars_["KICAD10_FOOTPRINT_DIR"] = f"{share}/footprints"
vars_["KICAD10_3DMODEL_DIR"] = f"{share}/3dmodels"
vars_["KICAD10_SYMBOL_DIR"] = f"{share}/symbols"
env["vars"] = vars_
json.dump(d, open(p, "w"), indent=2)
for k in ("KICAD10_FOOTPRINT_DIR", "KICAD10_3DMODEL_DIR", "KICAD10_SYMBOL_DIR"):
    print(f"     {k} = {vars_[k]}")
PY

# --- 3. prove it ------------------------------------------------------------
echo
echo "3. verification"
for probe in Resistor_SMD/R_0402_1005Metric Capacitor_SMD/C_0402_1005Metric \
             Package_TO_SOT_SMD/SOT-23 Connector_USB/USB_C_Receptacle_HRO_TYPE-C-31-M-12; do
    lib="${probe%%/*}"; fp="${probe##*/}"
    if [ -f "$SHARE/footprints/$lib.pretty/$fp.kicad_mod" ]; then
        say "OK   $lib:$fp"
    else
        say "MISS $lib:$fp"
    fi
done
m3=$(ls "$SHARE/3dmodels" | wc -l)
say "OK   $m3 3D model libraries reachable"

cat <<'MSG'

Done. Now, in KiCad:
  1. reopen the project
  2. Tools -> Update PCB from Schematic (F8)
  3. python3 tools/check_pcb.py   -- presence should read 327 of 327

If footprints ever vanish again after a KiCad update, run this again: the
bad path is written by the AppImage, not by anything in this project.
MSG
