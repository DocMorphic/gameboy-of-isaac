# gameboy of isaac

Prepare **The Binding of Isaac: Rebirth** for an **Anbernic RG40XX V**, using BinaryCounter's existing PortMaster port and your own Steam copy.

**Status: installation bundle prepared and checked; installation on the target handheld and gameplay are still unverified.** This repository provides setup tooling, not a newly written game engine or a Game Boy ROM. The target is the Linux Anbernic handheld.

## What runs

The selected port runs the original Linux x86-64 **base Rebirth** executable through Box64, GL4ES and Westonpack. It includes handheld controls and performance options. It does **not** support Afterbirth, Afterbirth+, Repentance, or the GOG build. Your macOS executable cannot substitute for the Linux depot.

The RG40XX V's firmware matters. PortMaster lists muOS, KNULLI and ROCKNIX for this model. Original Anbernic firmware is not officially supported. A separate [StockOS MOD adaptation](https://github.com/kai4man/PortMaster-for-StockOS-MOD) lists Rebirth as working, but requires its system patches; that does not establish compatibility with an untouched stock installation. See [the research notes](docs/RESEARCH.md).

## Prepare on the Mac

Requires Python 3.9+, `curl`, Steam, and a Steam account that owns Rebirth. No Python packages are needed.

1. Open Steam's console using `steam://open/console`.
2. Run this exact command and wait for **Depot download complete**:

   ```text
   download_depot 250900 250903 5148620425580684010
   ```

3. From this repository, prepare and verify:

   ```sh
   python3 scripts/isaac.py prepare
   python3 scripts/isaac.py verify
   ```

The tool searches both common Mac Steam depot locations. For a different library, use `prepare --depot "/path/to/depot_250903"`. It checks every expected game file against `steam-depot.lock.json`, downloads the pinned official packages, checks SHA-256 digests, and builds:

```text
.local/ready/
  ports/
    Binding Of Isaac Rebirth.sh
    tboirebirth/
      gamefiles/               # your private Steam files
      box64, launcher/, patch/, licenses/, ...
  dependencies/
    weston_pkg_0.2.squashfs
    PortMaster.zip              # includes LÖVE 11.5 launcher support
  bundle-manifest.json
```

All downloaded binaries and purchased game files stay in the ignored `.local/` directory. **Do not publish or upload that directory.** Preparing a second bundle refuses to replace an existing one; verify it or move it aside first.

## Connect the handheld

A USB-C charging connection does not guarantee file access. If the Mac sees no USB device, no external disk, and no ADB device, the install cannot be delivered over that connection yet.

- On stock firmware, check **App Center → Apps → TF1 → SSH_Server**, if your firmware provides it. Connect both devices to the same trusted Wi-Fi, enable that app, and obtain the handheld's IP address and firmware version from Settings. Older releases may not include this app. Use the credentials documented by that firmware. The USB cable alone is not sufficient evidence of access.
- On muOS, USB Function can provide ADB or MTP; SSH/SFTP is also available through Web Services. Menu locations vary by version.
- An SD-card reader is another route. Shut down the handheld before removing its card. Identify the actual mounted card and existing firmware before copying files.

For an accessible Linux handheld, this read-only check records its architecture, OS, graphics devices, storage, and likely PortMaster locations:

```sh
ssh USER@HANDHELD_IP sh -s < scripts/device-check.sh
```

No firmware flashing, partitioning, credential changes, or automatic device selection is performed by this project.

## Install on compatible firmware

First confirm the device/firmware combination and install or update PortMaster using [its official instructions](https://portmaster.games/installation.html). The bundled official `PortMaster.zip` is available for offline setup, but is **not a StockOS MOD installer**. Do not blindly extract it over a working stock adaptation.

For a card or network share mounted on the Mac, supply the **existing** Ports folder and the **active** PortMaster folder. Paths below are placeholders to replace with those identified on your device:

```sh
python3 scripts/isaac.py install \
  --ports-dir "/Volumes/YOUR_CARD/path/to/ports" \
  --portmaster-dir "/Volumes/YOUR_CARD/path/to/PortMaster"
```

This is a dry run. After reviewing its destination paths and confirming firmware compatibility, repeat with `--apply`. The installer checks for PortMaster/LÖVE, available space, and existing files; stages and verifies the game; and copies Westonpack into PortMaster's `libs/` directory. It refuses to overwrite an existing Isaac installation, saves, or a different Weston runtime. It does not install missing firmware dependencies.

If PortMaster lives on an unmounted Linux filesystem, use SSH/SFTP or the firmware's PortMaster installation workflow instead of inventing a Mac path. Game placement on the handheld must agree with the launcher's configured Ports directory.

Eject mounted media cleanly, boot the handheld, and open **Binding Of Isaac Rebirth** from Ports. Keep the launcher's default performance options for the initial test. Enable fullscreen in the game if needed. Complete [the gameplay checks](docs/TESTING.md) before calling the installation finished.

## Controls on the RG40XX V

| Input | Action |
| --- | --- |
| D-pad / left stick | Move and navigate |
| Face buttons | Shoot in the corresponding direction |
| L1 | Bomb |
| R1 | Pill / card |
| L2 | Drop trinket |
| R2 | Active item |
| Start | Confirm |
| Select | Pause / back |
| Guide/menu button | Map, subject to firmware mapping |

If face-button firing directions are wrong, use the launcher's alternate button-layout options. The RG40XX V has one stick; the face buttons provide the second directional control set.

Save/config data is under `ports/tboirebirth/conf/`. Back it up before upgrading. This project does not import desktop saves or configure Steam Cloud.

## Validation and credits

```sh
python3 -m unittest discover -s tests -v
sh -n scripts/device-check.sh
python3 scripts/isaac.py verify
```

The tests cover corrupt files, unsafe archive paths, symlink escapes, preserving existing saves, dry-run behavior, and installation with copy verification. They do not measure FPS or emulate the target handheld.

Port and optimizations: [BinaryCounter / PortMaster](https://github.com/PortsMaster/PortMaster-New/tree/main/ports/tboirebirth). Runtime translation: [ptitSeb/box64](https://github.com/ptitSeb/box64), [ptitSeb/gl4es](https://github.com/ptitSeb/gl4es). Game: Edmund McMillen and Nicalis. Original scripts here are MIT licensed; upstream components retain their own licenses. This repository distributes no commercial game data.
