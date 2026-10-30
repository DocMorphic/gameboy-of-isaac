"""Regression for a menu blocked in VT_WAITACTIVE after the game quits."""
from contextlib import ExitStack
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/stock'))
import console_state as console


class Terminals:
    def __init__(self):
        self.active = 1
        self.locked = False
        self.graphics = {1: 0, 2: 1}
        self.modes = {1: bytes(8), 2: struct.pack('BBhhh', 1, 0, 10, 12, 0)}
        self.fds = {}
        self.closed = []
        self.commands = []
        self.fail_unlock = False

    def open(self, path, flags):
        fd = len(self.fds)+100
        self.fds[fd] = int(path.removeprefix('/dev/tty'))
        return fd

    def ioctl(self, fd, command, arg):
        self.commands.append(command)
        terminal = self.fds[fd]
        if command == console.VT_GETSTATE:
            arg[:] = struct.pack('3H', self.active, 0, 0)
        elif command == console.KDGKBMODE:
            arg[:] = struct.pack('i', 3)
        elif command == console.VT_SETMODE:
            self.modes[terminal] = arg
        elif command == console.KDSETMODE:
            self.graphics[terminal] = arg
        elif command == console.VT_UNLOCKSWITCH:
            if self.fail_unlock:
                raise OSError('ioctl failed')
            self.locked = False
        elif command == console.VT_ACTIVATE:
            if self.locked or self.graphics[self.active] or self.modes[self.active][0]:
                raise RuntimeError('Menu would remain blocked waiting for its terminal')
            self.active = arg


class ConsoleTests(unittest.TestCase):
    def patched(self, terminals):
        stack = ExitStack()
        stack.enter_context(patch.object(console.os, 'open', terminals.open))
        stack.enter_context(patch.object(console.os, 'close', terminals.closed.append))
        stack.enter_context(patch.object(console.fcntl, 'ioctl', terminals.ioctl))
        stack.enter_context(patch.object(console.termios, 'tcgetattr', return_value=['saved']))
        restore = stack.enter_context(patch.object(console.termios, 'tcsetattr'))
        self.addCleanup(stack.close)
        return restore

    def test_exit_releases_graphics_and_switch_lock_before_returning(self):
        terminals = Terminals()
        restore = self.patched(terminals)
        state = console.ConsoleState()
        terminals.active = 2
        terminals.locked = True
        result = state.restore()
        self.assertEqual(result, {'game_vt': 2, 'restored_vt': 1,
                                  'keyboard_mode': 3, 'status': 'restored'})
        self.assertEqual(terminals.graphics, {1: 0, 2: 0})
        self.assertEqual(terminals.modes[2], bytes(8))
        self.assertLess(terminals.commands.index(console.VT_UNLOCKSWITCH),
                        terminals.commands.index(console.VT_ACTIVATE))
        self.assertNotIn(0x560B, terminals.commands)  # VT_LOCKSWITCH is the opposite.
        restore.assert_called_once_with(state.fd, console.termios.TCSANOW, ['saved'])
        self.assertEqual(set(terminals.closed), set(terminals.fds))

    def test_failed_restoration_still_closes_every_terminal(self):
        terminals = Terminals()
        self.patched(terminals)
        state = console.ConsoleState()
        terminals.active = 2
        terminals.fail_unlock = True
        with self.assertRaises(OSError):
            state.restore()
        self.assertEqual(set(terminals.closed), set(terminals.fds))

    def test_invalid_console_number_is_rejected_and_closed(self):
        terminals = Terminals()
        terminals.active = 0
        self.patched(terminals)
        with self.assertRaises(RuntimeError):
            console.ConsoleState()
        self.assertEqual(set(terminals.closed), set(terminals.fds))


if __name__ == '__main__':
    unittest.main()
