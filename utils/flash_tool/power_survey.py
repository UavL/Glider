# Install python3 hidapi and pyserial packages:
#   pip install hidapi pyserial
#
# If open_dev() raises OSError("open failed"), install 99-glider.rules (see
# that file for instructions) instead of running this with sudo -- sudo
# re-resolves python3's environment from root's, which can pick up an
# unrelated, incompatible package also importable as `hid`.
#
# Drives the device through its suspend states over the HID "Control"
# interface (same USBCMD_POWERDOWN/POWERUP path as flash.py --powerdown/
# --powerup) and reads the 'sensor' command's per-rail power breakdown back
# over the "Debug" CDC-ACM interface, to build a comparison table of power
# consumption across states.
#
# Requires the firmware to be built with -DGLIDER_DIAGNOSTIC_SHELL (see
# fw/User/shell/shell.c) so the 'sensor' shell command is present.
import argparse
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flash import open_dev, send_cmd, USBCMD_POWERDOWN, USBCMD_POWERUP, POWERDOWN_PARAMS

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Install python3 pyserial package: pip install pyserial", file=sys.stderr)
    raise

USB_VID = 0x1209
USB_PID = 0xAE86

PROMPT = "# "
STATE_ORDER = ["active", "retain", "retain-manual", "off"]

SENSOR_POWER_RE = re.compile(
    r"^(?P<label>[A-Za-z0-9 +]+):\s+(?P<cur>-?[\d.]+)\s*mW\s+"
    r"(?P<avg>-?[\d.]+)\s*mW\s+(?P<max>-?[\d.]+)\s*mW"
)
STATUS_STATE_RE = re.compile(r"state:\s*(\S+)")


def autodetect_port():
    for p in list_ports.comports():
        if p.vid == USB_VID and p.pid == USB_PID:
            return p.device
    return None


def open_shell(port, baud, timeout=2.0):
    ser = serial.Serial(port, baud, timeout=timeout)
    # Clear whatever's pending and get a clean prompt to sync against.
    ser.reset_input_buffer()
    ser.write(b"\r")
    time.sleep(0.2)
    ser.reset_input_buffer()
    return ser


def shell_cmd(ser, cmd, timeout=3.0):
    """Send a shell command, return its output lines with echo/prompt stripped.

    reset_input_buffer() just discarded any prompt left over from the
    previous exchange, so the only "# " this call will see is the fresh one
    printed after our command finishes -- wait for the buffer to end with
    it rather than counting occurrences.
    """
    ser.reset_input_buffer()
    ser.write(cmd.encode("ascii") + b"\r")
    deadline = time.time() + timeout
    buf = ""
    while time.time() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf += chunk.decode("ascii", errors="replace")
            if buf.endswith(PROMPT):
                break
    lines = buf.replace("\r", "").split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == cmd.strip() or stripped == PROMPT.strip():
            continue
        out.append(line)
    return out


def read_power_status(ser):
    lines = shell_cmd(ser, "power status")
    state = None
    for line in lines:
        m = STATUS_STATE_RE.search(line)
        if m:
            state = m.group(1)
            break
    return state


def wait_for_state(ser, expected, timeout=8.0, poll=0.3):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = read_power_status(ser)
        if last == expected:
            return last
        time.sleep(poll)
    print(f"  warning: timed out waiting for state '{expected}' (last seen: {last})",
          file=sys.stderr)
    return last


def read_sensor(ser):
    lines = shell_cmd(ser, "sensor")
    if any("Invalid command" in l for l in lines):
        raise RuntimeError(
            "The 'sensor' shell command isn't present in this firmware build. "
            "Rebuild with GLIDER_DIAGNOSTIC_SHELL defined "
            "(Project Properties > C/C++ Build > Settings > MCU GCC Compiler > "
            "Preprocessor) and reflash."
        )
    readings = {}
    for line in lines:
        m = SENSOR_POWER_RE.match(line.strip())
        if m:
            readings[m.group("label").strip()] = (
                float(m.group("cur")), float(m.group("avg")), float(m.group("max"))
            )
    return readings, lines


def hid_transition(h, powerdown=None, powerup=False):
    if powerup:
        send_cmd(h, USBCMD_POWERUP, 0, 0, 0, 0, 0, 0)
    else:
        send_cmd(h, USBCMD_POWERDOWN, POWERDOWN_PARAMS[powerdown], 0, 0, 0, 0, 0)


def goto_state(h, ser, state, settle):
    # retain/retain-manual/off requests are only consumed by the firmware
    # while it's active (see wait_for_retain_wake() in ui.c, which only
    # reacts to RESUME/SUSPEND while already suspended) -- bounce through
    # active first so every transition below is a single, unambiguous hop.
    hid_transition(h, powerup=True)
    wait_for_state(ser, "active", timeout=settle + 5.0)
    if state == "active":
        return
    time.sleep(0.5)
    hid_transition(h, powerdown=state)
    wait_for_state(ser, "suspended", timeout=settle + 5.0)


def sample_state(ser, samples, interval):
    final = None
    for i in range(samples):
        final, _ = read_sensor(ser)
        if i < samples - 1:
            time.sleep(interval)
    return final


def print_summary(results, states):
    labels = []
    for state in states:
        for label in results.get(state, {}):
            if label not in labels:
                labels.append(label)

    col = 14
    header = f"{'Rail (AVG mW)':16s}" + "".join(f"{s:>{col}s}" for s in states)
    print("\n" + header)
    print("-" * len(header))
    totals = {s: 0.0 for s in states}
    for label in labels:
        row = f"{label:16s}"
        for s in states:
            avg = results.get(s, {}).get(label, (0.0, 0.0, 0.0))[1]
            totals[s] += avg
            row += f"{avg:{col}.1f}"
        print(row)
    print("-" * len(header))
    print(f"{'TOTAL':16s}" + "".join(f"{totals[s]:{col}.1f}" for s in states))


def write_csv(results, states, path):
    labels = []
    for state in states:
        for label in results.get(state, {}):
            if label not in labels:
                labels.append(label)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rail_avg_mW"] + states)
        totals = {s: 0.0 for s in states}
        for label in labels:
            row = [label]
            for s in states:
                avg = results.get(s, {}).get(label, (0.0, 0.0, 0.0))[1]
                totals[s] += avg
                row.append(f"{avg:.1f}")
            w.writerow(row)
        w.writerow(["TOTAL"] + [f"{totals[s]:.1f}" for s in states])


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Survey Glider power consumption across suspend states."
    )
    parser.add_argument(
        "--port",
        help="Serial device for the shell console (e.g. /dev/ttyACM0). "
             "Auto-detected from the device's USB VID:PID if omitted.",
    )
    parser.add_argument("--baud", type=int, default=115200,
                         help="Ignored by the device (virtual CDC-ACM port) but "
                              "required by pyserial.")
    parser.add_argument("--settle", type=float, default=3.0,
                         help="Seconds to wait after a transition before sampling.")
    parser.add_argument("--samples", type=int, default=3,
                         help="'sensor' reads to take per state.")
    parser.add_argument("--interval", type=float, default=1.0,
                         help="Seconds between samples within a state.")
    parser.add_argument("--states", nargs="+", default=STATE_ORDER,
                         choices=STATE_ORDER,
                         help="Subset/order of states to test.")
    parser.add_argument("--csv", type=Path, help="Write a CSV summary to this path.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    port = args.port or autodetect_port()
    if not port:
        print("Could not auto-detect the device's CDC-ACM port; pass --port explicitly.",
              file=sys.stderr)
        return 1

    print("Opening HID control interface...")
    h = open_dev()
    print(f"Opening shell console on {port} @ {args.baud}...")
    ser = open_shell(port, args.baud)

    results = {}
    try:
        for state in args.states:
            print(f"\n=== {state} ===")
            goto_state(h, ser, state, args.settle)
            print(f"  settling {args.settle}s...")
            time.sleep(args.settle)
            final = sample_state(ser, args.samples, args.interval)
            results[state] = final
            for label, (cur, avg, mx) in final.items():
                print(f"  {label:12s} cur={cur:8.1f} mW  avg={avg:8.1f} mW  max={mx:8.1f} mW")
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    finally:
        print("\nResuming to active state...")
        hid_transition(h, powerup=True)
        wait_for_state(ser, "active", timeout=args.settle + 5.0)
        h.close()
        ser.close()

    print_summary(results, args.states)
    if args.csv:
        write_csv(results, args.states, args.csv)
        print(f"\nWrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
