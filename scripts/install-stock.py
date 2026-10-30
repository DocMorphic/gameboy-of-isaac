#!/usr/bin/env python3
"""Fresh isolated install on the specifically tested RG40XX V stock-derived firmware."""
import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

import isaac

SDL = '/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2800.5'
PATCHES = [
    ('0f2ec80f87f0010000', '0f28d048e910000000'),
    ('f30f59c2e881fee6fff30f10542410', 'f30f59c2f248904890f30f10542410'),
]


def patch_binary(data):
    for before, after in PATCHES:
        before, after = bytes.fromhex(before), bytes.fromhex(after)
        if data.count(before) != 1:
            raise ValueError('Unexpected executable: fractional scaling patch does not match exactly once')
        data = data.replace(before, after)
    return data


def menu_buttons(text):
    # The game's format uses numeric attribute names and is not valid XML.
    # A/B keep their shooting keys; only menu-context bindings change.
    for key, value in [('14-0', '68'), ('15-1', '83')]:
        text, count = re.subn(r'(?<![\w-])' + key + r'="[^\"]*"',
                             key + '="' + value + '"', text, count=1)
        if count != 1:
            raise ValueError('Unexpected input configuration')
    return text


def patch_weston(text):
    start = text.index('if [ -d "/opt/system/Tools/PortMaster/" ]; then')
    end = text.index('source $controlfolder/control.txt', start) + len('source $controlfolder/control.txt')
    text = text[:start] + ('controlfolder="$ISAAC_GAMEDIR/runtime/PortMaster"\n\n'
                          'source "$ISAAC_GAMEDIR/runtime/stock/control.txt"') + text[end:]
    old = 'export weston_dir="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"'
    if text.count(old) != 1:
        raise ValueError('Unexpected Weston directory assignment')
    text = text.replace(old, 'export weston_dir="${ISAAC_WESTON_DIR:?}"')
    old = 'while ! [[ -e $xfile ]]; do\n    sleep 0.1\ndone'
    if text.count(old) != 1:
        raise ValueError('Unexpected Weston startup loop')
    return text.replace(old, '''for attempt in $(seq 1 100); do
    [ ! -e "$xfile" ] || break
    sleep 0.1
done
if [ ! -e "$xfile" ]; then
    echo "XWayland failed to start within 10 seconds"
    cleanup
    exit 1
fi''')


def check_hardware():
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() != 0:
        raise ValueError('Run this installer as root on the handheld, not on the Mac')
    if Path('/mnt/vendor/oem/board.ini').read_text().strip() != 'RG40xxV':
        raise ValueError('Only the tested RG40XX V board is supported')
    fb = Path('/mnt/mod/ctrl/configs/fb.cfg').read_bytes()
    if len(fb) != 160 or struct.unpack_from('7I', fb) != (640, 480, 640, 960, 0, 0, 32):
        raise ValueError('Firmware framebuffer configuration differs from the tested device')
    for name in (SDL, '/usr/lib/libmali.so.0', '/dev/fb0', '/dev/mali0'):
        if not Path(name).exists():
            raise ValueError('Missing tested firmware dependency: ' + name)
    for command in ('unsquashfs', 'gcc', 'mount', 'bash', 'amixer'):
        if not shutil.which(command):
            raise ValueError('Missing command: ' + command)


def extract_pm(archive, runtime):
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            dest = isaac.safe_path(runtime, entry.filename)
            if Path(entry.filename).parts[0] != 'PortMaster' or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unexpected PortMaster archive entry')
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as src, dest.open('wb') as out:
                    shutil.copyfileobj(src, out)
                dest.chmod(0o755 if entry.external_attr >> 16 & 0o111 else 0o644)


def install(bundle, ports, apply):
    check_hardware()
    manifest = isaac.verify_bundle(bundle)
    ports = ports.resolve()
    if not ports.is_dir():
        raise ValueError('Ports directory must already exist')
    # Weston invokes an upstream shell command string; limit destinations to safe characters.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(ports)):
        raise ValueError('Ports directory must contain only letters, numbers, /, ., _, and -')
    for name in ('tboirebirth', isaac.LAUNCHER):
        if os.path.lexists(ports / name):
            raise ValueError('Refusing to overwrite existing installation/saves: ' + str(ports / name))
    with zipfile.ZipFile(bundle / 'dependencies/PortMaster.zip') as z:
        expanded = sum(e.file_size for e in z.infolist())
    needed = sum(v['size'] for v in manifest.values()) + expanded + 128 * 1024 * 1024
    if shutil.disk_usage(ports).free < needed:
        raise ValueError('Insufficient storage for isolated installation')
    print('Verified hardware and bundle. Destination:', ports)
    if not apply:
        print('Dry run only; repeat with --apply to install.')
        return
    with tempfile.TemporaryDirectory(prefix='.isaac-stock-', dir=ports) as tmp:
        game = Path(tmp) / 'tboirebirth'
        shutil.copytree(bundle / 'ports/tboirebirth', game)
        for name, expected in manifest.items():
            if name.startswith('ports/tboirebirth/'):
                isaac.check_file(game / name[len('ports/tboirebirth/'):], expected)
        runtime = game / 'runtime'
        runtime.mkdir()
        extract_pm(bundle / 'dependencies/PortMaster.zip', runtime)
        squash = runtime / 'weston_pkg_0.2.squashfs'
        shutil.copyfile(bundle / 'dependencies' / squash.name, squash)
        isaac.check_file(squash, {'sha256': isaac.digest(bundle / 'dependencies' / squash.name)})
        wrapper = subprocess.check_output(['unsquashfs', '-cat', str(squash), 'westonwrap.sh'], text=True)
        (runtime / 'westonwrap-stock.sh').write_text(patch_weston(wrapper))
        shutil.copytree(Path(__file__).parent / 'stock', runtime / 'stock', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(isaac.ROOT / 'steam-depot.lock.json', runtime / 'steam-depot.lock.json')
        subprocess.run(['gcc', '-O2', '-fPIC', '-shared', str(runtime / 'stock/fps-monitor.c'),
                        '-o', str(runtime / 'libfps-sdl.so'), '-Wl,--no-as-needed', SDL, '-ldl'], check=True)
        exe = game / 'gamefiles/isaac.x64'
        (game / 'gamefiles/isaac.x64.hack').write_bytes(patch_binary(exe.read_bytes()))
        conf = game / 'conf/binding of isaac rebirth'
        conf.mkdir(parents=True, exist_ok=True)
        (conf / 'options.ini').write_text((game / 'patch/options.ini').read_text().replace('VSync=0', 'VSync=1'))
        (conf / 'inputconfigs.dat').write_text(menu_buttons((game / 'patch/inputconfigs.dat').read_text()))
        shutil.copyfile(game / 'patch/config.ini', game / 'gamefiles/resources/config.ini')
        shutil.copytree(game / 'patch/gfx', game / 'gamefiles/resources/gfx', dirs_exist_ok=True)
        for name in ('box64', 'gamefiles/isaac.x64.hack', 'runtime/PortMaster/gptokeyb2'):
            (game / name).chmod(0o755)
        launcher = Path(tmp) / isaac.LAUNCHER
        launcher.write_text('#!/bin/sh\nDIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
                            'exec python3 "$DIR/tboirebirth/runtime/stock/supervisor.py"\n')
        launcher.chmod(0o755)
        game.rename(ports / 'tboirebirth')
        launcher.rename(ports / isaac.LAUNCHER)
    apps = ports.parent / 'APPS'
    shortcut = apps / 'Isaac Rebirth.sh'
    if apps.is_dir() and not os.path.lexists(shortcut):
        shortcut.write_text('#!/bin/sh\nexec python3 "' + str(ports / 'tboirebirth/runtime/stock/supervisor.py') + '"\n')
        shortcut.chmod(0o755)
    print('Installed. Launch from the handheld Ports menu, then complete docs/TESTING.md.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--ports-dir', type=Path, default=Path('/mnt/mmc/Roms/PORTS'))
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    try:
        install(a.bundle, a.ports_dir, a.apply)
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print('Error:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
