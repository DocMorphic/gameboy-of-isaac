#!/usr/bin/env python3
"""Prepare and verify a private PortMaster Isaac installation. Python 3.9+."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local'
LAUNCHER = 'Binding Of Isaac Rebirth.sh'


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check_file(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Missing file or unexpected symlink: {path}')
    if 'size' in expected and path.stat().st_size != expected['size']:
        raise ValueError(f'Wrong file size: {path}')
    if digest(path) != expected['sha256']:
        raise ValueError(f'Checksum mismatch: {path}')


def safe_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or not path.parts:
        raise ValueError(f'Unsafe relative path: {name}')
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes destination: {name}')
    return target


def extract_port(archive, target):
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            dest = safe_path(target, entry.filename)
            top = PurePosixPath(entry.filename).parts[0]
            if top not in (LAUNCHER, 'tboirebirth'):
                raise ValueError(f'Unexpected port archive entry: {entry.filename}')
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f'Symlink in port archive: {entry.filename}')
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as src, dest.open('wb') as out:
                    shutil.copyfileobj(src, out)
                dest.chmod(0o755 if mode & 0o111 else 0o644)
    (target / LAUNCHER).chmod(0o755)
    (target / 'tboirebirth/box64').chmod(0o755)


def find_depot():
    steam = Path.home() / 'Library/Application Support/Steam'
    candidates = [steam / 'steamapps/content/app_250900/depot_250903',
                  steam / 'Steam.AppBundle/Steam/Contents/MacOS/steamapps/content/app_250900/depot_250903']
    for path in candidates:
        if (path / 'isaac.x64').is_file():
            return path
    raise ValueError('Linux depot not found. Run the Steam console command in README.md, then pass --depot.')


def verify_depot(depot):
    manifest = read_json(ROOT / 'steam-depot.lock.json')
    for name, expected in manifest['files'].items():
        check_file(safe_path(depot, name), expected)
    return manifest


def fetch():
    cache = LOCAL / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    for asset in read_json(ROOT / 'upstream.lock.json')['assets']:
        dest = cache / asset['name']
        if not dest.exists():
            partial = dest.with_suffix(dest.suffix + '.partial')
            subprocess.run(['curl', '-fLsS', '--retry', '3', '--connect-timeout', '30',
                            '-o', str(partial), asset['url']], check=True)
            check_file(partial, asset)
            partial.replace(dest)
        check_file(dest, asset)
        print(f"Verified {asset['name']}", flush=True)


def inventory(root):
    return {str(p.relative_to(root)): {'size': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'bundle-manifest.json'}


def prepare(depot):
    depot = depot or find_depot()
    game = verify_depot(depot)
    fetch()
    bundle = LOCAL / 'ready'
    if bundle.exists():
        raise ValueError(f'{bundle} already exists; use verify. Move it aside to prepare again.')
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=LOCAL) as tmp:
        stage = Path(tmp) / 'ready'
        ports = stage / 'ports'
        ports.mkdir(parents=True)
        extract_port(LOCAL / 'downloads/tboirebirth.zip', ports)
        gamefiles = ports / 'tboirebirth/gamefiles'
        for name in game['files']:
            dest = safe_path(gamefiles, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(depot / name, dest)
        (gamefiles / 'isaac.x64').chmod(0o755)
        deps = stage / 'dependencies'
        deps.mkdir()
        for name in ('weston_pkg_0.2.squashfs', 'PortMaster.zip'):
            shutil.copy2(LOCAL / 'downloads' / name, deps / name)
        (stage / 'bundle-manifest.json').write_text(json.dumps(inventory(stage), indent=2) + '\n')
        stage.rename(bundle)
    print(f'Prepared private bundle: {bundle}\nHardware installation and gameplay are NOT yet verified.')


def verify_bundle(bundle):
    manifest = read_json(bundle / 'bundle-manifest.json')
    for name, expected in manifest.items():
        check_file(safe_path(bundle, name), expected)
    verify_depot(bundle / 'ports/tboirebirth/gamefiles')
    for asset in read_json(ROOT / 'upstream.lock.json')['assets']:
        if asset['name'] != 'tboirebirth.zip':
            check_file(bundle / 'dependencies' / asset['name'], asset)
    print(f'Verified {len(manifest)} bundle files. This is file verification, not a gameplay test.')
    return manifest


def install(bundle, ports, pm, apply):
    manifest = verify_bundle(bundle)
    ports, pm = ports.resolve(), pm.resolve()
    if not ports.is_dir() or not pm.is_dir():
        raise ValueError('Both destination directories must already exist on the mounted card/share.')
    for required in ('control.txt', 'runtimes/love_11.5/love.txt', 'runtimes/love_11.5/love.aarch64'):
        if not (pm / required).is_file():
            raise ValueError(f'PortMaster installation incomplete: missing {required}. Install/update PortMaster on the handheld first.')
    if ports.is_relative_to(bundle.resolve()) or pm.is_relative_to(bundle.resolve()):
        raise ValueError('Destination must not be inside the prepared bundle.')
    for name in ('tboirebirth', LAUNCHER):
        if os.path.lexists(ports / name):
            raise ValueError(f'Refusing to overwrite existing installation/saves: {ports / name}')
    runtime = pm / 'libs/weston_pkg_0.2.squashfs'
    safe_path(pm, 'libs/weston_pkg_0.2.squashfs')
    runtime_src = bundle / 'dependencies/weston_pkg_0.2.squashfs'
    if os.path.lexists(runtime):
        check_file(runtime, {'sha256': digest(runtime_src)})
    needed = sum(v['size'] for k, v in manifest.items() if k.startswith('ports/'))
    if shutil.disk_usage(ports).free < needed + 64 * 1024 * 1024:
        raise ValueError('Not enough free space for the game and installation margin.')
    if shutil.disk_usage(pm).free < runtime_src.stat().st_size + 64 * 1024 * 1024:
        raise ValueError('Not enough free space for the Weston runtime and installation margin.')
    print(f'Game destination: {ports}\nRuntime destination: {runtime}')
    if not apply:
        print('Dry run passed. Use --apply after confirming device/firmware compatibility.')
        return
    # Stage on the destination filesystem. The launcher is exposed only after all hashes pass.
    with tempfile.TemporaryDirectory(prefix='.isaac-install-', dir=ports) as tmp:
        staging = Path(tmp)
        shutil.copytree(bundle / 'ports/tboirebirth', staging / 'tboirebirth')
        shutil.copy2(bundle / 'ports' / LAUNCHER, staging / LAUNCHER)
        for name, expected in manifest.items():
            if name.startswith('ports/'):
                check_file(staging / name[len('ports/'):], expected)
        if not runtime.exists():
            runtime.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix='.weston-', dir=runtime.parent, delete=False) as out:
                partial = Path(out.name)
                with runtime_src.open('rb') as src:
                    shutil.copyfileobj(src, out)
            try:
                check_file(partial, {'sha256': digest(runtime_src)})
                partial.chmod(0o644)
                partial.rename(runtime)
            finally:
                partial.unlink(missing_ok=True)
        (staging / 'tboirebirth').rename(ports / 'tboirebirth')
        (staging / LAUNCHER).rename(ports / LAUNCHER)
    print('Files installed and verified. Eject cleanly, launch on the handheld, then complete docs/TESTING.md.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('fetch', help='Download/check pinned official PortMaster packages')
    prep = commands.add_parser('prepare', help='Assemble a private bundle using your Linux Steam depot')
    prep.add_argument('--depot', type=Path)
    verify = commands.add_parser('verify', help='Check every prepared file')
    verify.add_argument('--bundle', type=Path, default=LOCAL / 'ready')
    ins = commands.add_parser('install', help='Fresh install to mounted storage; dry run by default')
    ins.add_argument('--bundle', type=Path, default=LOCAL / 'ready')
    ins.add_argument('--ports-dir', required=True, type=Path)
    ins.add_argument('--portmaster-dir', required=True, type=Path)
    ins.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'fetch':
            fetch()
        elif args.command == 'prepare':
            prepare(args.depot)
        elif args.command == 'verify':
            verify_bundle(args.bundle)
        elif args.command == 'install':
            install(args.bundle, args.ports_dir, args.portmaster_dir, args.apply)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
