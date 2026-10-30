#!/usr/bin/env python3
"""Restore the firmware framebuffer and menu after the isolated game exits."""
import fcntl
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading


def write_log(stream, path):
    """Keep two bounded logs and discard GL4ES's repetitive per-pixel tracing."""
    log = path.open('w')
    try:
        for line in stream:
            if line.startswith(b'glReadPixels('):
                continue
            text = line[:8192].decode('utf8', 'replace')
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
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        fcntl.ioctl(fd, 0x4601, configured)
        env = dict(os.environ, ISAAC_GAMEDIR=str(game))
        child = subprocess.Popen(['bash', str(game / 'runtime/stock/run.sh')],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        logger = threading.Thread(target=write_log, args=(child.stdout, game / 'log.txt'), daemon=True)
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
        fcntl.ioctl(fd, 0x4601, saved)
        os.close(fd)
        lock.close()


if __name__ == '__main__':
    sys.exit(main())
