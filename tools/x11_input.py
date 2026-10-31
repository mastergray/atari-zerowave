# SPDX-FileCopyrightText: 2026 mastergray
# SPDX-License-Identifier: GPL-3.0-only

"""Small XTest helper for our own isolated Stella validation window."""
import ctypes
import time


class Keyboard:
    def __init__(self):
        self.x11 = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XKeysymToKeycode.restype = ctypes.c_uint
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Cannot open X display")

    def key(self, name, pressed):
        symbol = self.x11.XStringToKeysym(name.encode())
        code = self.x11.XKeysymToKeycode(self.display, symbol)
        if not code:
            raise ValueError(name)
        self.xtst.XTestFakeKeyEvent(self.display, code, int(pressed), 0)
        self.x11.XFlush(self.display)

    def tap(self, name):
        self.key(name, True)
        self.key(name, False)

    def command(self, text):
        shifted = {"_": "minus", "#": "3", "$": "4", "*": "8", ">": "period", "<": "comma", ":": "semicolon"}
        names = {" ": "space", "-": "minus", "/": "slash", ".": "period", "=": "equal", "+": "plus"}
        for char in text:
            shift = char.isupper() or char in shifted
            if shift:
                self.key("Shift_L", True)
            self.tap(shifted.get(char, names.get(char, char.lower())))
            if shift:
                self.key("Shift_L", False)
        self.tap("Return")
        time.sleep(0.15)
