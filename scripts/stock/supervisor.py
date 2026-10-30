#!/usr/bin/env python3
"""Restore the firmware framebuffer and menu after the isolated game exits."""
import fcntl
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
import time


def write_log(stream, path, started):
    """Keep two bounded logs and discard GL4ES's repetitive per-pixel tracing."""
    log = path.open('w')
    timings = {}
    try:
        for line in stream:
            if line.startswith(b'glReadPixels('):
                continue
            text = line[:8192].decode('utf8', 'replace')
            if text.startswith('load archives:'):
                timings['archive_ms'] = int(text.split(':', 1)[1].split()[0])
            if text.startswith(('Viewport: 640x479', 'Viewport: 640x480')) and 'archive_ms' in timings and 'title_ready_seconds' not in timings:
                timings['title_ready_seconds'] = round(time.monotonic() - started, 3)
                path.with_name('startup-timing.json').write_text(json.dumps(timings, indent=2)+'\n')
            if log.tell() + len(text.encode('utf8')) > 1024 * 1024:
                log.close()
                path.replace(path.with_suffix('.previous.txt'))
                log = path.open('w')
            log.write(text)
            log.flush()
    finally:
        log.close()


def main():
    game = Path(__file__).resolve().parents[2]
    logs = Path('/dev/shm/gameboy-of-isaac')
    logs.mkdir(parents=True, exist_ok=True)
    if os.statvfs(game).f_flag & os.ST_RDONLY:
        (logs / 'log.txt').write_text('Game card is read-only; saves cannot be written. Repair its filesystem before playing.\n')
        raise RuntimeError('Game card is read-only; saves cannot be written')
    lock = open('/tmp/gameboy-of-isaac.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    result = subprocess.run(['pidof', 'dmenu.bin'], capture_output=True, text=True)
    if result.stdout.strip():
        raise RuntimeError('Launch through the handheld menu; an active frontend holds the audio device open')
    fd = os.open('/dev/fb0', os.O_RDWR)
    saved = bytearray(160)
    fcntl.ioctl(fd, 0x4600, saved)
    configured = Path('/mnt/mod/ctrl/configs/fb.cfg').read_bytes()
    if len(configured) != 160 or struct.unpack_from('7I', configured) != (640, 480, 640, 960, 0, 0, 32):
        os.close(fd)
        raise RuntimeError('Unexpected firmware framebuffer configuration')
    child = None
    bound_log = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        fcntl.ioctl(fd, 0x4601, configured)
        env = dict(os.environ, ISAAC_GAMEDIR=str(game), ISAAC_LOG_DIR=str(logs))
        # Redirect the game's own verbose log to RAM while keeping saves on SD.
        conf = Path(env.get('ISAAC_CONFIG_DIR', str(game / 'conf')))
        target = conf / 'binding of isaac rebirth/log.txt'
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.touch()
        ram_log = logs / 'game.log'
        ram_log.write_bytes(b'')
        subprocess.run(['mount', '--bind', str(ram_log), str(target)], check=True)
        bound_log = target
        started = time.monotonic()
        (logs / 'startup-timing.json').unlink(missing_ok=True)
        child = subprocess.Popen(['bash', str(game / 'runtime/stock/run.sh')],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        logger = threading.Thread(target=write_log, args=(child.stdout, logs / 'log.txt', started), daemon=True)
        logger.start()
        result = child.wait()
        logger.join(timeout=2)
        return result
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            # The shell can exit before its descendants release open log files.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if bound_log is not None:
            for attempt in range(20):
                result = subprocess.run(['umount', str(bound_log)], capture_output=True)
                if result.returncode == 0:
                    break
                time.sleep(.1)
            else:
                print('Could not release temporary game log mount', file=sys.stderr)
        os.sync()
        fcntl.ioctl(fd, 0x4601, saved)
        os.close(fd)
        lock.close()


if __name__ == '__main__':
    sys.exit(main())
