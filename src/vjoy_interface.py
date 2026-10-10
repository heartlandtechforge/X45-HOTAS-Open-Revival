"""Minimal ctypes wrapper around vJoyInterface.dll.

Only the handful of calls the remapper needs. No pip dependency (pyvjoy) —
vJoyInterface.dll already ships with the vJoy driver install, so this talks
to it directly.

Reference: vJoy SDK public.h (github.com/BrunnerInnovation/vJoy).
"""
import ctypes
import os

# HID usages vJoy axes are reported under.
HID_USAGE_X = 0x30
HID_USAGE_Y = 0x31
HID_USAGE_Z = 0x32
HID_USAGE_RX = 0x33
HID_USAGE_RY = 0x34
HID_USAGE_RZ = 0x35
HID_USAGE_SL0 = 0x36
HID_USAGE_SL1 = 0x37
HID_USAGE_RUDDER = 0xBA
HID_USAGE_THROTTLE = 0xBB
HID_USAGE_POV = 0x39

# vJoy ships its DLL here by default.
_DEFAULT_DLL_DIRS = [
    r"C:\Program Files\vJoy\x64",
    r"C:\Program Files (x86)\vJoy\x86",
]


def _load_dll():
    last_err = None
    for d in _DEFAULT_DLL_DIRS:
        path = os.path.join(d, "vJoyInterface.dll")
        if os.path.exists(path):
            try:
                os.add_dll_directory(d)
            except (AttributeError, FileNotFoundError):
                pass
            try:
                return ctypes.WinDLL(path)
            except OSError as exc:
                last_err = exc
    raise RuntimeError(
        "Could not load vJoyInterface.dll. Is vJoy installed? "
        f"Last error: {last_err}"
    )


_dll = _load_dll()

_dll.vJoyEnabled.restype = ctypes.c_bool
_dll.GetVJDButtonNumber.restype = ctypes.c_int
_dll.GetVJDButtonNumber.argtypes = [ctypes.c_uint]
_dll.GetVJDAxisExist.restype = ctypes.c_bool
_dll.GetVJDAxisExist.argtypes = [ctypes.c_uint, ctypes.c_uint]
_dll.AcquireVJD.restype = ctypes.c_bool
_dll.AcquireVJD.argtypes = [ctypes.c_uint]
_dll.RelinquishVJD.argtypes = [ctypes.c_uint]
_dll.ResetVJD.argtypes = [ctypes.c_uint]
_dll.SetBtn.restype = ctypes.c_bool
_dll.SetBtn.argtypes = [ctypes.c_bool, ctypes.c_uint, ctypes.c_ubyte]
_dll.SetAxis.restype = ctypes.c_bool
_dll.SetAxis.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_uint]
_dll.SetContPov.restype = ctypes.c_bool
_dll.SetContPov.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_ubyte]


class VJoyError(RuntimeError):
    pass


class VJoyDevice:
    """One acquired vJoy virtual joystick (rID is 1-based, per vJoy convention)."""

    def __init__(self, rid: int = 1):
        if not _dll.vJoyEnabled():
            raise VJoyError("vJoy driver reports disabled. Check Device Manager.")
        self.rid = rid
        self.num_buttons = _dll.GetVJDButtonNumber(rid)
        if self.num_buttons <= 0:
            raise VJoyError(
                f"vJoy device #{rid} has 0 buttons configured. "
                "Run 'Configure vJoy' (as admin) and give it buttons/axes/a POV first."
            )
        if not _dll.AcquireVJD(rid):
            raise VJoyError(
                f"Could not acquire vJoy device #{rid}. Is it already owned by "
                "another app, or missing/disabled in Device Manager?"
            )
        _dll.ResetVJD(rid)
        self._warned_buttons = set()

    def has_axis(self, usage: int) -> bool:
        return bool(_dll.GetVJDAxisExist(self.rid, usage))

    def set_button(self, button_1_indexed: int, pressed: bool) -> None:
        if button_1_indexed < 1 or button_1_indexed > self.num_buttons:
            if button_1_indexed not in self._warned_buttons:
                self._warned_buttons.add(button_1_indexed)
                print(
                    f"Skipping virtual button {button_1_indexed}: outside configured "
                    f"range 1..{self.num_buttons}. Increase button count in "
                    "'Configure vJoy' (as Administrator) to use it."
                )
            return
        _dll.SetBtn(bool(pressed), self.rid, ctypes.c_ubyte(button_1_indexed))

    def set_axis(self, usage: int, value_0_to_32768: int) -> None:
        _dll.SetAxis(ctypes.c_long(int(value_0_to_32768)), self.rid, usage)

    def set_pov_degrees(self, pov_index: int, degrees) -> None:
        """degrees: 0.0-359.99 clockwise from north, or None for centered."""
        if degrees is None:
            val = -1
        else:
            val = int((degrees % 360) * 100)
        _dll.SetContPov(ctypes.c_long(val), self.rid, ctypes.c_ubyte(pov_index))

    def close(self) -> None:
        _dll.RelinquishVJD(self.rid)
