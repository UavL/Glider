#!/usr/bin/env python3
"""Give the board's footprints 3D models it can actually find.

After `tools/fix_kicad_paths.sh` set `KICAD10_3DMODEL_DIR`, **311 of 327
footprints resolve on their own**. This deals with the rest, and it makes the
project self-contained while it is there: every model it uses ends up in
`3dmodels/` and is referenced by `${KIPRJMOD}`, so the 3D view works on any
machine that clones the repo.

**Three reasons a model was missing, and they need different answers.**

1. **A real model exists but the path is somebody else's machine.** `pcb_common`
   keeps 66 STEP files *next to* its footprints rather than in a `.3dshapes`
   directory, and several are referenced by absolute paths from the original
   author -- `J24`'s points at `/Users/wenting/Documents/projects/Enchanter/...`.
   These are copied into `3dmodels/` and re-pointed. **The model is the real
   part.**
2. **No model exists anywhere for that footprint.** `footprints:Xilinx_FTG256`
   is a `pcb_common` custom footprint whose model lived on the Modos author's
   KiCad 6 install -- hence `${KICAD6_3DMODEL_DIR}`, a variable nothing defines
   any more. KiCad's own library has no `Xilinx_FTG256` either. For these a
   **dimensionally matched stand-in** from KiCad's library is used, and every
   one is listed below with what matches and what does not.
3. **Nothing suitable exists at all.** Reported, not faked.

⚠ **A stand-in is for clearance and collision, not for identity.** The body
outline and height are right; the pin detail, markings and often the exact
pad-field are not. Do not read a stand-in as confirmation that the right part is
fitted -- that is what the BOM is for. `check_pcb.py` reports how many are in
use so the number never quietly becomes invisible.

Re-runnable. Backs the board up, refuses to run while KiCad is open. If a future
`Update PCB from Schematic` resets a footprint, run this again.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
PCB = PROJ / "r2.kicad_pcb"
DEST = PROJ / "3dmodels"
COMMON = PROJ.parent / "pcb_common" / "footprints.pretty"
KI3D = pathlib.Path.home() / "Apps/kicad-10.0.4/share/kicad/3dmodels"

# --- 1. real models, copied out of pcb_common so the project stands alone ----
# lib_id -> (source file in pcb_common, name to use in 3dmodels/)
REAL = {
    "footprints:HC-FPC-05-09-8RLTAG":
        ("FPC-SMD_8P-P0.50_HC-FPC-05-09-8RLTAG.step", None),
    "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12":
        # the file in pcb_common has a double space in its name, which is
        # exactly the sort of thing that breaks quietly on another filesystem
        ("HRO  TYPE-C-31-M-12.step", "HRO_TYPE-C-31-M-12.step"),
    "footprints:TFC-WPAPR-08": ("HY-TF1007B.STEP", None),
    "footprints:Xunpu_FPC-05F-50PH20_1x50-1MP_P0.50mm_Horizontal":
        ("FPC-SMD_50P-P0.50_FPC-05F-50PH20.step", None),
}

# --- 2. dimensional stand-ins from KiCad's own library ----------------------
# lib_id -> (path under 3dmodels/, what matches, what does not)
STANDIN = {
    "footprints:Xilinx_FTG256": (
        "Package_BGA.3dshapes/BGA-256_17.0x17.0mm_Layout16x16_P1.0mm_Ball0.5mm_Pad0.4mm_NSMD.step",
        "17.0 x 17.0 mm body, 16 x 16 balls, 1.0 mm pitch -- the FTG256's exact geometry",
        "generic BGA, no Xilinx marking"),
    "Package_DFN_QFN:WQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm": (
        "Package_DFN_QFN.3dshapes/Texas_RTW_WQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm.step",
        "4 x 4 mm body, 24 pins, 0.5 mm pitch", "exposed pad 2.7 vs 2.6 mm"),
    "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm": (
        "Package_DFN_QFN.3dshapes/DFN-8-1EP_2x2mm_P0.5mm_EP0.6x1.2mm.step",
        "2 x 2 mm body, 8 pins, 0.5 mm pitch", "exposed pad 0.6 vs 0.8 mm wide"),
    "Package_DFN_QFN:Texas_RWU0007A_VQFN-7_2x2mm_P0.5mm": (
        "Package_DFN_QFN.3dshapes/DFN-8-1EP_2x2mm_P0.5mm_EP0.6x1.2mm.step",
        "2 x 2 mm body, 0.5 mm pitch", "8 pins drawn where the part has 7"),
    "Package_DFN_QFN:Texas_RGV0016A_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm": (
        "Package_DFN_QFN.3dshapes/Texas_RSA_VQFN-16-1EP_4x4mm_P0.65mm_EP2.7x2.7mm.step",
        "4 x 4 mm body, 16 pins, 0.65 mm pitch", "exposed pad 2.7 vs 2.1 mm"),
    "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A": (
        "Button_Switch_SMD.3dshapes/SW_Push_1P1T_NO_CK_KMR2.step",
        "4.2 x 3.2 mm body, same actuator class", "different maker; check the "
        "actuator height against the enclosure rather than trusting this"),
    "r2:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm": (
        "Package_DFN_QFN.3dshapes/DFN-10-1EP_2x3mm_P0.5mm_EP0.64x2.4mm.step",
        "2 x 3 mm body, 10 pins, 0.5 mm pitch", "VSON-HR has no exposed pad"),
}

# --- 3. nothing suitable exists ---------------------------------------------
NONE_AVAILABLE = {
    "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm":
        "X1 -- KiCad ships no ASE-4Pin model and pcb_common has none",
    "Inductor_SMD:L_Taiyo-Yuden_NR-30xx":
        "L1 -- no NR-30xx model; Taiyo Yuden publish STEP on their site",
    "Connector_Molex:Molex_Pico-Lock_504050-0391_1x03-1MP_P1.50mm_Horizontal":
        "J2 -- only 1.25 mm PicoBlade models exist, a different connector. "
        "This one sits at the board edge, so a wrong body would mislead the "
        "enclosure check; Molex publish STEP for 504050",
    "r2:Texas_YFQ0012_DSBGA-12_1.91x1.39mm_Layout3x4_P0.4mm":
        "U53 -- 1.9 mm DSBGA, nothing dimensionally close; cosmetic at this size",
    "r2:SolderPads_1x03_P3.50mm_Wire":
        "J25 -- bare copper pads, correctly has no model",
}


def fp_blocks(text: str):
    for m in re.finditer(r"\n\t\(footprint ", text):
        i = m.start() + 1
        d, j = 0, i
        while True:
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        yield i, j + 1


def set_model(blk: str, path: str) -> str:
    """Replace every (model ...) with exactly one pointing at `path`."""
    out, d, i = [], 0, 0
    while True:
        k = blk.find("\n\t\t(model ", i)
        if k < 0:
            out.append(blk[i:]); break
        out.append(blk[i:k])
        d, j = 0, k + 1
        while True:
            if blk[j] == "(":
                d += 1
            elif blk[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        i = j + 1
    stripped = "".join(out)
    model = (f'\n\t\t(model "{path}"\n\t\t\t(offset (xyz 0 0 0))\n'
             f'\t\t\t(scale (xyz 1 1 1))\n\t\t\t(rotate (xyz 0 0 0))\n\t\t)')
    k = stripped.rstrip().rfind("\n\t)")
    return stripped[:k] + model + stripped[k:]


def main() -> int:
    if not PCB.exists():
        print(f"{PCB.name} does not exist yet."); return 1
    if subprocess.run(["pgrep", "-x", "kicad"], capture_output=True).returncode == 0 \
            or list(PROJ.glob("~*.lck")):
        print("FAIL: KiCad is open. Close it first."); return 1

    DEST.mkdir(exist_ok=True)
    text = PCB.read_text()
    copied, applied, standins, left = [], 0, 0, []

    # copy the real models out of pcb_common
    for lib, (src, rename) in REAL.items():
        s = COMMON / src
        if not s.exists():
            left.append(f"{lib}: {src} is not in pcb_common"); continue
        dst = DEST / (rename or src)
        if not dst.exists() or dst.stat().st_size != s.stat().st_size:
            shutil.copy2(s, dst)
            copied.append(dst.name)

    edits = []
    for i, j in fp_blocks(text):
        blk = text[i:j]
        lib = re.search(r'footprint "([^"]+)"', blk).group(1)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        ref = ref.group(1) if ref else "?"
        if lib in REAL:
            src, rename = REAL[lib]
            p = f"${{KIPRJMOD}}/3dmodels/{rename or src}"
            if f'"{p}"' not in blk:
                edits.append((i, j, set_model(blk, p))); applied += 1
        elif lib in STANDIN:
            rel = STANDIN[lib][0]
            if not (KI3D / rel).exists():
                left.append(f"{ref} {lib}: stand-in {rel} is not installed"); continue
            p = "${KICAD10_3DMODEL_DIR}/" + rel
            if f'"{p}"' not in blk:
                edits.append((i, j, set_model(blk, p))); standins += 1
        elif lib.startswith("r2:"):
            # Our own footprints: take whatever the library file says. A
            # footprint edited in the library does NOT propagate to a board
            # that already has it placed, so X2 kept the model-less copy it
            # was imported with long after the generator started emitting one.
            src = PROJ / "r2.pretty" / (lib.split(":", 1)[1] + ".kicad_mod")
            want = re.search(r'\(model "([^"]+)"', src.read_text()) if src.exists() else None
            if want and f'"{want.group(1)}"' not in blk:
                edits.append((i, j, set_model(blk, want.group(1)))); applied += 1
            elif not want and lib in NONE_AVAILABLE:
                left.append(f"{ref:5s} {NONE_AVAILABLE[lib]}")
        elif lib in NONE_AVAILABLE:
            left.append(f"{ref:5s} {NONE_AVAILABLE[lib]}")

    for i, j, blk in sorted(edits, reverse=True):
        text = text[:i] + blk + text[j:]

    if edits:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(PCB, PCB.with_suffix(f".kicad_pcb.bak-{stamp}"))
        PCB.write_text(text)

    print(f"copied into 3dmodels/ : {len(copied)}  {copied}")
    print(f"real models applied   : {applied}")
    print(f"dimensional stand-ins : {standins}   ⚠ see the table in this file")
    print(f"still without a model : {len(set(left))}")
    for s in sorted(set(left)):
        print(f"    {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
