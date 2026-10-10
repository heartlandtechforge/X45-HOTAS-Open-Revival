# X45 Revival

Open-source remapper that brings the 20+ year old Saitek X45 HOTAS back to
life on modern Windows, for Star Citizen or anything else that reads a
joystick — no SST required.

SST (2016, v6.6.6.9) needs the legacy .NET Framework 2.0/3.5 runtime, which
can fail to install on modern Windows, and its "9 mode" profile setup turned
out to just fire console macros (`pp_rebindkeys ...`) to swap keybind XML
files rather than doing real hardware-level remapping. This project instead:

- Reads the X45 directly via SDL2 (`pygame`) — confirmed to see all 26
  buttons, 6 axes, and all 4 hats, unlike the older `winmm` Windows
  joystick API, which silently drops some of them (notably the Mode switch).
- Computes a layer from the Mode switch (3-way) x Aux slider (3-way) = 9
  layers, same idea as the old SST profiles.
- Remaps the 8 fire buttons onto a different vJoy virtual button per layer,
  so the same physical button can do something different depending on
  Mode/Aux position.
- Passes the 6 analog axes and all 4 hats (POV1, POV2, Throttle Hat, Mouse
  Hat — same layout the official Saitek driver uses) straight through,
  unlayered.
- Outputs through [vJoy](https://github.com/BrunnerInnovation/vJoy) (the
  actively maintained fork — not vjoystick.net, which has a malware
  warning), so Star Citizen (or any other game) just sees one normal
  virtual joystick. No console macros, no SST, no .NET fights.

## Requirements

- Windows with the X45 plugged in and its SD6 driver installed (for the
  physical device to show up at all).
- [vJoy](https://github.com/BrunnerInnovation/vJoy/releases) installed.
- Python 3.13 (not 3.14 yet — `pygame` has no prebuilt wheel for it as of
  this writing). This was built against
  `C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe`.

```
pip install -r requirements.txt
```

## One-time setup: configure the vJoy device

The remapper needs 72 virtual buttons (8 physical fire buttons x 9 layers)
plus 4 POVs and 6 axes on vJoy device #1, but vJoy defaults to far fewer of
each.

1. Run **Configure vJoy** as Administrator (Start menu, or
   `C:\Program Files\vJoy\x64\vJoyConf.exe`).
2. Select device **#1**.
3. Set **Number of Buttons** to at least **72** (128 is the max and is a
   safe round number to pick).
4. Under **Axes**, check **X, Y, Z, Rx, Ry, Rz** only. This vJoy fork also
   offers dedicated Rudder/Throttle/Slider/Dial axes with nicer labels, but
   its HID report descriptor puts Rudder/Throttle on non-standard usage IDs
   that generic axis parsers (confirmed: the Windows joystick test panel)
   don't recognize as axes at all — they silently don't work. Stick to the
   plain X/Y/Z/Rx/Ry/Rz set; less pretty labeling in Star Citizen's bind
   screen, but it actually registers.
5. Under **POV Hat Switch**, select **Continuous** with **4** POVs — one
   each for POV1 (main hat), POV2 (left-thumb mini-hat), and reserved slots
   for the Throttle Hat and Mouse Hat (POV3/4; only Mouse Hat is actually
   wired up by default, Throttle Hat is dead hardware on the original dev's
   unit — see "Known hardware fault" below if yours works).
6. Click **Apply** (not just OK — OK alone can close the dialog without
   saving; the status line at the bottom should stop reading "Changes not
   applied").
7. **Changing the axis set after the device already exists requires a reset
   to take effect**: open Device Manager, find **vJoy Device**, right-click
   → **Disable device**, then right-click → **Enable device** again.
   Confirmed necessary in testing — Apply alone updated the stored config
   but not the live device until this reset.

Run `python src/remapper.py` afterward — it checks the configured button
count on startup and will warn (not crash) if it's still too low.

**Testing the output:** Windows' built-in joystick test panel (`joy.cpl`)
uses an old API that only displays the first ~32 buttons, so with 128
buttons configured, only Mode 1's buttons (vJoy buttons 1-36) will visibly
light up there — Mode 2/3 presses are likely working but off the end of
what that panel can show. Use vJoy's own `JoyMonitor.exe`
(`C:\Program Files\vJoy\x64\JoyMonitor.exe`) instead for a real check across
the full button and axis range, or just test directly in Star Citizen's
bind screen.

## Figuring out the axis order

Which pygame axis index (0-5) corresponds to which physical control (stick
X/Y, throttle, rudder, 2 rotary knobs) was never recorded. Find out with:

```
python src/remapper.py --calibrate-axes
```

Move one control at a time and watch which `aN=` value changes. Update
`axis_order` in `config.json` to match for documentation purposes (the
script currently passes axes through positionally regardless, 0->X ... 5->Rz,
so this step is about labeling, not required for it to work).

The same idea works for buttons and hats:

```
python src/remapper.py --calibrate-buttons
```

Prints each button's physical index live as you press it (`button 14 ->
DOWN`). Useful for finding a hat's up/down/left/right indices one direction
at a time — this is exactly how POV2's and POV4's button mappings in
`config.json` were worked out.

## Running it

```
python src/remapper.py
```

Leave it running, then in Star Citizen open its own keybinding screen and
bind actions to the vJoy virtual device's buttons/axes/POV as usual — one
time, in-game, same as binding any other controller.

`python src/remapper.py --list-devices` lists connected joysticks if you
need to sanity-check names/indices.

## Known hardware fault: Throttle Hat (POV3)

The official Saitek driver names 4 separate hats: POV1, POV2, Throttle Hat,
and Mouse Hat. On the original dev's unit, the **Throttle Hat** (physical
SDL indices 18-21) does not register at all — not in this tool's SDL2
capture, and not in the Windows/Saitek DirectInput test panel either. Since
even the OS-level panel sees nothing, this is almost certainly a real
physical/electrical fault inside the 20+ year old throttle unit (broken
contact, cracked solder joint, loose ribbon cable), not something software
can work around. It's left disabled in `config.json` (`disabled_buttons`,
and `pov3_throttle_hat.enabled: false`).

**If your Throttle Hat isn't dead**, it's worth enabling: the physical
button range (18-21) almost certainly carries over to other X45 units since
it's the same hardware/driver, but the up/down/left/right *order* within
those 4 was never verified live (couldn't be, on hardware that doesn't
respond) — `config.json`'s `pov3_throttle_hat.buttons` is an unverified
guess extrapolated from POV2's pattern. Confirm it with
`python src/remapper.py --calibrate-buttons` (press one direction at a
time, note which index fires), fix the mapping if needed, flip `enabled` to
`true`, and you'll also need to bump vJoy's POV count — it's already
configured for 4, so no vJoy changes needed, just the config edit.

Either way, the remapper is fully usable without it: the Mouse Hat (POV4),
POV1, POV2, all 8 fire buttons across all 9 Mode/Aux layers, and all 6 axes
are already wired up regardless.

## Layout reference

The original SST `.pr0` profiles and the one real keybind layout they
produced (the other 8 of the "9 mode" XMLs were byte-identical copies) are
decoded into `reference/X45_Star_Citizen_Button_Map.xlsx` for reference,
alongside the full project notes in `reference/X45_Project_Notes.md`.

## License

MIT — see `LICENSE`.
