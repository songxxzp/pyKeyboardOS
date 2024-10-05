import time
import board
import busio
import digitalio
import usb_hid
import _bleio

import neopixel

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

from lib.ch9329 import CH9329


PL_PIN = board.D8  # Parallel Load pin
CE_PIN = board.D10  # Chip Enable pin
SPI_CLOCK = board.D9  # SPI Clock pin
SPI_MISO = board.D5  # SPI Master In Slave Out pin
RGB_CONTROLL = board.D2
pixel_pin = board.D4  # RGB IN
MOS_PIN = board.D3
TX_PIN = board.D6
RX_PIN = board.D7

num_pixels = 68
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=1, auto_write=False, pixel_order=ORDER)

rgb_io = digitalio.DigitalInOut(RGB_CONTROLL)
rgb_io.direction = digitalio.Direction.OUTPUT
rgb_io.value = True

# Set up the SPI interface
spi = busio.SPI(SPI_CLOCK, MOSI=None, MISO=SPI_MISO)

# Set up the control pins
pl = digitalio.DigitalInOut(PL_PIN)
pl.direction = digitalio.Direction.OUTPUT

ce = digitalio.DigitalInOut(CE_PIN)
ce.direction = digitalio.Direction.OUTPUT
ce.value = False  # Enable the chip (active low)

mos_io = digitalio.DigitalInOut(MOS_PIN)
mos_io.direction = digitalio.Direction.OUTPUT
mos_io.value = True

uart = busio.UART(TX_PIN, RX_PIN, baudrate=9600)


light_2_key = [66, 65, 64, 63, 70, 69, 68, 50, 49, 48, 47, 54, 46, 39, 38, 31, 30, 23, 22, 18, 14, 7, 67, 55, 62, 8, 13, 17, 21, 24, 29, 32, 37, 40, 45, 53, 52, 44, 41, 36, 33, 28, 25, 20, 16, 12, 9, 61, 58, 56, 51, 43, 42, 35, 34, 27, 26, 19, 15, 11, 10, 60, 59, 57, 6, 5, 4, 3]

physical_key_name_map = {
    "A": 45,
    "B": 30,
    "C": 38,
    "D": 37,
    "E": 36,
    "F": 32,
    "G": 29,
    "H": 24,
    "I": 16,
    "J": 21,
    "K": 17,
    "L": 13,
    "M": 22,
    "N": 23,
    "O": 12,
    "P": 9,
    "Q": 44,
    "R": 33,
    "S": 40,
    "T": 28,
    "U": 20,
    "V": 31,
    "W": 41,
    "X": 39,
    "Y": 25,
    "Z": 46,
    "UP_ARROW": 66,
    "RIGHT_ARROW": 65,
    "DOWN_ARROW": 64,
    "LEFT_ARROW": 63,
    "RIGHT_CONTROL": 70,
    "Fn": 69,
    "RIGHT_ALT": 68,
    "SPACEBAR": 50,
    "LEFT_ALT": 49,
    "LEFT_GUI": 48,
    "LEFT_CONTROL": 47,
    "LEFT_SHIFT": 54,
    "COMMA": 18,
    "PERIOD": 14,
    "FORWARD_SLASH": 7,
    "RIGHT_SHIFT": 67,
    "ENTER": 55,
    "QUOTE": 62,
    "SEMICOLON": 8,
    "CAPS_LOCK": 53,
    "TAB": 52,
    "LEFT_BRACKET": 61,
    "RIGHT_BRACKET": 58,
    "BACKSLASH": 56,
    "ESCAPE": 51,  # "~": 51,
    "ONE": 43,
    "TWO": 42,
    "THREE": 35,
    "FOUR": 34,
    "FIVE": 27,
    "SIX": 26,
    "SEVEN": 19,
    "EIGHT": 15,
    "NINE": 11,
    "ZERO": 10,
    "MINUS": 60,
    "EQUALS": 59,
    "BACKSPACE": 57,
    "INSERT": 6,  # "Esc": 6,
    "PAGE_UP": 5,  # "Home": 5,
    "PAGE_DOWN": 4,  # "End": 4,
    "DELETE": 3,
}

physical_key_ids = list(physical_key_name_map.values())


class PhysicalKey:
    def __init__(self, key_id: int, key_name: str) -> None:
        self.physical_id = key_id
        self.key_name = key_name
        self.pressed = False
        # TODO: add used mark to avoid conflict


class VirtualKey:
    def __init__(self, key_name: str, keycode: int, bind_physical_key: PhysicalKey, pressed_function=None) -> None:
        self.keycode = keycode
        self.key_name = key_name
        self.pressed_function = pressed_function  # TODO: rename
        # TODO: press condition function
        self.bind_physical_key = bind_physical_key
        self.pressed = False
        self.update_time = time.time()

    # TODO: @property
    def is_pressed(self):
        pressed = self.bind_physical_key.pressed
        if pressed and self.pressed_function:
            pressed_function_result = self.pressed_function()
            if pressed_function_result is None:  # TODO
                return False
        return pressed


class VirtualKeyBoard:
    def __init__(self, mode="ch9329", usb_timeout=1):
        self.mode = mode
        
        # print("init ble_keyboard")
        self.adapter = _bleio.adapter
        if not self.adapter.enabled:
            self.adapter.enabled = True

        # 获取并打印蓝牙MAC地址
        self.mac_address = self.adapter.address
        print("Bluetooth MAC Address:", self.mac_address)
        self.ble = BLERadio()
        self.ble_hid = HIDService()
        self.advertisement = ProvideServicesAdvertisement(self.ble_hid)
        self.advertisement.appearance = 961
        self.advertisement.short_name = "s68k"
        self.advertisement.complete_name = "s68k esp32s3 keyboard"
        self.ble_keyboard = Keyboard(self.ble_hid.devices)

        # print("init usb_hid_keyboard")
        try:
            self.usb_hid_keyboard = Keyboard(usb_hid.devices, timeout=usb_timeout)
        except:
            # print("failed to init usb_hid_keyboard")
            self.usb_hid_keyboard = None

        # print("init ch9329_keyboard")
        self.ch9329_keyboard = CH9329(uart)
    
        self.set_mode("ch9329")
        self.reset()

    def erase_bonding(self):
        self.adapter.erase_bonding()

    def set_mode(self, mode, usb_timeout=1):
        # print(f"set mode to: {mode}")
        if mode == "bluetooth" and self.mode != "bluetooth":
            if not self.ble.advertising:
                self.ble.start_advertising(self.advertisement)
        elif self.mode == "bluetooth" and mode != "bluetooth":
            if self.ble.advertising:
                self.ble.stop_advertising()

        self.mode = mode

        if mode == "usb_hid" and self.usb_hid_keyboard is None:
            try:
                self.usb_hid_keyboard = Keyboard(usb_hid.devices, timeout=usb_timeout)
            except:
                # print("failed to init usb_hid_keyboard")
                self.usb_hid_keyboard = None
                self.mode = "dummy"
    
    def reset(self):
        if self.usb_hid_keyboard is not None:
            self.usb_hid_keyboard.release_all()
        if self.ch9329_keyboard is not None:
            self.ch9329_keyboard.keyboard_release_all()
        if self.ble_keyboard is not None:
            self.ble_keyboard.release_all()

    def press(self, *keycodes: int) -> None:
        if self.mode == "usb_hid":
            if self.usb_hid_keyboard is not None:
                try:
                    self.usb_hid_keyboard.press(*keycodes)
                except:
                    self.set_mode("dummy")
            else:
                raise ValueError(f"self.usb_hid_keyboard is None")
        elif self.mode == "ch9329":
            if self.ch9329_keyboard is not None:
                # TODO: add warning or sort by time
                self.ch9329_keyboard.keyboard_press(*keycodes[:6])
            else:
                print(f"self.ch9329_keyboard is None")
        elif self.mode == "bluetooth":
            if self.ble_keyboard is not None:
                self.ble_keyboard.press(*keycodes)
            else:
                raise ValueError(f"self.ble_keyboard is None")
        elif self.mode == "dummy":
            pass
        else:
            raise NotImplementedError(f"self.mode: {self.mode}")

    def release(self, *keycodes: int) -> None:
        if self.mode == "usb_hid":
            if self.usb_hid_keyboard is not None:
                try:
                    self.usb_hid_keyboard.release(*keycodes)
                except:
                    self.set_mode("dummy")
            else:
                print(f"self.usb_hid_keyboard is None")
        elif self.mode == "ch9329":
            if self.ch9329_keyboard is not None:
                self.ch9329_keyboard.keyboard_release(*keycodes)
            else:
                raise ValueError(f"self.ch9329_keyboard is None")
        elif self.mode == "bluetooth":
            if self.ble_keyboard is not None:
                self.ble_keyboard.release(*keycodes)
            else:
                raise ValueError(f"self.ble_keyboard is None")
        elif self.mode == "dummy":
            pass
        else:
            raise NotImplementedError(f"self.mode: {self.mode}")


def partial(func, *args):
    def wrapper(*more_args):
        return func(*args, *more_args)
    return wrapper


physical_key_map = {
    key_name: PhysicalKey(key_id, key_name) for key_name, key_id in physical_key_name_map.items()
}

fn_key = physical_key_map["Fn"]
physical_keys = list(physical_key_map.values())


def generate_standard_layer():
    standard_layer = {
        physical_key.physical_id: VirtualKey(physical_key.key_name, getattr(Keycode, physical_key.key_name), bind_physical_key=physical_key) for physical_key in physical_keys if physical_key.key_name in dir(Keycode)
    }
    standard_keys = [
        VirtualKey("TWO", Keycode.TWO, physical_key_map["TWO"]),
        VirtualKey("EIGHT", Keycode.EIGHT, physical_key_map["EIGHT"]),
        VirtualKey("PAGE_DOWN", Keycode.PAGE_DOWN, physical_key_map["PAGE_DOWN"]),
        VirtualKey("PAGE_UP", Keycode.PAGE_UP, physical_key_map["PAGE_UP"]),
        VirtualKey("ENTER", Keycode.ENTER, physical_key_map["ENTER"]),
        VirtualKey("E", Keycode.E, physical_key_map["E"]),
        VirtualKey("D", Keycode.D, physical_key_map["D"]),
        VirtualKey("SPACEBAR", Keycode.SPACEBAR, physical_key_map["SPACEBAR"]),
        VirtualKey("RIGHT_ALT", Keycode.RIGHT_ALT, physical_key_map["RIGHT_ALT"]),
        VirtualKey("EQUALS", Keycode.EQUALS, physical_key_map["EQUALS"]),
        VirtualKey("LEFT_GUI", Keycode.LEFT_GUI, physical_key_map["LEFT_GUI"]),
        VirtualKey("BACKSLASH", Keycode.BACKSLASH, physical_key_map["BACKSLASH"]),
        VirtualKey("G", Keycode.G, physical_key_map["G"]),
        VirtualKey("COMMA", Keycode.COMMA, physical_key_map["COMMA"]),
        VirtualKey("F", Keycode.F, physical_key_map["F"]),
        VirtualKey("O", Keycode.O, physical_key_map["O"]),
        VirtualKey("CAPS_LOCK", Keycode.CAPS_LOCK, physical_key_map["CAPS_LOCK"]),
        VirtualKey("I", Keycode.I, physical_key_map["I"]),
        VirtualKey("H", Keycode.H, physical_key_map["H"]),
        VirtualKey("K", Keycode.K, physical_key_map["K"]),
        VirtualKey("J", Keycode.J, physical_key_map["J"]),
        VirtualKey("U", Keycode.U, physical_key_map["U"]),
        VirtualKey("T", Keycode.T, physical_key_map["T"]),
        VirtualKey("W", Keycode.W, physical_key_map["W"]),
        VirtualKey("V", Keycode.V, physical_key_map["V"]),
        VirtualKey("Q", Keycode.Q, physical_key_map["Q"]),
        VirtualKey("P", Keycode.P, physical_key_map["P"]),
        VirtualKey("S", Keycode.S, physical_key_map["S"]),
        VirtualKey("R", Keycode.R, physical_key_map["R"]),
        VirtualKey("DOWN_ARROW", Keycode.DOWN_ARROW, physical_key_map["DOWN_ARROW"]),
        VirtualKey("TAB", Keycode.TAB, physical_key_map["TAB"]),
        VirtualKey("LEFT_ARROW", Keycode.LEFT_ARROW, physical_key_map["LEFT_ARROW"]),
        VirtualKey("DELETE", Keycode.DELETE, physical_key_map["DELETE"]),
        VirtualKey("Y", Keycode.Y, physical_key_map["Y"]),
        VirtualKey("X", Keycode.X, physical_key_map["X"]),
        VirtualKey("RIGHT_CONTROL", Keycode.RIGHT_CONTROL, physical_key_map["RIGHT_CONTROL"]),
        VirtualKey("Z", Keycode.Z, physical_key_map["Z"]),
        VirtualKey("LEFT_ALT", Keycode.LEFT_ALT, physical_key_map["LEFT_ALT"]),
        VirtualKey("LEFT_SHIFT", Keycode.LEFT_SHIFT, physical_key_map["LEFT_SHIFT"]),
        VirtualKey("PERIOD", Keycode.PERIOD, physical_key_map["PERIOD"]),
        VirtualKey("LEFT_CONTROL", Keycode.LEFT_CONTROL, physical_key_map["LEFT_CONTROL"]),
        VirtualKey("MINUS", Keycode.MINUS, physical_key_map["MINUS"]),
        VirtualKey("RIGHT_SHIFT", Keycode.RIGHT_SHIFT, physical_key_map["RIGHT_SHIFT"]),
        VirtualKey("FORWARD_SLASH", Keycode.FORWARD_SLASH, physical_key_map["FORWARD_SLASH"]),
        VirtualKey("UP_ARROW", Keycode.UP_ARROW, physical_key_map["UP_ARROW"]),
        VirtualKey("A", Keycode.A, physical_key_map["A"]),
        VirtualKey("C", Keycode.C, physical_key_map["C"]),
        VirtualKey("B", Keycode.B, physical_key_map["B"]),
        VirtualKey("M", Keycode.M, physical_key_map["M"]),
        VirtualKey("SEVEN", Keycode.SEVEN, physical_key_map["SEVEN"]),
        VirtualKey("L", Keycode.L, physical_key_map["L"]),
        VirtualKey("N", Keycode.N, physical_key_map["N"]),
        VirtualKey("ZERO", Keycode.ZERO, physical_key_map["ZERO"]),
        VirtualKey("QUOTE", Keycode.QUOTE, physical_key_map["QUOTE"]),
        VirtualKey("NINE", Keycode.NINE, physical_key_map["NINE"]),
        VirtualKey("SEMICOLON", Keycode.SEMICOLON, physical_key_map["SEMICOLON"]),
        VirtualKey("LEFT_BRACKET", Keycode.LEFT_BRACKET, physical_key_map["LEFT_BRACKET"]),
        VirtualKey("RIGHT_BRACKET", Keycode.RIGHT_BRACKET, physical_key_map["RIGHT_BRACKET"]),
        VirtualKey("RIGHT_ARROW", Keycode.RIGHT_ARROW, physical_key_map["RIGHT_ARROW"]),
        VirtualKey("ESCAPE", Keycode.ESCAPE, physical_key_map["ESCAPE"]),
        VirtualKey("ONE", Keycode.ONE, physical_key_map["ONE"]),
        VirtualKey("SIX", Keycode.SIX, physical_key_map["SIX"]),
        VirtualKey("FOUR", Keycode.FOUR, physical_key_map["FOUR"]),
        VirtualKey("INSERT", Keycode.INSERT, physical_key_map["INSERT"]),
        VirtualKey("BACKSPACE", Keycode.BACKSPACE, physical_key_map["BACKSPACE"]),
        VirtualKey("THREE", Keycode.THREE, physical_key_map["THREE"]),
        VirtualKey("FIVE", Keycode.FIVE, physical_key_map["FIVE"]),
    ]
    return standard_layer


def generate_custom_layer():
    layer = generate_standard_layer()
    mapping = {
        "PAGE_UP": "HOME",
        "PAGE_DOWN": "END",
        "ESCAPE": "GRAVE_ACCENT",
        "INSERT": "ESCAPE",
    }
    # layer[physical_key_map["ESCAPE"].physical_id] = VirtualKey("GRAVE_ACCENT", Keycode.GRAVE_ACCENT, physical_key_map["ESCAPE"])
    # layer[physical_key_map["INSERT"].physical_id] = VirtualKey("ESCAPE", Keycode.ESCAPE, physical_key_map["INSERT"])
    for k, v in mapping.items():
        layer[physical_key_map[k].physical_id] = VirtualKey(v, getattr(Keycode, v), physical_key_map[k])
    return layer


def generate_fn_layer():
    layer = generate_standard_layer()
    mapping = {
        "ONE": "F1",
        "TWO": "F2",
        "THREE": "F3",
        "FOUR": "F4",
        "FIVE": "F5",
        "SIX": "F6",
        "SEVEN": "F7",
        "EIGHT": "F8",
        "NINE": "F9",
        "ZERO": "F10",
        "MINUS": "F11",
        "EQUALS": "F12",
        "INSERT": "PRINT_SCREEN",
        "RIGHT_CONTROL": "APPLICATION",
        "PAGE_UP": "PAGE_UP",
        "PAGE_DOWN": "PAGE_DOWN",
        "ESCAPE": "ESCAPE",
    }
    for k, v in mapping.items():
        layer[physical_key_map[k].physical_id] = VirtualKey(v, getattr(Keycode, v), physical_key_map[k])
    # layer[physical_key_map["ONE"].physical_id] = VirtualKey("F1", Keycode.F1, physical_key_map["ONE"])
    # layer[physical_key_map["TWO"].physical_id] = VirtualKey("F2", Keycode.F2, physical_key_map["TWO"])
    return layer


virtual_key_layers = [
    generate_custom_layer(),
    generate_fn_layer(),
]


def read_shift_registers():
    pl.value = False
    time.sleep(1e-6)  # Small delay to ensure the data is loaded
    pl.value = True

    while not spi.try_lock():
        pass

    try:
        result = bytearray(9)
        spi.readinto(result)
    finally:
        spi.unlock()

    bits = []
    for byte in result:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits


def get_pressed_key_ids(register_bits):
    pressed_key_ids = [physical_key_id for physical_key_id in physical_key_ids if not register_bits[physical_key_id]]
    return pressed_key_ids


def light_keys(keys, refresh=True, color=(16, 16, 16)):
    if refresh:
        for i in range(num_pixels):
            pixels[i] = (0, 0, 0)
    for key_id in keys:
        pixels[light_2_key.index(key_id)] = color
    pixels.show()


if __name__ == "__main__":
    running = True
    id_key_map = {}
    for k, v in physical_key_name_map.items():
        id_key_map[v] = k

    kbd = VirtualKeyBoard()

    fn_key_layer_id = 1
    virtual_key_layers[fn_key_layer_id][physical_key_map["Q"].physical_id].pressed_function = partial(kbd.set_mode, "usb_hid")  # TODO: getkey function
    virtual_key_layers[fn_key_layer_id][physical_key_map["W"].physical_id].pressed_function = partial(kbd.set_mode, "ch9329")
    virtual_key_layers[fn_key_layer_id][physical_key_map["E"].physical_id].pressed_function = partial(kbd.set_mode, "bluetooth")
    virtual_key_layers[fn_key_layer_id][physical_key_map["R"].physical_id].pressed_function = partial(kbd.set_mode, "dummy")
    virtual_key_layers[fn_key_layer_id][physical_key_map["BACKSPACE"].physical_id].pressed_function = kbd.erase_bonding

    virtual_key_layer_id = 0

    while running:
        register_bits = read_shift_registers()
        pressed_key_ids = get_pressed_key_ids(register_bits)
        for key in physical_keys:
            if key.physical_id in pressed_key_ids:
                if key.pressed == False:
                    # kbd.press(key.keycode)
                    # print(f"Pressed PhysicalKey: {key.key_name}")
                    pass
                key.pressed = True
            elif key.pressed == True:
                key.pressed = False
                # kbd.release(key.keycode)
                # print(f"Released PhysicalKey: {key.key_name}")

        virtual_key_layer_id = int(fn_key.pressed)  # TODO: light conifg as well

        for key in virtual_key_layers[virtual_key_layer_id].values():
            if key.is_pressed():
                if key.pressed == False:
                    kbd.press(key.keycode)
                key.pressed = True
                key.update_time = time.time()  # TODO: add an update function
            else:
                if key.pressed == True:
                    kbd.release(key.keycode)
                key.pressed = False
                key.update_time = time.time()

        light_keys(pressed_key_ids, refresh=True)
        time.sleep(0.005)

