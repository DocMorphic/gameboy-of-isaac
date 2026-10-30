# Target acceptance checks

**Hardware validation: 2026-10-30, RG40XX V, firmware V1.0.8 (20250915), StockOS MOD marker 3.7.** The full base Rebirth installation runs locally with the Mali-G31 GPU. This is a working installation, with the remaining coverage limits below.

| Check | Result |
| --- | --- |
| Game files | Exact Steam Linux depot verified; all 178 transferred game/port files checked |
| Graphics | Native Mali acceleration; game screenshots inspected at 640×480; normal, treasure and sacrifice rooms rendered |
| Audio | Owner confirmed audible game sound; PCM stream running without device-busy error |
| Volume buttons | Both physical event devices handled; owner confirmed physical Volume +/− changed audible volume after the final fix |
| Controls | Physical movement/shooting confirmed by owner; remote tests verified A confirm, B back, B shooting without pause, directional shooting, movement, bomb and map inputs |
| Gameplay | Early Basement combat on normal/hard runs, enemies/projectiles, damage, death, item pickup and room transitions exercised |
| Save/relaunch | Used in-game Exit Game, quit to frontend, relaunched and Continued; seed, room, health and inventory matched |
| Cleanup | Weston/controller helper exited and frontend restarted; save/config testing used an isolated copy |
| Source checks | Seventeen installer/patch/input/startup safety tests passed; shell syntax checked; native diagnostics compiled with warnings treated as errors |

A subsequent owner report described a blank display after physical Start. Remote tests now inject the firmware's Start event (code 311) through the kernel input device, exercising the controller mapper instead of sending only X11 Enter. With profiling disabled, title → file selection → Continue → gameplay rendered correctly in direct framebuffer captures. The duplicate firmware keyboard is now isolated while retaining its volume handling, and Select/Menu indices are corrected against the device tree. A physical Start press was recorded on the handheld, and a subsequent direct framebuffer capture showed the running game.

Follow-up caught a real `SIGABRT` with `double free or corruption (fasttop)` while freeing a GLib hash-table entry. Inspection of the pinned X11 cache identified the same allocated key inserted into both tables with two key destructors. The adaptation now removes key ownership from the first table; the second table owns and frees the shared key after the first table has removed its entry. A native GLib regression experiment reproduced an abort with the original ownership and passed **10,000 refreshes plus cleanup** with corrected ownership. Unit tests guard the precise patch and preserve the timestamp-key and both value destructors. Debugging used a small RAM-resident debugger and bounded text backtraces, without large crash dumps.

The corrected game then ran for more than two minutes through the normal SDL path with profiling and temporary trace libraries disabled, including eight controller-driven pause/resume cycles. Direct framebuffer captures showed gameplay and pause menus; a normal in-game exit and quit returned exit code **0**, released the temporary keyboard grab and mounts, and restored the frontend. Original save hashes matched the pre-test backup. The test save copy and temporary debugger were removed afterward.

Startup follow-up: the original archive-loading stage logged **28,212 ms**. After native asset verification and the guarded checksum patch, repeated launches logged **111–1,735 ms** for that stage. These figures are archive-stage times, not total launch time. Initial native verification took approximately 27 seconds once; unchanged later launches reuse its cached result. Screenshots confirmed the intro was skipped and both title and saved room fit the 640×480 panel with the shorter X11 cache interval. Intro configuration tests verify ending cutscenes are retained.

The development card was found mounted read-only with FAT errors affecting two diagnostic log chains and orphan clusters. Save/config and FAT metadata backups were made privately before an offline filesystem repair. No save `.dat` damage was reported, packed assets passed SHA-256 verification, and card writes worked after repair. The launcher does not automatically repair cards; its new read-only check prevents playing with unwritable saves.

The game is base **Rebirth v1.032**, using the pinned Linux depot and upstream PortMaster port. DLCs are not included.

## Ability controls

The control audit checks the complete input path: firmware button events → controller mapping → game keyboard bindings → visible game effects. It corrected crossed X/Y entries in the custom mapping; physical X now shoots up and Y shoots left. A and B shoot right and down.

| Input | Representative effect checked |
| --- | --- |
| R2 | Book of Belial activated and spent its charge; Doctor's Remote produced its aiming target and missile |
| R1 | The Magician card and a pill were consumed; the game reported its PillCard action |
| L1 | Bomb stock decreased from five to four and the bomb exploded |
| L2, tap | With Starter Deck and two cards, selection changed from 2 of Spades to The Magician |
| L2, hold | Held card and trinket were dropped onto the floor |
| X / Y, hold then release | Brimstone charged and fired upward / leftward respectively |
| Face buttons after R2 | Doctor's Remote target moved using the shooting controls |
| A then X | Ludovico's tear moved right and upward independently of the stationary player |
| Menu, hold | Expanded map and elapsed-time overlay appeared |

Tests used a separate save/config copy and temporary RAM-backed character definitions to obtain representative equipment without grinding unlocks. The character override is removed when the test process exits. Game archives are reused unchanged; the public repository contains neither these extracted definitions nor save data or screenshots. No per-item control patch was needed; the only mapping correction from this audit was X/Y direction order.

Passive powers apply without a dedicated button. Active items share R2, consumables share R1, and attack modifiers retain the shooting controls. Charge bars, item cooldowns, resources and short activation animations still determine when an action can be used. These checks exercise the input mechanisms; they do not claim exhaustive validation of every collectible, synergy or DLC mechanic.

## Performance evidence

The target's native refresh rate is approximately 59.7 Hz. With the original `VSync=0`, inspected gameplay samples were generally 58–60 FPS with recurring frame intervals around 35–38 ms. With `VSync=1`, inspected samples stabilized near 59.7 FPS with fewer long frame intervals. The stock adaptation therefore enables VSync.

A timed 6.61-second early combat interval produced six complete one-second samples of **59.70–59.71 FPS**, with a maximum frame interval of **25.78 ms**, three frames over 25 ms total, and none over 50 ms. This interval contained no screenshot readback. Screenshots themselves can cause approximately 100 ms stalls and are excluded from performance measurements. Loading new archives/rooms also causes stalls and is reported separately from steady gameplay.

A separate **61-second sustained shooting test** in the empty starting room averaged **59.71 FPS** across 59 complete samples (range **59.33–60.05 FPS**), with a maximum frame interval of **26.9 ms** and **zero frames over 50 ms**. The reported temperature at the end was 58.1 °C. See the [raw timing samples](benchmarks/rg40xxv-sustained.csv) and [measurement context](benchmarks/rg40xxv-sustained.json). This measures sustained presentation and shooting, not a late-game stress scene.

**Coverage limits:** no full-game completion, late-floor stress run, every boss/item combination, HDMI/headphone validation, or power-cycle test was performed. Early-game measurements are not a guarantee of constant performance in every situation. The full base game's assets are installed; this is not a demo or a subset of levels.

## Repeatable acceptance checks

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
| Immediately returns to menu | On this stock adaptation, `/dev/shm/gameboy-of-isaac/log.txt`; on upstream PortMaster, `ports/tboirebirth/log.txt`. Check Linux depot, PortMaster location and dependencies |
| Cannot find Weston runtime | Active PortMaster `libs/weston_pkg_0.2.squashfs`; compare SHA-256 with the lock file |
| Launcher fails before game | `runtimes/love_11.5/`, graphics/backend support and controller helper |
| Keyboard-related game crash | Keep XKB Crash Fix enabled |
| Poor performance | Preserve default effect reduction, overlay reduction and X11 caching; verify GPU acceleration before tuning further |
| Incorrect shot directions | Try the launcher's alternate button layout; verify each physical button |
| Small image | Fractional scaling enabled; fullscreen in game |
| Stock OS fails despite copied files | Stock OS is not officially supported; inspect StockOS MOD patches or use supported firmware |

Back up `ports/tboirebirth/conf/` before upgrades. This installer intentionally refuses to replace existing installations.
