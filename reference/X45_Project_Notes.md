# X45 Star Citizen Project — Notes (as of 2026-10-08)

Pick this back up tomorrow. Everything below is what we've confirmed, decided, and still need to do.

## Original goal
Set up the Saitek X45 HOTAS for Star Citizen using the old files found in
`C:\Users\Lonnon\Downloads\X45 total package` (SST software, two `.pr0` profiles, nine
`layout_my_x45a..i.xml` keybind exports from 2016).

## What we found in the old package
- **SD6 driver** (`Saitek_X45_Flight_Controller_SD6_64.exe`) — small, installed successfully, no issues.
- **SST software** (235MB, v6.6.6.9, from 2016) — installer requires the legacy .NET Framework
  2.0/3.5 runtime. `Enable-WindowsOptionalFeature -Online -FeatureName NetFx3 -All` failed with
  **"Class not registered"** (a DISM/COM servicing-stack issue, unresolved). We ended up not needing
  SST at all (see below), so this was never chased further.
- **The two `.pr0` SST profiles** ("3 mode" and "9 mode") were decoded by hand (they're UTF-16
  bracket-syntax config files, not executables — no IP issue reading them). Key finding:
  - The "9 mode" profile uses the Mode switch (3 pos) × Aux slider (3 pos) = 9 combinations, but
    each combination just fires a macro that types the console command `pp_rebindkeys layout_my_x45X`
    to load one of the nine XML files.
  - **All nine `layout_my_x45a.xml` … `layout_my_x45i.xml` files are byte-identical** except for
    their internal name/timestamp. So the elaborate 9-way switching never actually did anything —
    there's only one real finished keybind layout in the whole package.
  - The "3 mode" `.pr0` is messier/unfinished — some internal macro names are literally "Untitled",
    "yup", "yes", "move", and one is even named "x52" (a different Saitek stick), suggesting a copied,
    never-cleaned-up test profile. Not worth using.
  - Decoded button/axis → Star Citizen action map for the one real layout is saved in
    `X45_Star_Citizen_Button_Map.xlsx` (same Documents folder), sheets "9-Mode Profile" and
    "3 vs 9 Mode Comparison".

## Decision: build our own open-source tool instead of SST
You asked to reverse-engineer SST's *behavior* (not decompile their binary — that's a real
copyright/EULA line we're not crossing) and build something fresh we can publish on GitHub.
Plan agreed: a small Python tool that reads the X45 directly via SDL2 (`pygame`) and remaps its
buttons through a **vJoy** virtual joystick based on Mode/Aux switch position, so Star Citizen just
sees normal virtual buttons — no console macros, no SST, no `.NET` fights.

## Real hardware button map — confirmed via live testing tonight
Spent a long session capturing live data straight off your plugged-in X45 (not just inferring from
the old file). Key lesson: the old `winmm` Windows joystick API silently drops some buttons —
**SDL2 (`pygame`) is the reliable one to build on.**

Python 3.13 (not 3.14 — pygame has no prebuilt wheel for 3.14 yet) at
`C:\Users\Lonnon\AppData\Local\Programs\Python\Python313\python.exe`, with `pygame` installed.

Confirmed 0-indexed SDL button map (26 buttons total):
| Buttons | Control |
|---|---|
| 0–7 | Trigger, Fire A, Fire B, Launch, Fire D, Mouse Fire, Pinkie, Fire C |
| 8–10 | Mode switch (M1/M2/M3) — confirmed via SDL2 only; `winmm` can't see it at all |
| 11–13 | Aux slider (positions 1/2/3) |
| 14–17 | POV2 mini-hat (up/down/left/right) |
| 18–25 | Throttle hat + Mouse hat — **see hardware fault below, throttle hat does not work** |

Plus 6 axes (stick X/Y, throttle, rudder, 2 rotary knobs) and 1 main POV hat (POV1), all working.

## Hardware fault found: throttle hat is likely dead
Pressed all 4 directions of the small hat switch on the throttle grip — **nothing registered**,
not in our SDL2 capture, and not in the official Windows/Saitek DirectInput test panel either
(you checked directly). Since even the OS-level panel shows nothing, this isn't a software/API
gap like Mode was — it's almost certainly a real physical/electrical fault: a broken contact,
a cracked solder joint, or a loose ribbon cable inside the 20+ year old throttle unit.

**Decision pending:** open up the throttle unit and inspect/repair it, or just proceed without
that control (we still have 22 confirmed-working digital buttons plus the main hat and all axes —
plenty for the project either way).

## vJoy — installed and working
Installed `vJoySetup_v2.2.2.0_Win10_Win11.exe` from the actively-maintained, digitally-signed fork
at **github.com/BrunnerInnovation/vJoy** (NOT the original vjoystick.net site — that one has a
known malware warning, avoid it). Confirmed working: both "vJoy Driver" and "vJoy Device" show
status OK in Device Manager.

## Where things physically are
- Scratch scripts from tonight's diagnostics (winmm/pygame/raw HID capture probes) are in
  `C:\Users\Lonnon\AppData\Local\Temp\claude\` — these are **temp files and may get cleaned up**,
  nothing important is only there. Treat them as disposable scratch work, not a deliverable.
- The real keepable outputs so far: `X45_Star_Citizen_Button_Map.xlsx` (Documents) and this notes
  file.

## Next steps for tomorrow
1. Decide: repair the throttle hat, or proceed without it.
2. Set up a real project folder (e.g. `C:\Users\Lonnon\Documents\X45-OpenHOTAS` or similar) — don't
   keep building in the temp scratch folder.
3. Write the actual remapper: poll the X45 via `pygame`, compute Mode×Aux combo, remap physical
   button presses onto different vJoy virtual-button ranges per combo, output continuously to the
   vJoy device.
4. Bind the vJoy virtual device in Star Citizen's own keybinding screen (one-time, in-game).
5. Package it up (README, MIT license) and publish to your GitHub.
