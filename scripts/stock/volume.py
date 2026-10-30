#!/usr/bin/env python3
"""Handle the RG40XX V volume keys while its frontend is closed."""
import os
from pathlib import Path
import select
import struct
import subprocess
import time

NODE = Path('/sys/class/power_supply/axp2202-battery/openbor_volume')
EVENT = struct.Struct('llHHi')


def set_volume(level):
    level = max(0, min(10, level))
    subprocess.run(['amixer', '-q', 'sset', 'digital volume', str(round(level * 63 / 10))], check=True)
    NODE.write_text(str(level))
    return level


def main():
    nodes = [Path('/dev/input') / p.parent.parent.name
             for p in Path('/sys/class/input').glob('event*/device/name')
             if p.read_text().strip() == 'dierct-keys-polled']
    if len(nodes) != 1:
        raise RuntimeError('Expected one firmware volume-key device')
    for control in ('LINEOUT', 'SPK', 'OutputL Mixer DACL', 'OutputR Mixer DACR'):
        subprocess.run(['amixer', '-q', 'sset', control, 'on'], check=True)
    level = set_volume(int(NODE.read_text().strip()))
    fd = os.open(nodes[0], os.O_RDONLY | os.O_NONBLOCK)
    last = 0.0
    try:
        while True:
            if not select.select([fd], [], [], 1)[0]:
                continue
            data = os.read(fd, EVENT.size * 64)
            for offset in range(0, len(data), EVENT.size):
                _, _, kind, code, value = EVENT.unpack_from(data, offset)
                if kind == 1 and code in (114, 115) and value in (1, 2):
                    now = time.monotonic()
                    if now - last >= .10:
                        level = set_volume(level + (1 if code == 115 else -1))
                        last = now
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
