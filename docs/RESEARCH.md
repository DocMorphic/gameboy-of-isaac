# Compatibility research

Checked 30 October 2026. These are upstream findings, not a claim that this particular handheld has passed testing.

## Selected route

[PortMaster's Rebirth metadata](https://github.com/PortsMaster/PortMaster-New/blob/293560abff0642dbb23d6497c601ca3c7a766652/ports/tboirebirth/port.json) specifies the aarch64 port, Westonpack 0.2, and Steam depot `250903`, manifest `5148620425580684010`. It explicitly excludes DLCs and GOG. Using this tested upstream route is substantially more practical than recreating the game's proprietary engine.

The [launcher source](https://github.com/PortsMaster/PortMaster-New/blob/293560abff0642dbb23d6497c601ca3c7a766652/ports/tboirebirth/Binding%20Of%20Isaac%20Rebirth.sh) additionally requires PortMaster's LÖVE 11.5 launcher runtime, gptokeyb/gptokeyb2, native graphics support, and the ability to mount the Weston squashfs. Copying only `isaac.x64` is insufficient.

[BinaryCounter's port notes](https://github.com/PortsMaster/PortMaster-New/blob/293560abff0642dbb23d6497c601ca3c7a766652/ports/tboirebirth/README.md) explain the fractional scaling modification, X11 call caching and keyboard crash fix. The upstream defaults also reduce visual effects and overlays. The project preserves these defaults; no unmeasured speedup or frame-rate guarantee is claimed here.

Pinned release packages and expected SHA-256 values are in `upstream.lock.json`. Game hashes in `steam-depot.lock.json` were calculated from the specified depot after Steam reported a successful authenticated download. These hashes identify files; they contain no game data or account credentials.

## Target and firmware

The [Anbernic RG40XX V specification](https://anbernic.com/products/rg-40xxv) identifies an H700 Linux handheld with a 640×480 display. It is an ARM handheld, not original Nintendo Game Boy hardware.

The [PortMaster supported-device list](https://jantrueno.github.io/PortMaster-Wiki/installation/supported-handhelds/) lists KNULLI, ROCKNIX and muOS for this model. [muOS also explicitly supports it](https://muos.dev/devices). The [PortMaster FAQ](https://jantrueno.github.io/PortMaster-Wiki/faq/) states that stock firmware is generally unsupported.

There is a separate [PortMaster-for-StockOS-MOD adaptation](https://github.com/kai4man/PortMaster-for-StockOS-MOD). Its maintainer says system patches are required and are included in StockOS MOD v3.9.8 onward. Its linked [working-ports table](https://docs.google.com/spreadsheets/d/1UlxRCSIfNkZIiCMAgo8eFqKhsIbrLA_1d3lFdVyS4q8/edit?gid=0) marks The Binding Of Isaac: Rebirth as working. That is evidence for the patched environment, not proof that any original Anbernic release can launch it unchanged. The original firmware and access method must be inspected before selecting this route.

The [StockOS MOD project](https://github.com/cbepx-me/Anbernic-H700-RG-xx-StockOS-Modification) supplies separate images/upgrade packages. No image has been flashed and no system patch has been applied by this setup kit.

## Connection findings

The Mac initially exposed no external USB device in IORegistry, no external disk in `diskutil`, and no device in `adb devices`. Common custom-firmware hostnames also did not resolve. These observations do not identify a bad cable conclusively: firmware mode, power state, or missing data support could explain them.

[muOS connectivity documentation](https://muos.dev/tour/modules/muxconnect) distinguishes ADB/MTP USB functions from SSH/SFTP web services. Stock firmware requires its own access mechanism. There is no remote software fix for an inaccessible physical card or a cable that supplies power but no usable data connection.

## Scope and remaining proof

The local preparation verifies all files, packages the entire selected base-game depot, and provides non-overwriting installation tooling. It cannot establish target launch, audio, directional controls, saving, stability, or frame pacing without access to the handheld. Those are the acceptance checks in `TESTING.md`.
