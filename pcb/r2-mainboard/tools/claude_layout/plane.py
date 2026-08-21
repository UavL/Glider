#!/usr/bin/env python3
"""Ground planes, the two HV island cut-outs, and stitching vias.

`GND` is 345 pads and 344 of the 1047 ratsnest edges. Routing it as tracks
would be both enormous and wrong: `layout.md` §7.2 wants the DDR3 bus over one
continuous `In1.Cu`, which only exists if `In1.Cu` is a plane. So `GND` is
poured, not routed --

    F.Cu    GND pour, so SMD ground pads connect where they sit
    In1.Cu  the solid plane; the continuous reference for everything
    B.Cu    GND pour
    + a stitching via grid tying the outer pours to the plane

⚠ **`layout.md` §7.1 / `epd-port.md` §11.1.** `U9` (`LGS5145`) and `U26`
(`LGS5145`) are inverting buck-boosts whose pin 2 is labelled `GND` and sits at
**-VGL ~ -20 V** and **-VN ~ -15 V**. Connecting either to the ground plane
destroys the part. Each gets a keep-out over its courtyard that forbids
*copper pour* on every layer -- the plane is cut away beneath it -- while still
allowing tracks and vias, because the part's own signals have to reach it.

The keep-outs carry no net. `check_pcb.py` refuses a copper zone on `-VGL` or
`-VN`, and nothing here creates one.
"""
from __future__ import annotations

import uuid as _uuid

HV_ISLANDS = [
    ("U9", "-VGL", "LGS5145 inverting buck-boost: pin 2 sits at about -20 V"),
    ("U26", "-VN", "LGS5145 inverting buck-boost: pin 2 sits at about -15 V"),
]
ISLAND_MARGIN = 1.5      # mm around the courtyard


def _uid():
    return str(_uuid.uuid4())


def _pts(poly):
    return " ".join("(xy %s %s)" % (round(x, 4), round(y, 4)) for x, y in poly)


def gnd_zone(layer, poly, name="GND"):
    return (
        '\n\t(zone\n\t\t(net "GND")\n\t\t(layer "%s")\n\t\t(uuid "%s")\n'
        '\t\t(name "%s")\n\t\t(hatch edge 0.5)\n\t\t(priority 0)\n'
        # `connect_pads yes` is a solid connection, not a thermal relief:
        # thermal spokes on this board's 0402 ground pads came out starved
        # (31 violations), and reflow does not need the relief that hand
        # soldering does. `island_removal_mode 0` is "always remove", which
        # clears the 149 isolated pour fragments that mode 1 kept.
        '\t\t(connect_pads yes\n\t\t\t(clearance 0.2)\n\t\t)\n'
        '\t\t(min_thickness 0.25)\n'
        '\t\t(fill yes\n\t\t\t(thermal_gap 0.3)\n'
        '\t\t\t(thermal_bridge_width 0.4)\n\t\t\t(island_removal_mode 0)\n'
        '\t\t)\n'
        '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n\t)\n'
        % (layer, _uid(), name, _pts(poly)))


def keepout_zone(poly, name):
    """A rule area that forbids copper pour but still allows tracks and vias."""
    return (
        '\n\t(zone\n\t\t(net 0)\n\t\t(net_name "")\n'
        '\t\t(layers "F.Cu" "In1.Cu" "In2.Cu" "B.Cu")\n\t\t(uuid "%s")\n'
        '\t\t(name "%s")\n\t\t(hatch edge 0.5)\n'
        '\t\t(keepout\n\t\t\t(tracks allowed)\n\t\t\t(vias allowed)\n'
        '\t\t\t(pads allowed)\n\t\t\t(copperpour not_allowed)\n'
        '\t\t\t(footprints allowed)\n\t\t)\n'
        '\t\t(placement\n\t\t\t(enabled no)\n\t\t\t(sheetname "")\n\t\t)\n'
        '\t\t(fill\n\t\t\t(thermal_gap 0.5)\n'
        '\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n'
        '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n\t)\n'
        % (_uid(), name, _pts(poly)))


def via(x, y, dia=0.6, drill=0.3, net="GND"):
    return ('\n\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n'
            '\t\t(layers "F.Cu" "B.Cu")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
            % (round(x, 4), round(y, 4), dia, drill, net, _uid()))


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
