# circuitpython-ch9329: https://github.com/74th/circuitpython-ch9329
#
# circuitpython-ch9329: MIT

import time

from busio import UART

from adafruit_hid.keycode import Keycode as Keycode

HEADER = bytearray([0x57, 0xAB])
CMD_KEY = 0x02
CMD_MEDIA_KEY = 0x03
CMD_MOUSE_ABSOLUTE = 0x04
CMD_MOUSE_RELATIVE = 0x05

MODIFIER_KEY_CODE = set(
    [
        Keycode.LEFT_CONTROL,
        Keycode.LEFT_SHIFT,
        Keycode.LEFT_ALT,
        Keycode.LEFT_GUI,
        Keycode.RIGHT_CONTROL,
        Keycode.RIGHT_SHIFT,
        Keycode.RIGHT_ALT,
        Keycode.RIGHT_GUI,
    ]
)


class InvalidKeyCodeError(Exception):
    pass


class MOUSE_BUTTON_KEYCODE:
    LEFT_BUTTON = 1
    RIGHT_BUTTON = 2
    MIDDLE_BUTTON = 4


class CH9329:  # TODO: Maintaining Key Order
    KEYBOARD_KEYCODE = Keycode
    MOUSE_KEYCODE = MOUSE_BUTTON_KEYCODE

    def __init__(self, uart: UART, address: int = 0x00):
        self._uart = uart
        self._address = address
        self._pressed_keys: set[int] = set()
        self._pressed_modifier_keys: set[int] = set()
        self._pressed_mouse_key_bit: int = 0

        self.debug = False

    def _parse_modifier_keys(self, keys: set[int]) -> int:
        b: int = 0
        for i, modifier_key in enumerate(MODIFIER_KEY_CODE):
            if modifier_key in keys:
                b |= 1 << i
        return b

    def keyboard_press(self, *key_codes: int):
        arg_keys = set(key_codes)

        pressed_keys = self._pressed_keys | (arg_keys - MODIFIER_KEY_CODE)
        # if len(pressed_keys) > 6:
        #     raise InvalidKeyCodeError(
        #         "The number of pressed keys must be less than or equal to 6."
        #     )
        self._pressed_keys = set(list(pressed_keys)[:6])

        pressed_modifier_keys = self._pressed_modifier_keys | (
            arg_keys & MODIFIER_KEY_CODE
        )
        # if len(pressed_keys) > 4:
        #     raise InvalidKeyCodeError(
        #         "The number of modifier keys must be less than or equal to 4."
        #     )
        self._pressed_modifier_keys = set(list(pressed_modifier_keys)[:4])

        self._send_key()

    def keyboard_release(self, *key_codes: int):
        arg_keys = set(key_codes)

        self._pressed_keys = self._pressed_keys - arg_keys
        self._pressed_modifier_keys = self._pressed_modifier_keys - arg_keys

        self._send_key()

    def keyboard_release_all(self):
        self._pressed_keys = set()
        self._pressed_modifier_keys = set()

        self._send_key()

    def keyboard_tap(self, *key_codes: int):
        self.keyboard_press(*key_codes)
        time.sleep(0.01)
        self.keyboard_release_all()

    def _send_key(self):
        b = bytearray(5 + 8 + 1)
        b[0:2] = HEADER
        b[2] = self._address
        b[3] = CMD_KEY
        b[4] = 8
        b[5] = self._parse_modifier_keys(self._pressed_modifier_keys)
        b[6] = 0
        n = 0
        for code in self._pressed_keys:
            b[7 + n] = code
            n += 1

        self._add_checksum(b)

        if self.debug:
            print("ch9329 send:", " ".join(map(hex, b)))
        self._uart.write(b)

    def mouse_move(self, x: int, y: int, wheel: int):
        if x < -128 or 127 < x:
            raise ValueError("x must be between -128 and 127.")

        if y < -128 or 127 < y:
            raise ValueError("y must be between -128 and 127.")

        if wheel < -128 or 127 < wheel:
            raise ValueError("wheel must be between -128 and 127.")

        self._send_mouse(x, y, wheel)

    def mouse_press(self, *key_codes: int):
        self._pressed_mouse_key_bit |= sum(key_codes)
        self._send_mouse(0, 0, 0)

    def mouse_release(self, *key_codes: int):
        self._pressed_mouse_key_bit &= ~sum(key_codes) & 0xFF
        self._send_mouse(0, 0, 0)

    def mouse_release_all(self):
        self._pressed_mouse_key_bit = 0x00
        self._send_mouse(0, 0, 0)

    def mouse_tap(self, *key_codes: int):
        self.mouse_press(*key_codes)
        time.sleep(0.01)
        self.mouse_release_all()

    def _send_mouse(self, x: int, y: int, wheel: int):
        b = bytearray(5 + 5 + 1)
        b[0:2] = HEADER
        b[2] = self._address
        b[3] = CMD_MOUSE_RELATIVE
        b[4] = 5
        b[5] = 0x01
        b[6] = self._pressed_mouse_key_bit
        b[7] = x & 0xFF
        b[8] = y & 0xFF
        b[9] = wheel & 0xFF

        self._add_checksum(b)

        if self.debug:
            print("ch9329 send:", " ".join(map(hex, b)))
        self._uart.write(b)

    @classmethod
    def _add_checksum(cls, b: bytearray):
        b[-1] = sum(b[:-1]) & 0xFF
