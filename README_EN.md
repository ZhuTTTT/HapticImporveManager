# HapticImproveManager

[中文](README.md) | English

A visual manager for the DualSense haptic low-latency injection pipeline — it
squeezes the haptic audio buffer that PC games send to the controller from the
native 20–85ms down to ~10ms, and manages the whole injection chain from a GUI.

![Dark theme](docs/screenshots/dark.png)

<details>
<summary>Light theme screenshot</summary>

![Light theme](docs/screenshots/light.png)
</details>

## Features

- **Game hub**: game list on the left (status dot + search), detail page on the
  right. Selecting a game sets the context — status badge, IFEO auto-inject
  toggle, game launching, and injection config all belong to the current game.
  Removing a game also turns off its IFEO auto-inject, leaving no registry
  leftovers
- **Plain-language injection config**: four modes (Normal / Virtual Buffer /
  Compatibility / Hands-off) as card-style radio options, every setting
  explained in plain words, buffer frames converted to milliseconds in real
  time, and settings that don't apply to the current mode hidden automatically
- **Add-game wizard**: pick an exe → anti-cheat signature detection
  (HoYoKProtect / EAC / BattlEye risk warnings) → generates
  `redirect_config.toml` → enable IFEO in one click
- **Diagnostics page**: recent injection results plus tail-follow of
  `injector_debug.log` / `wasapi_relink.log`, with one-click "open in Explorer"
- **Settings page**: light / dark / follow-system theme, Mica backdrop,
  changeable log directory with batch sync to all registered games
- **Multi-language**: switch between Follow system / 中文 / English in
  Settings; takes effect after restart

## Install & Run

### Option 1: Download the build (recommended)

Download from [Releases](../../releases):

- **`HapticImproveManager-Setup-x.y.z.exe` (installer, recommended)** —
  installs to `C:\Program Files\HapticImproveManager` (one UAC prompt;
  creates a Start Menu shortcut and grants write access to `chain\` so the
  app itself never needs admin). Upgrades install right over the top — the
  game registry and IFEO settings carry over; uninstalling cleans up the
  IFEO registry entries automatically
- **`HapticImproveManager.zip` (portable)** — extract and double-click
  `HapticImproveManager.exe` (keep the whole folder together; extract to a
  writable location, not Program Files)

> Zero dependencies, ready to run: the injection chain ships frozen in the
> package — `injector.exe`, `haptic_launcher.exe`, and `wasapi_relink.dll`
> under `chain/`. No Python or any external dependency required.

### Option 2: Run from source

Requires Windows 10/11 + Python 3.11+:

```bash
python -m pip install -r requirements.txt
python app.py
```

## Permissions (when UAC pops up)

The app itself **always runs unelevated** — never launch it as administrator.
However, IFEO auto-inject lives under an `HKLM` registry key, so changing it
needs admin rights; the bundled launcher elevates itself via UAC on demand.
A UAC prompt in the following situations is expected:

1. **Enabling IFEO auto-inject** (last step of the add-game wizard, or the
   IFEO toggle on the detail page)
2. **Disabling IFEO auto-inject** (the same toggle)
3. **Removing a game** whose auto-inject is on — IFEO is turned off first,
   then the game is removed. Clicking "Cancel" on that UAC prompt aborts the
   removal and keeps the game in the list (so no invisible registry leftover
   is left behind)

Separately, some games (e.g. Zenless Zone Zero) ship an exe whose own manifest
requires administrator — Windows shows a UAC prompt for the game itself when it
launches. That is the game's own behavior, unrelated to this tool.

With the installer, **installing/uninstalling** also shows one UAC prompt each
(writing to Program Files and the Start Menu needs admin) — that's the
installer, not the app.

## How It Works

PC games render DualSense haptics as an audio stream and push it through
WASAPI shared mode to the controller's audio endpoint (4 channels: ch1/2 =
speakers, ch3/4 = haptic motors). The audio buffer the game requests
(20–85ms) is the main source of haptic latency.

The injection chain (source lives in this repo's `chain/` directory, frozen
into exes at build time) injects the
[wasapi_relink](https://github.com/Litttlefish/wasapi_relink) DLL into the
game process, shrinking the buffer at the WASAPI level and pacing the writes.
This GUI handles game registration, config editing (`redirect_config.toml`),
IFEO auto-injection management, and log diagnostics.

## Project Structure

```
HapticImporveManager/
├─ app.py                   # Entry point
├─ backend/                 # Backend: path constants / game registry / IFEO / config / logs
├─ ui/                      # PySide6 + Fluent Widgets UI (thin GUI, unelevated)
├─ chain/                   # Injection chain (single source of truth, frozen into the package)
│   ├─ injector.py          #   Launched by IFEO, windowless; CreateProcess + remote-thread injection
│   ├─ haptic_launcher.py   #   GUI subprocess / CLI; self-elevates via UAC for IFEO toggles
│   └─ wasapi_relink.dll    #   The injected core DLL (third-party, Apache-2.0)
├─ i18n.py                  # Chinese/English strings
├─ tests/                   # pytest suite
├─ packaging/               # Packaging: build_exe.bat (app+chain zip)
│                           #             installer.iss + build_installer.bat (Inno installer)
├─ licenses/                # Third-party license texts
└─ docs/superpowers/        # Design and implementation docs
```

Runtime data lives in three places: the game registry `games.yaml` and GUI
settings in `%APPDATA%/HapticImproveManager/` (survives upgrades and reinstalls
— a registry left in the old `chain/` location is migrated on first launch);
injection logs inside the app folder under `chain/` (`logs/`,
`injector_result.txt`, etc.); and `redirect_config.toml` (the injection config
read by wasapi_relink) next to each game exe.

## Development

```bash
python -m pip install -r requirements.txt
python app.py                    # Run from source (the GUI uses the .py chain in chain/)
python -m pytest tests/ -v       # Tests
packaging\build_exe.bat          # Package: dist\HapticImproveManager\ + release zip
packaging\build_installer.bat    # Full release: the above + Inno installer (needs Inno Setup 6)
```

Packaging is fully self-contained: the GUI is frozen as an onedir exe, and the
`chain/` sources are frozen into `injector.exe` / `haptic_launcher.exe` and
bundled with `wasapi_relink.dll` under `dist\HapticImproveManager\chain\` — no
machine-specific path constants anywhere. `chain\` is rebuilt from scratch on
every build, so runtime leftovers from local test runs (e.g. a personal
`games.yaml`) never leak into the zip. The script reports `[FAIL]` explicitly
on build errors (e.g. `dist\` locked because the exe is still running).

When editing the chain sources, note that `IFEO_VALUE` is computed by the same
rule in three places — `backend/paths.py`, `chain/injector.py`, and
`chain/haptic_launcher.py` (the GUI uses it to recognize its own Debugger
value in the registry). Keep all three in sync; `tests/test_paths.py` has a
consistency test as a safety net.

## Acknowledgments

- [wasapi_relink](https://github.com/Litttlefish/wasapi_relink) (Litttlefish) —
  the core of haptic low latency: the DLL injected into game processes to
  shrink the audio buffer at the WASAPI level, redistributed under the
  Apache-2.0 license (see `licenses/`)
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)
  (zhiyiYo) — the Fluent Design component library behind the entire UI
- [XXMI](https://github.com/SpectrumQT/XXMI) / [3DMigoto](https://github.com/bo3b/3DMigoto)
  communities — the injection approach in `chain/injector.py`: launching the
  game as its creator, using the full-access handle returned by CreateProcess
  to bypass anti-cheat handle stripping

## License

[MIT](LICENSE) — free to use, modify, and redistribute (including
commercially), as long as the copyright notice is kept.

Third-party component: `wasapi_relink.dll` is redistributed under the
[Apache-2.0](licenses/wasapi_relink.LICENSE.txt) license, copyright
Litttlefish.
