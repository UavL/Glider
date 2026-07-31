#!/usr/bin/env python3
"""Idle/wake manager for using Glider's retain mode as an e-reader reading state.

Runs on the host that drives the panel (e.g. the Raspberry Pi). It watches the
input devices you read with (page-turn buttons, keyboard, touchscreen) and:

  * on any input while the panel is in a low-power state, sends USBCMD_POWERUP
    so the rails come back up while your reader renders the next page;
  * after --idle seconds of no input, sends USBCMD_POWERDOWN "retain-manual"
    (image kept on the panel, no autonomous wake -- matches the firmware that
    stops the EPDC during retain);
  * after --deep-idle seconds, escalates to a full "off" standby (~0.19 W).

This is the host half of the tiered power strategy; the firmware half is the
retain/off suspend states. The HID plumbing is imported from flash.py, so keep
this file next to it.

Requirements: the `hidapi` and `evdev` PyPI packages (`pip install hidapi
evdev`), plus permission to open the HID device (udev rule 99-glider.rules) and
the input devices (typically the `input` group).

Examples:
  python3 retain_hook.py --list                 # show input devices
  python3 retain_hook.py --dry-run              # print transitions, send nothing
  python3 retain_hook.py --device /dev/input/event0 --idle 45 --deep-idle 600
"""

import argparse
import select
import sys
import time
from datetime import datetime

try:
    from flash import (open_dev, send_cmd, USBCMD_POWERUP, USBCMD_POWERDOWN,
                       POWERDOWN_PARAMS)
except ImportError as exc:
    print(f"Could not import HID helpers from flash.py: {exc}\n"
          "Run this from the utils/flash_tool directory (or add it to "
          "PYTHONPATH), and install the 'hidapi' package.", file=sys.stderr)
    raise SystemExit(1)

try:
    import evdev
except ImportError:
    print("The 'evdev' package is required: pip install evdev", file=sys.stderr)
    raise SystemExit(1)

# Believed device power state. The host cannot observe the panel directly (the
# user might press a board button), so this is best-effort: a wrong guess only
# costs a redundant POWERUP/POWERDOWN, which the firmware treats as a no-op.
STATE_ACTIVE = "active"
STATE_RETAINED = "retained"
STATE_OFF = "off"

RESCAN_INTERVAL_S = 5.0     # re-scan for (re)connected input devices
RECONNECT_BACKOFF_S = 5.0   # wait before retrying a dropped HID device

# Event types that count as user activity.
ACTIVITY_TYPES = (evdev.ecodes.EV_KEY, evdev.ecodes.EV_REL, evdev.ecodes.EV_ABS)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def list_devices():
    found = False
    for path in sorted(evdev.list_devices()):
        try:
            dev = evdev.InputDevice(path)
        except OSError as exc:
            log(f"{path}: {exc}")
            continue
        found = True
        print(f"{path}\t{dev.name}")
        dev.close()
    if not found:
        print("No input devices readable (need the 'input' group?)",
              file=sys.stderr)


class Hid:
    """Lazily-opened HID handle that reconnects across device drop-outs."""

    def __init__(self, dry_run):
        self.dry_run = dry_run
        self._h = None
        self._next_retry = 0.0

    def _ensure(self):
        if self.dry_run or self._h is not None:
            return self._h is not None or self.dry_run
        now = time.monotonic()
        if now < self._next_retry:
            return False
        try:
            self._h = open_dev()
        except OSError as exc:
            self._next_retry = now + RECONNECT_BACKOFF_S
            log(f"HID open failed ({exc}); retrying later")
            return False
        return True

    def _send(self, cmd, param):
        if self.dry_run:
            return True
        if not self._ensure():
            return False
        try:
            send_cmd(self._h, cmd, param, 0, 0, 0, 0, 0)
            return True
        except Exception as exc:  # flash.send_cmd raises bare Exception on NAK
            log(f"HID send failed ({exc}); will reconnect")
            try:
                self._h.close()
            except Exception:
                pass
            self._h = None
            self._next_retry = time.monotonic() + RECONNECT_BACKOFF_S
            return False

    def powerup(self):
        return self._send(USBCMD_POWERUP, 0)

    def powerdown(self, kind):
        return self._send(USBCMD_POWERDOWN, POWERDOWN_PARAMS[kind])

    def close(self):
        if self._h is not None:
            try:
                self._h.close()
            except Exception:
                pass
            self._h = None


def open_input_devices(paths):
    devices = {}
    for path in paths:
        try:
            dev = evdev.InputDevice(path)
            devices[dev.fd] = dev
        except OSError as exc:
            log(f"{path}: {exc}")
    return devices


def resolve_paths(explicit):
    if explicit:
        return list(explicit)
    # Default: every readable input device. Reading is passive (no grab), so
    # watching extras is harmless.
    return sorted(evdev.list_devices())


def run(args):
    hid = Hid(args.dry_run)
    wanted_paths = resolve_paths(args.device)
    if not wanted_paths:
        log("No input devices to watch; pass --device or fix permissions.")
        return 1

    devices = open_input_devices(wanted_paths)
    log(f"Watching {len(devices)} device(s); idle={args.idle}s "
        f"deep-idle={args.deep_idle or 'off'}s "
        f"{'(dry-run)' if args.dry_run else ''}")

    state = STATE_ACTIVE
    last_input = time.monotonic()
    last_rescan = last_input

    while True:
        now = time.monotonic()

        # Compute the next idle deadline so select() wakes us to act on it.
        deadlines = []
        if state == STATE_ACTIVE:
            deadlines.append(last_input + args.idle)
        elif state == STATE_RETAINED and args.deep_idle:
            deadlines.append(last_input + args.deep_idle)
        deadlines.append(last_rescan + RESCAN_INTERVAL_S)
        timeout = max(0.0, min(deadlines) - now)

        try:
            readable, _, _ = select.select(list(devices), [], [], timeout)
        except OSError:
            readable = []

        now = time.monotonic()
        activity = False
        for fd in readable:
            dev = devices.get(fd)
            if dev is None:
                continue
            try:
                for event in dev.read():
                    if event.type in ACTIVITY_TYPES:
                        if not (event.type == evdev.ecodes.EV_KEY and
                                event.value == 0):  # ignore key-up
                            activity = True
            except OSError:
                log(f"{dev.path} disconnected")
                try:
                    dev.close()
                except Exception:
                    pass
                del devices[fd]

        if activity:
            last_input = now
            if state != STATE_ACTIVE:
                log(f"input -> waking from {state}")
                hid.powerup()
                state = STATE_ACTIVE

        # Idle transitions.
        if state == STATE_ACTIVE and (now - last_input) >= args.idle:
            log(f"idle {args.idle}s -> retain")
            if hid.powerdown("retain-manual"):
                state = STATE_RETAINED
        elif (state == STATE_RETAINED and args.deep_idle and
                (now - last_input) >= args.deep_idle):
            log(f"idle {args.deep_idle}s -> off")
            if hid.powerdown("off"):
                state = STATE_OFF

        # Periodic re-scan to pick up (re)connected devices.
        if (now - last_rescan) >= RESCAN_INTERVAL_S:
            last_rescan = now
            current = set(dev.path for dev in devices.values())
            for path in resolve_paths(args.device):
                if path not in current:
                    try:
                        dev = evdev.InputDevice(path)
                        devices[dev.fd] = dev
                        log(f"{path} connected")
                    except OSError:
                        pass


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Drive Glider retain/off from host input activity.")
    p.add_argument("--device", action="append", metavar="PATH",
                   help="Input device to watch (repeatable). Default: all.")
    p.add_argument("--idle", type=float, default=60.0,
                   help="Seconds of no input before entering retain (default 60).")
    p.add_argument("--deep-idle", type=float, default=600.0,
                   help="Seconds before escalating retain to full off "
                        "(default 600; 0 disables).")
    p.add_argument("--dry-run", action="store_true",
                   help="Log transitions without sending HID commands.")
    p.add_argument("--list", action="store_true",
                   help="List input devices and exit.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.list:
        list_devices()
        return 0
    try:
        return run(args) or 0
    except KeyboardInterrupt:
        log("stopping")
        return 0


if __name__ == "__main__":
    sys.exit(main())
