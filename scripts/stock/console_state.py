#!/usr/bin/env python3
"""Return the handheld console to firmware control after native SDL exits."""
import fcntl
import os
import struct
import termios
import time

VT_SETMODE = 0x5602
VT_GETSTATE = 0x5603
VT_ACTIVATE = 0x5606
VT_UNLOCKSWITCH = 0x560C
KDSETMODE = 0x4B3A
KDGKBMODE = 0x4B44
KDSKBMODE = 0x4B45
VT_AUTO = bytes(8)
KD_TEXT = 0


def active_vt(fd):
    state = bytearray(6)
    fcntl.ioctl(fd, VT_GETSTATE, state)
    number = struct.unpack_from('H', state)[0]
    if not 1 <= number <= 63:
        raise RuntimeError('Unexpected active virtual terminal')
    return number


def integer_state(fd, request):
    state = bytearray(4)
    fcntl.ioctl(fd, request, state)
    return struct.unpack('i', state)[0]


class ConsoleState:
    def __init__(self):
        control = os.open('/dev/tty0', os.O_RDWR)
        try:
            self.number = active_vt(control)
        finally:
            os.close(control)
        self.fd = os.open('/dev/tty%d' % self.number, os.O_RDWR)
        try:
            self.keyboard = integer_state(self.fd, KDGKBMODE)
            self.attributes = termios.tcgetattr(self.fd)
        except BaseException:
            os.close(self.fd)
            raise

    def restore(self):
        control = current = None
        try:
            control = os.open('/dev/tty0', os.O_RDWR)
            previous = active_vt(control)
            current = os.open('/dev/tty%d' % previous, os.O_RDWR)
            # Crusty's native SDL can leave VT_PROCESS and KD_GRAPHICS behind.
            # No frontend is running yet; release the game's terminal before
            # asking the kernel to switch, otherwise the next SDL 1.2 menu waits.
            fcntl.ioctl(current, VT_SETMODE, VT_AUTO)
            fcntl.ioctl(current, KDSETMODE, KD_TEXT)
            fcntl.ioctl(current, KDSKBMODE, self.keyboard)
            fcntl.ioctl(control, VT_UNLOCKSWITCH, 0)
            fcntl.ioctl(self.fd, VT_SETMODE, VT_AUTO)
            fcntl.ioctl(self.fd, KDSETMODE, KD_TEXT)
            fcntl.ioctl(self.fd, KDSKBMODE, self.keyboard)
            termios.tcsetattr(self.fd, termios.TCSANOW, self.attributes)
            fcntl.ioctl(control, VT_ACTIVATE, self.number)
            for attempt in range(40):
                if active_vt(control) == self.number:
                    return {'game_vt': previous, 'restored_vt': self.number,
                            'keyboard_mode': self.keyboard, 'status': 'restored'}
                time.sleep(.05)
            raise RuntimeError('Firmware console did not become active')
        finally:
            for fd in (current, control, self.fd):
                if fd is not None:
                    os.close(fd)
