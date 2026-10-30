#!/usr/bin/env python3
"""Handle the RG40XX V volume keys while its frontend is closed."""
import fcntl
import os
from pathlib import Path
import select
import struct
import subprocess
import time

NODE = Path('/sys/class/power_supply/axp2202-battery/openbor_volume')
EVENT = struct.Struct('llHHi')
EVIOCGRAB = 0x40044590


def set_volume(level):
    level = max(0, min(10, level))
    # The DAC's digital scale is logarithmic. Dividing its raw 0..63 range
    # linearly made most steps nearly inaudible. Use 3 dB analogue steps.
    if level:
        subprocess.run(['amixer', '-q', 'sset', 'lineout volume', str(11 + 2 * level)], check=True)
    subprocess.run(['amixer', '-q', 'sset', 'digital volume', '63' if level else '0'], check=True)
    NODE.write_text(str(level))
    return level


def find_devices(sys_input=Path('/sys/class/input'), dev_input=Path('/dev/input')):
    return [dev_input / p.parent.parent.name
            for p in sys_input.glob('event*/device/name')
            if p.read_text().strip() in ('ANBERNIC-keys', 'dierct-keys-polled')]


def open_devices(nodes, sys_input=Path('/sys/class/input')):
    """Keep firmware keyboard duplicates away from SDL; retain joystick input."""
    fds = []
    try:
        for node in nodes:
            fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
            fds.append(fd)
            name = (sys_input / node.name / 'device/name').read_text().strip()
            if name == 'dierct-keys-polled':
                fcntl.ioctl(fd, EVIOCGRAB, 1)
                print('Isolated duplicate firmware keyboard: ' + str(node), flush=True)
        return fds
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise


def main():
    nodes = find_devices()
    if not nodes:
        raise RuntimeError('No firmware volume-key devices found')
    for control in ('LINEOUT', 'SPK', 'OutputL Mixer DACL', 'OutputR Mixer DACR'):
        subprocess.run(['amixer', '-q', 'sset', control, 'on'], check=True)
    level = set_volume(int(NODE.read_text().strip()))
    fds = open_devices(nodes)
    last = {}
    print('Listening for volume keys on: ' + ', '.join(str(p) for p in nodes), flush=True)
    try:
        ready = os.environ.get('ISAAC_INPUT_READY')
        if ready:
            Path(ready).touch()
        while True:
            for fd in select.select(fds, [], [], 1)[0]:
                data = os.read(fd, EVENT.size * 64)
                for offset in range(0, len(data), EVENT.size):
                    _, _, kind, code, value = EVENT.unpack_from(data, offset)
                    if kind == 1 and code in (114, 115) and value in (1, 2):
                        now = time.monotonic()
                        if now - last.get(code, 0) >= .10:
                            previous = level
                            level = set_volume(level + (1 if code == 115 else -1))
                            last[code] = now
                            if level != previous:
                                print('Volume: %d/10' % level, flush=True)
    finally:
        for fd in fds:
            os.close(fd)


if __name__ == '__main__':
    main()
