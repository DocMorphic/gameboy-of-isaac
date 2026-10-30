# RG40XX V stock-derived firmware adaptation

The development target reports **RG40xxV**, firmware **V1.0.8 (20250915)**, with a **StockOS MOD 3.7 marker** and the original Anbernic interface. This is a tested configuration, not a claim that every stock firmware release works.

The installed game is under `Roms/PORTS/tboirebirth`. Launch **Binding Of Isaac Rebirth** from the PORTS category in RA Game, or use the **Isaac Rebirth** shortcut in App Center → Apps on the internal card. Some menu versions omit the card selector when only one card is available. Restart the frontend after adding a launcher if it has cached its game list.

## Reproduce a fresh installation

Prepare the private bundle on the Mac using the README instructions. Transfer this repository (excluding `.git` and `.local`) and the contents of `.local/ready` to the handheld using SSH/SFTP or an SD-card reader. These files include your purchased game and must remain private. On the handheld:

```sh
python3 /path/to/gameboy-of-isaac/scripts/install-stock.py \
  --bundle /path/to/private-ready \
  --ports-dir /mnt/mmc/Roms/PORTS
```

This checks the exact board, framebuffer configuration, SDL/Mali libraries, compiler, hashes, and available space. Repeat with `--apply` to install. Existing installations and saves are refused. This installer runs on the handheld, not on the Mac, and does not replace the system's PortMaster or flash firmware.

## How the adaptation works

- A private PortMaster runtime supplies the controller helper; Westonpack supplies headless XWayland, Crusty and GL4ES. The native Mali-G31 driver renders the game.
- The supervisor temporarily applies the firmware's 640×480, 32-bit framebuffer configuration and restores the previous mode on exit.
- The launcher uses the firmware's newer SDL 2.28 library and an explicit mapping for the built-in controller. Crusty's cached library symlinks are refreshed on launch.
- The in-game Fullscreen option stays off: the native backend already fills the panel, while the original fullscreen switch caused inconsistent virtual window sizes during testing. VSync is enabled for more even frame pacing.
- The upstream fractional scaling, reduced effects, reduced overlays, X11 cache and XKB fixes are retained. The executable patch requires exactly one match for each original byte sequence.
- A private ALSA configuration avoids the firmware hook that locks the digital mixer at full volume. A small event listener handles the dedicated volume keys, maintains the firmware's 0–10 volume value, and stops when the game exits.
- A/B menu actions are configured independently of their shooting actions. Start/Select remain available.

Always launch through the menu for normal play. Suspending a running frontend leaves its audio device open and prevents Isaac from playing sound. Development used a temporary remote harness to close/restart the frontend; that harness is not needed for normal use.

## Diagnostics and storage

`fps.csv` records native SDL buffer-swap timing, including frame intervals over 25 ms and 50 ms. This measures presentation calls, not the game's internal simulation rate. Loading screens and diagnostic screenshots must be separated from gameplay samples. The CSV is capped at approximately 256 KiB, and the supervisor keeps at most two 1 MiB logs, filtering repetitive GL readback tracing.

A screenshot is only captured when both `ISAAC_CAPTURE_REQUEST` and `ISAAC_CAPTURE_FILE` are set and the request file is created. It reads the native GPU framebuffer; ordinary X11 screenshots cannot see this rendering path. Captures are private and must not be added to this source repository.

`ISAAC_CONFIG_DIR` can point to a separate test copy of `conf`. Tests reuse the same game files and runtime. On the development device, the save/config copy occupies about 616 KiB. Remove that copy and temporary captures after testing. Preserve the real `conf` directory when uninstalling or upgrading.
