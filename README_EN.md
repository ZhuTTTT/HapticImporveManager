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
  toggle, game launching, and injection config all belong to the current game
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

Download `HapticImproveManager.zip` from [Releases](../../releases), extract
it, and double-click `HapticImproveManager.exe` (keep the whole folder
together — copying just the exe won't work).

> Zero dependencies, ready to run: the injection chain ships frozen in the
> package — `injector.exe`, `haptic_launcher.exe`, and
> `zzz_inject/wasapi_relink.dll` under `chain/`. No Python or any external
> dependency required.

> **Upgrading from ≤v0.2.0**: toggle IFEO off and back on once for each game.
> The old pythonw-based debugger value left in the registry no longer matches,
> so the game status shows "IFEO is taken by another debugger" until you
> re-toggle — that fixes it.

### Option 2: Run from source

Requires Windows 10/11 + Python 3.11+:

```bash
python -m pip install -r requirements.txt
python app.py
```

## How It Works

PC games render DualSense haptics as an audio stream and push it through
WASAPI shared mode to the controller's audio endpoint (4 channels: ch1/2 =
speakers, ch3/4 = haptic motors). The audio buffer the game requests
(20–85ms) is the main source of haptic latency.

The injection chain bundled with this tool (`injector.exe` /
`haptic_launcher.exe` under `chain/`, developed in the specialk project and
frozen at build time) injects the
[wasapi_relink](https://github.com/Litttlefish/wasapi_relink) DLL into the
game process, shrinking the buffer at the WASAPI level and pacing the writes.
This GUI handles game registration, config editing (`redirect_config.toml`),
IFEO auto-injection management, and log diagnostics.

## Architecture

Thin GUI (PySide6 + [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets))
+ subprocess backend. The GUI runs unelevated; the launcher escalates via UAC
on its own when toggling IFEO.

- The injection chain ships frozen under `chain/`: `injector.exe` (launched by
  IFEO, windowless), `haptic_launcher.exe` (GUI subprocess), and
  `zzz_inject/wasapi_relink.dll`; `games.yaml` and injection logs are written
  there at runtime
- The game registry `games.yaml` is shared between the GUI and the CLI
- `ui/config_model.py` is a pure-function form ↔ TOML mapping (unit-testable,
  comment-preserving)
- GUI settings (theme / log directory) live in
  `%APPDATA%/HapticImproveManager/gui_config.json`
- Design and implementation docs are in `docs/superpowers/`

## Tests

```bash
python -m pytest tests/ -v
```

## Build the exe yourself

```cmd
packaging\build_exe.bat
```

Output goes to `dist\HapticImproveManager\` (onedir mode, including the
`chain\` injection chain). The chain source path is the `SPECIALK` constant at
the top of the script (build-time only, not needed at runtime) — adjust it as
needed. The script reports `[FAIL]` explicitly on build errors (e.g. `dist\`
locked because the exe is still running).
