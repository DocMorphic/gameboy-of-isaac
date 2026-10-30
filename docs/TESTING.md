# Target acceptance checks

**Current target gameplay result: NOT TESTED.** File hashes and installer tests are not substitutes for these checks.

Record the model, firmware version, PortMaster version, launch options and date when testing. Do not commit personal network addresses, credentials, game assets or save files.

1. Confirm Linux aarch64, graphics device availability and the active PortMaster location. Run `scripts/device-check.sh` over SSH when possible.
2. Verify the prepared bundle using `python3 scripts/isaac.py verify`. Install using the firmware's actual Ports directory; ensure Westonpack and LÖVE 11.5 are available.
3. Launch from the handheld's game menu. Confirm the configuration launcher and main game menu both render and that audio works.
4. Start a run. Test D-pad/stick movement and each of the four face-button shooting directions separately. Test bomb, active item, consumable, map and pause.
5. Play several rooms and a boss. Check busy rooms and later-floor effects when possible. Record actual slowdowns; do not claim a fixed FPS without measurements.
6. Exit a run normally, relaunch, and verify Continue restores it. Restart the handheld and verify again. Test a second save slot without disturbing an existing save.
7. Quit and launch another port to check compositor/input cleanup. Record any need to reboot.

## Troubleshooting

| Symptom | Inspect |
| --- | --- |
| Immediately returns to menu | `ports/tboirebirth/log.txt`, correct Linux depot, PortMaster location and dependencies |
| Cannot find Weston runtime | Active PortMaster `libs/weston_pkg_0.2.squashfs`; compare SHA-256 with the lock file |
| Launcher fails before game | `runtimes/love_11.5/`, graphics/backend support and controller helper |
| Keyboard-related game crash | Keep XKB Crash Fix enabled |
| Poor performance | Preserve default effect reduction, overlay reduction and X11 caching; verify GPU acceleration before tuning further |
| Incorrect shot directions | Try the launcher's alternate button layout; verify each physical button |
| Small image | Fractional scaling enabled; fullscreen in game |
| Stock OS fails despite copied files | Stock OS is not officially supported; inspect StockOS MOD patches or use supported firmware |

Back up `ports/tboirebirth/conf/` before upgrades. This installer intentionally refuses to replace existing installations.
