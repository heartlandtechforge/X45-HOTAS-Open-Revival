"""X45-OpenHOTAS remapper.

Reads the Saitek X45 directly via SDL2 (pygame) and drives a vJoy virtual
joystick, so Star Citizen (or anything else) just sees one clean virtual
device. No SST, no console macros, no legacy .NET dependency.

Layering: the Mode switch (3-way) and Aux slider (3-way) together select one
of 9 layers. Each of the 12 "layered" physical buttons (8 fire buttons + the
POV2 mini-hat) gets remapped to a different vJoy virtual button per layer, so
the same physical button can mean something different in each Mode/Aux
combination -- done entirely in software, replacing what the old SST .pr0
profiles tried to do with console macros.

Usage:
    python remapper.py                  run the remapper
    python remapper.py --calibrate-axes  print live axis values to help
                                          label config.json's axis_order
    python remapper.py --list-devices    list connected joysticks and exit
"""
import argparse
import json
import pathlib
import sys
import time

import pygame

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vjoy_interface as vj

CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "config.json"

# Physical-control name (as used in config.json's axis_order) -> vJoy HID usage.
# Tried this fork's dedicated Rudder/Throttle/Slider/Dial usages first, but
# its HID report descriptor puts Rudder (0xBA) and Throttle (0xBB) on the
# Generic Desktop usage page under non-standard usage IDs -- outside the
# page's normal 0x30-0x39 axis range -- so generic axis parsers (confirmed:
# the Windows joystick test panel) don't recognize them as axes at all.
# Sticking to the plain, universally-recognized set instead: less pretty
# labeling in Star Citizen's bind screen, but it actually registers.
AXIS_USAGE_BY_NAME = {
    "stick_x": vj.HID_USAGE_X,
    "stick_y": vj.HID_USAGE_Y,
    "throttle": vj.HID_USAGE_Z,
    "rudder": vj.HID_USAGE_RX,
    "knob_1": vj.HID_USAGE_RY,
    "knob_2": vj.HID_USAGE_RZ,
}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_joystick(name_match: str) -> pygame.joystick.Joystick:
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        if name_match.lower() in j.get_name().lower():
            return j
    raise SystemExit(
        f"No joystick matching '{name_match}' found. "
        f"Connected: {[pygame.joystick.Joystick(i).get_name() for i in range(pygame.joystick.get_count())]}"
    )


def list_devices():
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        print(f"{i}: {j.get_name()}  buttons={j.get_numbuttons()} "
              f"axes={j.get_numaxes()} hats={j.get_numhats()}")


def calibrate_axes(joy: pygame.joystick.Joystick):
    print("Move one control at a time. Ctrl+C to stop.\n")
    try:
        while True:
            pygame.event.pump()
            vals = [round(joy.get_axis(i), 3) for i in range(joy.get_numaxes())]
            print("\r" + " | ".join(f"a{i}={v:+.3f}" for i, v in enumerate(vals)), end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def norm_axis_to_vjoy(value: float) -> int:
    """pygame axis is -1.0..1.0 -> vJoy's default 1..32768 range."""
    value = max(-1.0, min(1.0, value))
    return int((value + 1.0) / 2.0 * 32767) + 1


def build_layer_map(cfg) -> dict:
    """physical_button -> {layer_index: vjoy_button_1_indexed}"""
    layered = cfg["layered_buttons"]
    mapping = {}
    for layer in range(9):
        base = layer * len(layered)
        for slot, entry in enumerate(layered):
            mapping.setdefault(entry["physical"], {})[layer] = base + slot + 1
    return mapping


def current_layer(joy, cfg) -> int:
    mode_btns = cfg["mode_switch_buttons"]
    aux_btns = cfg["aux_slider_buttons"]
    mode_idx = 0
    for i, key in enumerate(["M1", "M2", "M3"]):
        if joy.get_button(mode_btns[key]):
            mode_idx = i
            break
    aux_idx = 0
    for i, key in enumerate(["A1", "A2", "A3"]):
        if joy.get_button(aux_btns[key]):
            aux_idx = i
            break
    return mode_idx * 3 + aux_idx


def hat_to_degrees(hat_xy):
    x, y = hat_xy
    if x == 0 and y == 0:
        return None
    table = {
        (0, 1): 0, (1, 1): 45, (1, 0): 90, (1, -1): 135,
        (0, -1): 180, (-1, -1): 225, (-1, 0): 270, (-1, 1): 315,
    }
    return table.get((x, y))


def run(cfg):
    joy = find_joystick(cfg["device_name_match"])
    print(f"Using physical device: {joy.get_name()}")

    device = vj.VJoyDevice(cfg["vjoy_rid"])
    print(f"Acquired vJoy device #{cfg['vjoy_rid']} "
          f"({device.num_buttons} buttons configured)")

    needed = len(cfg["layered_buttons"]) * 9
    if device.num_buttons < needed:
        print(f"WARNING: vJoy device only has {device.num_buttons} buttons, "
              f"but the 9-layer map needs {needed}. Open 'Configure vJoy' "
              "(as Administrator) and raise the button count, then restart this script.")

    layer_map = build_layer_map(cfg)
    last_layer = None
    last_button_state = {}

    axis_order = cfg["axes"].get("axis_order", [])
    unknown_axis_names = [n for n in axis_order if n not in AXIS_USAGE_BY_NAME]
    if unknown_axis_names:
        print(f"WARNING: unrecognized axis name(s) in config.json axis_order, "
              f"skipping: {unknown_axis_names}")
    axis_usages = [AXIS_USAGE_BY_NAME[name] for name in axis_order if name in AXIS_USAGE_BY_NAME]

    try:
        while True:
            pygame.event.pump()

            layer = current_layer(joy, cfg)
            if layer != last_layer:
                print(f"Layer -> {layer} (Mode {layer // 3 + 1}, Aux {layer % 3 + 1})")
                # Release every virtual button this physical button could have
                # driven on the old layer, so nothing gets stuck held.
                if last_layer is not None:
                    for physical, layers in layer_map.items():
                        vbtn = layers.get(last_layer)
                        if vbtn:
                            device.set_button(vbtn, False)
                last_button_state.clear()
                last_layer = layer

            for physical, layers in layer_map.items():
                vbtn = layers.get(layer)
                if vbtn is None:
                    continue
                pressed = bool(joy.get_button(physical))
                if last_button_state.get(physical) != pressed:
                    device.set_button(vbtn, pressed)
                    last_button_state[physical] = pressed

            for i, usage in enumerate(axis_usages):
                if i >= joy.get_numaxes():
                    break
                if device.has_axis(usage):
                    device.set_axis(usage, norm_axis_to_vjoy(joy.get_axis(i)))

            if cfg["pov1"].get("enabled") and joy.get_numhats() > 0:
                degrees = hat_to_degrees(joy.get_hat(0))
                device.set_pov_degrees(cfg["pov1"]["vjoy_pov_index"], degrees)

            time.sleep(0.004)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        device.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate-axes", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()

    if args.list_devices:
        list_devices()
        return

    cfg = load_config()

    if args.calibrate_axes:
        joy = find_joystick(cfg["device_name_match"])
        calibrate_axes(joy)
        return

    run(cfg)


if __name__ == "__main__":
    main()
