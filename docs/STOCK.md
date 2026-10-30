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
- Exit cleanup also releases native SDL's graphics/process-controlled virtual terminal, enables terminal switching, restores the starting console's keyboard/terminal settings, and reactivates that console before the firmware starts its menu. Restoring the framebuffer alone leaves the menu waiting for terminal activation and showing a black screen.
- The launcher uses the firmware's newer SDL 2.28 library and an explicit mapping for the built-in controller. Physical A/B/X/Y map to indices 0/1/2/3, so shooting follows the button positions. Crusty's cached library symlinks are refreshed on launch.
- The in-game Fullscreen option stays off: the native backend already fills the panel, while the original fullscreen switch caused inconsistent virtual window sizes during testing. VSync is enabled for more even frame pacing.
- The upstream fractional scaling, reduced effects, reduced overlays and XKB fixes are retained. The X11 cache expiration is reduced from ten seconds to one second so faster startup still acquires the correct panel size. Its two hash tables share keys; only the timestamps table now owns those keys, preventing double frees during refresh and cleanup. Both tables still free their own values. Patches require pinned source hashes and expected byte sequences.
- `startup.py` verifies the original executable and packed archives against the pinned Steam SHA-256 manifest natively. It caches successful checks with file size, modification and change timestamps. It then generates a separate executable that bypasses redundant archive checksum work under Box64; original files remain intact. First launch, changed metadata or a missing cache requires full verification again.
- The opening intro alone is removed through a private loose cutscene configuration generated from the verified archive. Ending cutscenes remain present.
- A private ALSA configuration avoids the firmware hook that locks the digital mixer at full volume. A small event listener handles volume keys from both `ANBERNIC-keys` and `dierct-keys-polled`, deduplicates overlapping events, uses audible 3 dB analog steps and digital mute, maintains the firmware's 0–10 volume value, and stops when the game exits.
- A/B menu actions are configured independently of their shooting actions. Start/Select remain available.
- The volume helper exclusively reads the duplicate `dierct-keys-polled` keyboard while the game runs, preventing its unmapped keyboard events from reaching SDL alongside controller input. The joystick stays shared with the controller mapper. The launcher waits for this isolation before starting the game; closing the helper releases it automatically. Select and Menu map to the firmware's button indices 6 and 8 respectively; Start is index 7.
- The supervisor refuses to launch on a read-only game card and synchronizes saved data after the game exits.

Always launch through the menu for normal play. Suspending a running frontend leaves its audio device open and prevents Isaac from playing sound. Development used a temporary remote harness to close/restart the frontend; that harness is not needed for normal use.

## Diagnostics and storage

Current stock-adaptation logs are in `/dev/shm/gameboy-of-isaac`, a RAM filesystem cleared on reboot. The supervisor keeps at most two 1 MiB output logs and filters repetitive GL readback tracing. It also temporarily redirects the game's own log to RAM with a bind mount; save files stay on the card. Old logs beside the game are not current diagnostics.

`console-restore.json` records the game's active terminal and the console restored on exit. A successful game exit and a running `dmenu.bin` process alone do not prove that the menu is visible. On the tested firmware, the display engine's `capture_dump` interface can capture the composed display, including the menu's separate YUV layer, into one temporary BMP in RAM; `/dev/fb0` alone cannot capture that menu layer.

FPS recording is off during normal play. Set `ISAAC_DIAGNOSTICS=1` for a profiling launch: `fps.csv` records native SDL buffer-swap timing, including frame intervals over 25 ms and 50 ms, and is capped at approximately 256 KiB in RAM. This measures presentation calls, not the game's internal simulation rate. Loading screens and diagnostic screenshots must be separated from gameplay samples. `startup-timing.json` records the archive-stage time and the first panel-sized viewport after archive loading; inspect a screenshot to confirm the visible title state.

A screenshot is only captured when both `ISAAC_CAPTURE_REQUEST` and `ISAAC_CAPTURE_FILE` are set and the request file is created. It reads the native GPU framebuffer; ordinary X11 screenshots cannot see this rendering path. Captures are private and must not be added to this source repository.

`ISAAC_CONFIG_DIR` can point to a separate test copy of `conf`. Tests reuse the same game files and runtime. On the development device, the save/config copy occupies about 616 KiB. Remove that copy and temporary captures after testing. Preserve the real `conf` directory when uninstalling or upgrading.
