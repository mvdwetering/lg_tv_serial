#!/usr/bin/env python3
"""LG TV Serial Protocol Emulator

TCP server that emulates an LG TV's RS-232C serial protocol for integration testing.
Exposes the same interface as real hardware when accessed via socket://<host>:<port>.

Usage:
    python3 lgtv_emulator.py [--port PORT] [--host HOST] [--set-id ID]

Example:
    python3 lgtv_emulator.py --port 12345
    # Then point the integration at socket://localhost:12345
"""

import argparse
import asyncio
import curses
import re
import sys
import time
from dataclasses import dataclass

# ── Name tables ──────────────────────────────────────────────────────────────

ASPECT_RATIO_NAMES: dict[int, str] = {
    0x01: "4:3",
    0x02: "16:9",
    0x04: "Zoom",
    0x06: "Original",
    0x07: "14:9",
    0x09: "Just Scan",
    0x0B: "Full Wide",
}
ASPECT_RATIOS = [0x01, 0x02, 0x04, 0x06, 0x07, 0x09, 0x0B]

INPUT_NAMES: dict[int, str] = {
    0x00: "DTV",
    0x01: "CADTV",
    0x11: "CATV",
    0x20: "AV1",
    0x21: "AV2",
    0x40: "Component1",
    0x41: "Component2",
    0x60: "RGB",
    0x90: "HDMI1",
    0x91: "HDMI2",
    0x92: "HDMI3",
    0x93: "HDMI4",
}
INPUT_CYCLE = [0x00, 0x20, 0x21, 0x40, 0x41, 0x60, 0x90, 0x91, 0x92, 0x93]

ENERGY_SAVING_NAMES: dict[int, str] = {
    0x00: "Off",
    0x01: "Min",
    0x02: "Medium",
    0x03: "Max",
    0x04: "Auto",
    0x05: "Screen Off",
}
ENERGY_SAVING_CYCLE = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05]

ISM_METHOD_NAMES: dict[int, str] = {
    0x02: "Orbiter",
    0x04: "White Wash",
    0x08: "Normal",
    0x20: "Colour Wash",
}

CHANNEL_TYPE_NAMES: dict[int, str] = {
    0x00: "Analogue",
    0x10: "DTV",
    0x20: "Radio",
}

SCREEN_MUTE_NAMES: dict[int, str] = {
    0x00: "Off",
    0x01: "Screen mute",
    0x10: "Video mute",
}

MODE_3D_NAMES: dict[int, str] = {
    0x00: "On",
    0x01: "Off",
    0x02: "3D→2D",
    0x03: "2D→3D",
}

# Real LG TVs take ~15 seconds to boot after power-on and don't respond during this time
# (observed behavior: 3x 5-second timeouts before responding, suggesting ~15-17s boot time)
BOOT_DELAY = 15.0

# ── TV state ──────────────────────────────────────────────────────────────────

@dataclass
class TvState:
    # Commands from the protocol doc
    power: bool = False
    aspect_ratio: int = 0x02          # 16:9
    screen_mute: int = 0x00           # Off
    volume_mute: bool = False
    volume: int = 0x10                # 16
    contrast: int = 0x32              # 50
    brightness: int = 0x32
    color: int = 0x32
    tint: int = 0x32
    sharpness: int = 0x32
    osd: bool = True
    remote_lock: bool = False
    treble: int = 0x32
    bass: int = 0x32
    balance: int = 0x32
    color_temp: int = 0x32
    ism_method: int = 0x08            # Normal
    energy_saving: int = 0x00
    backlight: int = 0x32
    channel_high: int = 0x00
    channel_low: int = 0x01
    channel_type: int = 0x00          # Analogue
    programme_skip: bool = False
    input_source: int = 0x00          # DTV
    mode_3d: int = 0x01               # Off
    encoding_3d: int = 0x00
    right_to_left_3d: bool = False
    depth_3d: int = 0x00
    # Extended 3D option values (one per option index 0–5)
    ext_3d_correction: int = 0x01     # Left to Right
    ext_3d_depth: int = 0x00
    ext_3d_viewpoint: int = 0x00
    ext_3d_size: int = 0x01           # 16:9
    ext_3d_balance: int = 0x00
    ext_3d_optim: int = 0x00
    # UI state (not part of TV protocol)
    clients_connected: int = 0
    last_command: str = "(none)"
    last_command_count: int = 0  # Track consecutive repeats of same command
    show_help: bool = False
    power_on_time: float | None = None  # Timestamp when power-on was initiated


# ── Protocol helpers ──────────────────────────────────────────────────────────

# Command wire format: {cmd1}{cmd2} {set_id:02X} {data0:02X}[ {data1:02X}...]\r
_CMD_RE = re.compile(
    r"^(?P<cmd1>.)(?P<cmd2>.) (?P<set_id>[0-9A-Fa-f]{2})"
    r"(?: (?P<data>[0-9A-Fa-f]{2}(?:(?: [0-9A-Fa-f]{2})*)?))?$"
)


def parse_command(raw: str) -> tuple[str, str, int, list[int]] | None:
    """Parse a command line (with or without trailing \\r) into components."""
    m = _CMD_RE.match(raw.strip())
    if not m:
        return None
    cmd1 = m.group("cmd1")
    cmd2 = m.group("cmd2")
    set_id = int(m.group("set_id"), 16)
    data_str = m.group("data") or ""
    data_bytes = [int(x, 16) for x in data_str.split() if x]
    return cmd1, cmd2, set_id, data_bytes


def build_response(cmd2: str, set_id: int, ok: bool, *data_bytes: int) -> bytes:
    """
    Build a response matching the format expected by parse_response() in lgtv_api.py.
    Format: ``{cmd2} {set_id:02X} {OK|NG}{data:02X}...x``
    No trailing CR — the reader accumulates until the literal ``x`` end-marker.
    """
    status = "OK" if ok else "NG"
    data_str = "".join(f"{b:02X}" for b in data_bytes)
    return f"{cmd2} {set_id:02X} {status}{data_str}x".encode("ascii")


def _clamp(val: int, lo: int = 0, hi: int = 0x64) -> int:
    return max(lo, min(hi, val))


# ── Command handlers ──────────────────────────────────────────────────────────

def _h_power(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        val = 0x01 if state.power else 0x00
        state.last_command = f"Power? → {'ON' if state.power else 'OFF'}"
        return build_response(cmd2, set_id, True, val)
    # When powering on, set the boot time so emulator will not respond for BOOT_DELAY seconds
    if data[0] == 0x01 and not state.power:
        state.power_on_time = time.time()
    state.power = data[0] == 0x01
    state.last_command = f"Power = {'ON' if state.power else 'OFF'}"
    return build_response(cmd2, set_id, True, data[0])


def _h_aspect_ratio(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        name = ASPECT_RATIO_NAMES.get(state.aspect_ratio, f"{state.aspect_ratio:#04x}")
        state.last_command = f"Aspect? → {name}"
        return build_response(cmd2, set_id, True, state.aspect_ratio)
    state.aspect_ratio = data[0]
    name = ASPECT_RATIO_NAMES.get(data[0], f"{data[0]:#04x}")
    state.last_command = f"Aspect = {name}"
    return build_response(cmd2, set_id, True, data[0])


def _h_screen_mute(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        state.last_command = f"ScreenMute? → {SCREEN_MUTE_NAMES.get(state.screen_mute, f'{state.screen_mute:#04x}')}"
        return build_response(cmd2, set_id, True, state.screen_mute)
    state.screen_mute = data[0]
    state.last_command = f"ScreenMute = {SCREEN_MUTE_NAMES.get(data[0], f'{data[0]:#04x}')}"
    return build_response(cmd2, set_id, True, data[0])


def _h_volume_mute(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    # Protocol: 00 = mute on (volume off), 01 = mute off (volume on)
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        val = 0x00 if state.volume_mute else 0x01
        state.last_command = f"Mute? → {'ON' if state.volume_mute else 'OFF'}"
        return build_response(cmd2, set_id, True, val)
    state.volume_mute = data[0] == 0x00
    state.last_command = f"Mute = {'ON' if state.volume_mute else 'OFF'}"
    return build_response(cmd2, set_id, True, data[0])


def _make_numeric_handler(attr: str, label: str) -> object:
    """Factory for simple numeric get/set (range 0x00–0x64)."""
    def handler(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
        if not data:
            return build_response(cmd2, set_id, False, 0x00)
        if data[0] == 0xFF:
            val = getattr(state, attr)
            state.last_command = f"{label}? → {val} ({val:#04x})"
            return build_response(cmd2, set_id, True, val)
        val = _clamp(data[0])
        setattr(state, attr, val)
        state.last_command = f"{label} = {val} ({val:#04x})"
        return build_response(cmd2, set_id, True, val)
    return handler


def _make_bool_handler(attr: str, label: str) -> object:
    """Factory for boolean get/set: 0x00 = off/false, 0x01 = on/true."""
    def handler(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
        if not data:
            return build_response(cmd2, set_id, False, 0x00)
        if data[0] == 0xFF:
            raw: bool = getattr(state, attr)
            val = 0x01 if raw else 0x00
            state.last_command = f"{label}? → {'On' if raw else 'Off'}"
            return build_response(cmd2, set_id, True, val)
        setattr(state, attr, data[0] == 0x01)
        raw = getattr(state, attr)
        state.last_command = f"{label} = {'On' if raw else 'Off'}"
        return build_response(cmd2, set_id, True, data[0])
    return handler


def _h_ism_method(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        name = ISM_METHOD_NAMES.get(state.ism_method, f"{state.ism_method:#04x}")
        state.last_command = f"ISM? → {name}"
        return build_response(cmd2, set_id, True, state.ism_method)
    state.ism_method = data[0]
    name = ISM_METHOD_NAMES.get(data[0], f"{data[0]:#04x}")
    state.last_command = f"ISM = {name}"
    return build_response(cmd2, set_id, True, data[0])


def _h_energy_saving(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        name = ENERGY_SAVING_NAMES.get(state.energy_saving, f"{state.energy_saving:#04x}")
        state.last_command = f"Energy? → {name}"
        return build_response(cmd2, set_id, True, state.energy_saving)
    state.energy_saving = data[0]
    name = ENERGY_SAVING_NAMES.get(data[0], f"{data[0]:#04x}")
    state.last_command = f"Energy = {name}"
    return build_response(cmd2, set_id, True, data[0])


def _h_auto_configure(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    state.last_command = "AutoConfigure triggered"
    return build_response(cmd2, set_id, True, 0x01)


def _h_tune(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if len(data) < 3:
        return build_response(cmd2, set_id, False, 0x00)
    state.channel_high = data[0]
    state.channel_low = data[1]
    state.channel_type = data[2]
    ch = (data[0] << 8) | data[1]
    ctype = CHANNEL_TYPE_NAMES.get(data[2], f"{data[2]:#04x}")
    state.last_command = f"Tune ch={ch} type={ctype}"
    return build_response(cmd2, set_id, True, data[0])


def _h_programme_skip(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    # 00 = Skip, 01 = Add
    state.programme_skip = data[0] == 0x00
    state.last_command = f"ProgrammeSkip = {'Skip' if state.programme_skip else 'Add'}"
    return build_response(cmd2, set_id, True, data[0])


def _h_ir_key(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    state.last_command = f"IR key {data[0]:#04x}"
    return build_response(cmd2, set_id, True, data[0])


def _h_input(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        name = INPUT_NAMES.get(state.input_source, f"{state.input_source:#04x}")
        state.last_command = f"Input? → {name}"
        return build_response(cmd2, set_id, True, state.input_source)
    state.input_source = data[0]
    name = INPUT_NAMES.get(data[0], f"{data[0]:#04x}")
    state.last_command = f"Input = {name}"
    return build_response(cmd2, set_id, True, data[0])


def _h_3d(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if not data:
        return build_response(cmd2, set_id, False, 0x00)
    if data[0] == 0xFF:
        state.last_command = f"3D? → {MODE_3D_NAMES.get(state.mode_3d, str(state.mode_3d))}"
        return build_response(
            cmd2, set_id, True,
            state.mode_3d, state.encoding_3d,
            0x01 if state.right_to_left_3d else 0x00,
            state.depth_3d,
        )
    mode = data[0]
    state.mode_3d = mode
    if mode == 0x00 and len(data) >= 3:   # 3D On: data2=encoding, data3=direction
        state.encoding_3d = data[1]
        state.right_to_left_3d = data[2] == 0x00
    elif mode == 0x03 and len(data) >= 4:  # 2D→3D: data4=depth
        state.depth_3d = data[3]
    state.last_command = f"3D = {MODE_3D_NAMES.get(mode, str(mode))}"
    return build_response(cmd2, set_id, True, *data)


_EXT3D_ATTRS = [
    "ext_3d_correction",  # 0
    "ext_3d_depth",       # 1
    "ext_3d_viewpoint",   # 2
    "ext_3d_size",        # 3
    "ext_3d_balance",     # 4
    "ext_3d_optim",       # 5
]


def _h_ext_3d(state: TvState, cmd2: str, set_id: int, data: list[int]) -> bytes:
    if len(data) < 2:
        return build_response(cmd2, set_id, False, 0x00)
    option = data[0]
    if option >= len(_EXT3D_ATTRS):
        return build_response(cmd2, set_id, False, 0x00)
    setattr(state, _EXT3D_ATTRS[option], data[1])
    state.last_command = f"Ext3D opt={option} = {data[1]}"
    return build_response(cmd2, set_id, True, data[0], data[1])


# Build the dispatch table using factories where appropriate
_DISPATCH: dict[tuple[str, str], object] = {
    ("k", "a"): _h_power,
    ("k", "c"): _h_aspect_ratio,
    ("k", "d"): _h_screen_mute,
    ("k", "e"): _h_volume_mute,
    ("k", "f"): _make_numeric_handler("volume", "Volume"),
    ("k", "g"): _make_numeric_handler("contrast", "Contrast"),
    ("k", "h"): _make_numeric_handler("brightness", "Brightness"),
    ("k", "i"): _make_numeric_handler("color", "Color"),
    ("k", "j"): _make_numeric_handler("tint", "Tint"),
    ("k", "k"): _make_numeric_handler("sharpness", "Sharpness"),
    ("k", "l"): _make_bool_handler("osd", "OSD"),
    ("k", "m"): _make_bool_handler("remote_lock", "RemoteLock"),
    ("k", "r"): _make_numeric_handler("treble", "Treble"),
    ("k", "s"): _make_numeric_handler("bass", "Bass"),
    ("k", "t"): _make_numeric_handler("balance", "Balance"),
    ("x", "u"): _make_numeric_handler("color_temp", "ColorTemp"),
    ("j", "p"): _h_ism_method,
    ("j", "q"): _h_energy_saving,
    ("j", "u"): _h_auto_configure,
    ("m", "a"): _h_tune,
    ("m", "b"): _h_programme_skip,
    ("m", "c"): _h_ir_key,
    ("m", "g"): _make_numeric_handler("backlight", "Backlight"),
    ("x", "b"): _h_input,
    ("x", "t"): _h_3d,
    ("x", "v"): _h_ext_3d,
}


def _dispatch_command(
    state: TvState, cmd1: str, cmd2: str, data: list[int], resp_set_id: int
) -> bytes | None:
    cmd_key = f"{cmd1}{cmd2}"
    
    # Track command repeats
    if cmd_key == getattr(state, "_last_cmd_key", ""):
        state.last_command_count += 1
    else:
        state.last_command_count = 1
    state._last_cmd_key = cmd_key  # type: ignore[attr-defined]
    
    # Real LG TVs take time to boot after power-on and don't respond during this time.
    # Return None (no response) to simulate timeout on the client side.
    if state.power_on_time is not None and time.time() - state.power_on_time < BOOT_DELAY:
        state.last_command = f"{cmd_key} → (no response, booting)"
        return None
    
    # After boot completes, clear the boot timer
    if state.power_on_time is not None:
        state.power_on_time = None
    
    # Real LG TVs only respond to power command when powered off. All other commands
    # return NG (or timeout, but we just return NG for simplicity).
    if not state.power and (cmd1, cmd2) != ("k", "a"):
        state.last_command = f"{cmd1}{cmd2} → NG (TV off)"
        return build_response(cmd2, resp_set_id, False, 0x00)
    
    handler = _DISPATCH.get((cmd1, cmd2))
    if handler is None:
        state.last_command = f"{cmd1}{cmd2} → NG (unknown)"
        return build_response(cmd2, resp_set_id, False, 0x00)
    try:
        return handler(state, cmd2, resp_set_id, data)  # type: ignore[operator]
    except Exception:
        return build_response(cmd2, resp_set_id, False, 0x00)


# ── TCP client handler ────────────────────────────────────────────────────────

async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: TvState,
    configured_set_id: int,
) -> None:
    state.clients_connected += 1
    buf = bytearray()
    try:
        while True:
            chunk = await reader.read(256)
            if not chunk:
                break
            buf.extend(chunk)
            # Process all complete commands (terminated by \r)
            while b"\r" in buf:
                idx = buf.index(b"\r")
                raw_bytes = bytes(buf[:idx])
                buf = buf[idx + 1:]
                try:
                    raw = raw_bytes.decode("ascii").strip()
                except UnicodeDecodeError:
                    continue
                if not raw:
                    continue
                parsed = parse_command(raw)
                if parsed is None:
                    continue
                cmd1, cmd2, incoming_set_id, data = parsed
                # Ignore commands not addressed to this emulator
                if incoming_set_id != 0x00 and incoming_set_id != configured_set_id:
                    continue
                response = _dispatch_command(state, cmd1, cmd2, data, configured_set_id)
                # Skip sending if no response (e.g., during boot delay)
                if response is not None:
                    writer.write(response)
                    await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        state.clients_connected = max(0, state.clients_connected - 1)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ── Curses display ────────────────────────────────────────────────────────────

def _safe_addstr(
    stdscr: "curses.window", y: int, x: int, text: str, attr: int = 0
) -> None:
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    max_len = w - x - 1
    if max_len <= 0:
        return
    try:
        stdscr.addstr(y, x, text[:max_len], attr)
    except curses.error:
        pass


def _draw_ui(
    stdscr: "curses.window",
    state: TvState,
    port: int,
    host: str,
    configured_set_id: int,
    has_colors: bool,
) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    color_on = curses.color_pair(1) | curses.A_BOLD if has_colors else curses.A_BOLD
    color_off = curses.color_pair(2) | curses.A_BOLD if has_colors else curses.A_BOLD
    color_label = curses.color_pair(3) if has_colors else 0

    # Title bar
    title = f" LG TV Emulator  {host}:{port}  Set ID {configured_set_id:02X} "
    _safe_addstr(stdscr, 0, 0, title.center(w - 1), curses.A_REVERSE)

    row = 2

    # Main controls (with keyboard shortcuts inline)
    power_str = "ON" if state.power else "OFF"
    power_attr = color_on if state.power else color_off
    _safe_addstr(stdscr, row, 2, "[p] Power", color_label)
    _safe_addstr(stdscr, row, 14, power_str, power_attr)

    mute_str = "Muted" if state.volume_mute else "Unmuted"
    _safe_addstr(stdscr, row, 24, "[m] Mute", color_label)
    _safe_addstr(stdscr, row, 35, mute_str)

    _safe_addstr(stdscr, row, 48, "[+/-] Volume", color_label)
    _safe_addstr(stdscr, row, 62, f"{state.volume:3d}")

    row += 1
    _safe_addstr(stdscr, row, 2, "[i] Input", color_label)
    input_name = INPUT_NAMES.get(state.input_source, f"0x{state.input_source:02X}")
    _safe_addstr(stdscr, row, 14, input_name)

    row += 1
    row += 1  # Blank line

    # Picture controls
    _safe_addstr(stdscr, row, 2, "[b/B] Brightness", color_label)
    _safe_addstr(stdscr, row, 21, f"{state.brightness:3d}")
    _safe_addstr(stdscr, row, 30, "[c/C] Contrast", color_label)
    _safe_addstr(stdscr, row, 47, f"{state.contrast:3d}")

    row += 1
    _safe_addstr(stdscr, row, 2, "[g/G] Backlight", color_label)
    _safe_addstr(stdscr, row, 21, f"{state.backlight:3d}")
    _safe_addstr(stdscr, row, 30, "[t/T] Treble", color_label)
    _safe_addstr(stdscr, row, 47, f"{state.treble:3d}")

    row += 1
    _safe_addstr(stdscr, row, 2, "[v/V] Tint", color_label)
    _safe_addstr(stdscr, row, 21, f"{state.tint:3d}")
    _safe_addstr(stdscr, row, 30, "[z/Z] Bass", color_label)
    _safe_addstr(stdscr, row, 47, f"{state.bass:3d}")

    row += 1
    _safe_addstr(stdscr, row, 2, "[x/X] Color", color_label)
    _safe_addstr(stdscr, row, 21, f"{state.color:3d}")
    _safe_addstr(stdscr, row, 30, "[h/H] Sharpness", color_label)
    _safe_addstr(stdscr, row, 47, f"{state.sharpness:3d}")

    row += 1
    _safe_addstr(stdscr, row, 2, "[u/U] Balance", color_label)
    _safe_addstr(stdscr, row, 21, f"{state.balance:3d}")
    _safe_addstr(stdscr, row, 30, "[y/Y] ColorTemp", color_label)
    _safe_addstr(stdscr, row, 47, f"{state.color_temp:3d}")

    row += 1
    row += 1  # Blank line

    # Feature toggles/cycles
    aspect_name = ASPECT_RATIO_NAMES.get(state.aspect_ratio, f"0x{state.aspect_ratio:02X}")
    _safe_addstr(stdscr, row, 2, "[a] Aspect", color_label)
    _safe_addstr(stdscr, row, 15, f"{aspect_name:<12}")

    energy_name = ENERGY_SAVING_NAMES.get(state.energy_saving, f"0x{state.energy_saving:02X}")
    _safe_addstr(stdscr, row, 28, "[e] Energy", color_label)
    _safe_addstr(stdscr, row, 40, f"{energy_name:<12}")

    row += 1
    sm_name = SCREEN_MUTE_NAMES.get(state.screen_mute, f"0x{state.screen_mute:02X}")
    _safe_addstr(stdscr, row, 2, "[s] ScreenMute", color_label)
    _safe_addstr(stdscr, row, 18, f"{sm_name:<8}")

    mode3d = MODE_3D_NAMES.get(state.mode_3d, str(state.mode_3d))
    _safe_addstr(stdscr, row, 28, "[3] 3D", color_label)
    _safe_addstr(stdscr, row, 36, f"{mode3d:<12}")

    row += 1
    osd_attr = 0 if state.osd else color_off
    _safe_addstr(stdscr, row, 2, "[l] OSD", color_label)
    _safe_addstr(stdscr, row, 12, "On" if state.osd else "Off", osd_attr)

    lock_attr = color_on if state.remote_lock else 0
    _safe_addstr(stdscr, row, 28, "[r] RemoteLock", color_label)
    _safe_addstr(stdscr, row, 45, "On" if state.remote_lock else "Off", lock_attr)

    row += 1
    ch = (state.channel_high << 8) | state.channel_low
    ch_type = CHANNEL_TYPE_NAMES.get(state.channel_type, f"0x{state.channel_type:02X}")
    _safe_addstr(stdscr, row, 2, "[n/N] Channel", color_label)
    _safe_addstr(stdscr, row, 17, f"{ch:4d} ({ch_type})")

    row += 1
    ism_name = ISM_METHOD_NAMES.get(state.ism_method, f"0x{state.ism_method:02X}")
    _safe_addstr(stdscr, row, 2, "[k/K] ISM", color_label)
    _safe_addstr(stdscr, row, 14, f"{ism_name:<14}")
    _safe_addstr(stdscr, row, 28, "[j/J] ProgSkip", color_label)
    _safe_addstr(stdscr, row, 45, "Yes" if state.programme_skip else "No")

    row += 1
    row += 1  # Blank line

    # Status bar
    _safe_addstr(stdscr, row, 0, "─" * (w - 1))
    row += 1
    clients_attr = color_on if state.clients_connected > 0 else 0
    _safe_addstr(stdscr, row, 2, "Clients: ", color_label)
    _safe_addstr(stdscr, row, 11, str(state.clients_connected), clients_attr)
    
    # Show command repeat count
    repeat_str = f" (×{state.last_command_count})" if state.last_command_count > 1 else ""
    last_cmd_display = f"Last: {state.last_command}{repeat_str}"
    _safe_addstr(stdscr, row, 20, last_cmd_display)

    row += 1
    _safe_addstr(stdscr, row, 0, "─" * (w - 1))

    stdscr.refresh()


# ── Async tasks ───────────────────────────────────────────────────────────────

async def _display_task(
    stdscr: "curses.window",
    state: TvState,
    port: int,
    host: str,
    configured_set_id: int,
    has_colors: bool,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            _draw_ui(stdscr, state, port, host, configured_set_id, has_colors)
        except curses.error:
            pass
        try:
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            break


async def _keyboard_task(
    stdscr: "curses.window",
    state: TvState,
    stop_event: asyncio.Event,
) -> None:
    loop = asyncio.get_running_loop()
    while not stop_event.is_set():
        try:
            key = await loop.run_in_executor(None, stdscr.getch)
        except Exception:
            break
        if stop_event.is_set():
            break
        _handle_key(key, state, stop_event)


# ── Keyboard handler ──────────────────────────────────────────────────────────

def _handle_key(key: int, state: TvState, stop_event: asyncio.Event) -> None:
    ch = chr(key) if 0 <= key <= 255 else None

    if ch in ("q", "Q"):
        stop_event.set()
    elif ch == "p":
        state.power = not state.power
        state.last_command = f"[kbd] Power → {'ON' if state.power else 'OFF'}"
    elif ch == "m":
        state.volume_mute = not state.volume_mute
        state.last_command = f"[kbd] Mute → {'ON' if state.volume_mute else 'OFF'}"
    elif ch in ("+", "="):
        state.volume = _clamp(state.volume + 1)
        state.last_command = f"[kbd] Volume → {state.volume}"
    elif ch == "-":
        state.volume = _clamp(state.volume - 1)
        state.last_command = f"[kbd] Volume → {state.volume}"
    elif ch == "v":
        state.volume = _clamp(state.volume + 5)
        state.last_command = f"[kbd] Volume → {state.volume}"
    elif ch == "V":
        state.volume = _clamp(state.volume - 5)
        state.last_command = f"[kbd] Volume → {state.volume}"
    elif ch == "i":
        idx = INPUT_CYCLE.index(state.input_source) if state.input_source in INPUT_CYCLE else -1
        state.input_source = INPUT_CYCLE[(idx + 1) % len(INPUT_CYCLE)]
        state.last_command = f"[kbd] Input → {INPUT_NAMES.get(state.input_source, f'{state.input_source:#04x}')}"
    elif ch == "?":
        state.show_help = not state.show_help
    elif ch == "b":
        state.brightness = _clamp(state.brightness + 1)
        state.last_command = f"[kbd] Brightness → {state.brightness}"
    elif ch == "B":
        state.brightness = _clamp(state.brightness - 1)
        state.last_command = f"[kbd] Brightness → {state.brightness}"
    elif ch == "c":
        state.contrast = _clamp(state.contrast + 1)
        state.last_command = f"[kbd] Contrast → {state.contrast}"
    elif ch == "C":
        state.contrast = _clamp(state.contrast - 1)
        state.last_command = f"[kbd] Contrast → {state.contrast}"
    elif ch == "t":
        state.treble = _clamp(state.treble + 1)
        state.last_command = f"[kbd] Treble → {state.treble}"
    elif ch == "T":
        state.treble = _clamp(state.treble - 1)
        state.last_command = f"[kbd] Treble → {state.treble}"
    elif ch == "z":
        state.bass = _clamp(state.bass + 1)
        state.last_command = f"[kbd] Bass → {state.bass}"
    elif ch == "Z":
        state.bass = _clamp(state.bass - 1)
        state.last_command = f"[kbd] Bass → {state.bass}"
    elif ch == "g":
        state.backlight = _clamp(state.backlight + 1)
        state.last_command = f"[kbd] Backlight → {state.backlight}"
    elif ch == "G":
        state.backlight = _clamp(state.backlight - 1)
        state.last_command = f"[kbd] Backlight → {state.backlight}"
    elif ch == "x":
        state.color = _clamp(state.color + 1)
        state.last_command = f"[kbd] Color → {state.color}"
    elif ch == "X":
        state.color = _clamp(state.color - 1)
        state.last_command = f"[kbd] Color → {state.color}"
    elif ch == "h":
        state.sharpness = _clamp(state.sharpness + 1)
        state.last_command = f"[kbd] Sharpness → {state.sharpness}"
    elif ch == "H":
        state.sharpness = _clamp(state.sharpness - 1)
        state.last_command = f"[kbd] Sharpness → {state.sharpness}"
    elif ch == "u":
        state.balance = _clamp(state.balance + 1)
        state.last_command = f"[kbd] Balance → {state.balance}"
    elif ch == "U":
        state.balance = _clamp(state.balance - 1)
        state.last_command = f"[kbd] Balance → {state.balance}"
    elif ch == "y":
        state.color_temp = _clamp(state.color_temp + 1)
        state.last_command = f"[kbd] ColorTemp → {state.color_temp}"
    elif ch == "Y":
        state.color_temp = _clamp(state.color_temp - 1)
        state.last_command = f"[kbd] ColorTemp → {state.color_temp}"
    elif ch == "a":
        idx = ASPECT_RATIOS.index(state.aspect_ratio) if state.aspect_ratio in ASPECT_RATIOS else -1
        state.aspect_ratio = ASPECT_RATIOS[(idx + 1) % len(ASPECT_RATIOS)]
        state.last_command = f"[kbd] Aspect → {ASPECT_RATIO_NAMES.get(state.aspect_ratio, f'{state.aspect_ratio:#04x}')}"
    elif ch == "e":
        idx = ENERGY_SAVING_CYCLE.index(state.energy_saving) if state.energy_saving in ENERGY_SAVING_CYCLE else -1
        state.energy_saving = ENERGY_SAVING_CYCLE[(idx + 1) % len(ENERGY_SAVING_CYCLE)]
        state.last_command = f"[kbd] Energy → {ENERGY_SAVING_NAMES.get(state.energy_saving, str(state.energy_saving))}"
    elif ch == "s":
        cycle = [0x00, 0x01, 0x10]
        idx = cycle.index(state.screen_mute) if state.screen_mute in cycle else -1
        state.screen_mute = cycle[(idx + 1) % len(cycle)]
        state.last_command = f"[kbd] ScreenMute → {SCREEN_MUTE_NAMES.get(state.screen_mute, f'{state.screen_mute:#04x}')}"
    elif ch == "3":
        state.mode_3d = 0x01 if state.mode_3d == 0x00 else 0x00
        state.last_command = f"[kbd] 3D → {MODE_3D_NAMES.get(state.mode_3d, str(state.mode_3d))}"
    elif ch == "r":
        state.remote_lock = not state.remote_lock
        state.last_command = f"[kbd] RemoteLock → {'On' if state.remote_lock else 'Off'}"
    elif ch == "l":
        state.osd = not state.osd
        state.last_command = f"[kbd] OSD → {'On' if state.osd else 'Off'}"
    elif ch == "k":
        cycle = list(ISM_METHOD_NAMES)
        idx = cycle.index(state.ism_method) if state.ism_method in cycle else -1
        state.ism_method = cycle[(idx + 1) % len(cycle)]
        state.last_command = f"[kbd] ISM → {ISM_METHOD_NAMES.get(state.ism_method, str(state.ism_method))}"
    elif ch == "j":
        state.programme_skip = not state.programme_skip
        state.last_command = f"[kbd] ProgSkip → {'Yes' if state.programme_skip else 'No'}"
    elif ch == "n":
        ch_num = ((state.channel_high << 8) | state.channel_low) + 1
        state.channel_high = (ch_num >> 8) & 0xFF
        state.channel_low = ch_num & 0xFF
        state.last_command = f"[kbd] Channel → {ch_num}"
    elif ch == "N":
        ch_num = max(0, ((state.channel_high << 8) | state.channel_low) - 1)
        state.channel_high = (ch_num >> 8) & 0xFF
        state.channel_low = ch_num & 0xFF
        state.last_command = f"[kbd] Channel → {ch_num}"


# ── Entry point ───────────────────────────────────────────────────────────────

async def _async_main(
    stdscr: "curses.window",
    host: str,
    port: int,
    configured_set_id: int,
    state: TvState,
    has_colors: bool,
) -> None:
    stop_event = asyncio.Event()

    server = await asyncio.start_server(
        lambda r, w: _handle_client(r, w, state, configured_set_id),
        host,
        port,
    )

    display = asyncio.create_task(
        _display_task(stdscr, state, port, host, configured_set_id, has_colors, stop_event)
    )
    keyboard = asyncio.create_task(
        _keyboard_task(stdscr, state, stop_event)
    )

    async with server:
        await stop_event.wait()

    display.cancel()
    keyboard.cancel()
    await asyncio.gather(display, keyboard, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "LG TV Serial Protocol Emulator — TCP server for integration testing.\n"
            "Connect the integration using socket://<host>:<port>."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=int, default=12345,
        help="TCP port to listen on (default: 12345)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--set-id", type=int, default=1, dest="set_id",
        choices=range(1, 100), metavar="ID",
        help="Set ID to emulate (1–99, default: 1)",
    )
    args = parser.parse_args()

    state = TvState()

    # Initialise curses manually so we can pass stdscr into asyncio.run()
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.curs_set(0)

    has_colors = False
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # power on / connected
        curses.init_pair(2, curses.COLOR_RED, -1)     # power off / warning
        curses.init_pair(3, curses.COLOR_CYAN, -1)    # labels / help
        has_colors = curses.has_colors()
    except curses.error:
        pass

    try:
        asyncio.run(_async_main(stdscr, args.host, args.port, args.set_id, state, has_colors))
    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal
        try:
            curses.echo()
            curses.nocbreak()
            stdscr.keypad(False)
            curses.endwin()
        except curses.error:
            pass

    print(f"Emulator stopped. Served {args.host}:{args.port} (Set ID {args.set_id:02X})")


if __name__ == "__main__":
    main()
