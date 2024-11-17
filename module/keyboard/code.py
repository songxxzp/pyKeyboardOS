import time
import board
import busio
import digitalio
import usb_hid
import random
import json
import _bleio

import neopixel

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

from lib.ch9329 import CH9329


scan_interval = 0.001
light_level = 255
max_light_level = 255
light_mode = "random_static"  # "on_press", "random_static"
light_keys_on_start = ["W", "A", "S", "D"]
on_start_keyboard_mode = "usb_hid"
physical_key_config_path = "config/physical_key_name_map.json"
mapping_config_path = "config/mapping.json"
fn_mapping_config_path = "config/fn_mapping.json"

CE_PIN = board.D10  # Chip Enable pin
PL_PIN = board.D9  # Parallel Load pin
SPI_CLOCK = board.D8  # SPI Clock pin
SPI_MISO = board.D5  # SPI Master In Slave Out pin

RGB_CONTROLL = board.D3
pixel_pin = board.D4  # RGB IN
MOS_PIN = board.D2
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
mos_io.value = False

uart = busio.UART(TX_PIN, RX_PIN, baudrate=38400)

light_2_key = [66, 65, 64, 63, 70, 69, 68, 50, 49, 48, 47, 54, 46, 39, 38, 31, 30, 23, 22, 18, 14, 7, 67, 55, 62, 8, 13, 17, 21, 24, 29, 32, 37, 40, 45, 53, 52, 44, 41, 36, 33, 28, 25, 20, 16, 12, 9, 61, 58, 56, 51, 43, 42, 35, 34, 27, 26, 19, 15, 11, 10, 60, 59, 57, 6, 5, 4, 3]


class PhysicalKey:
    def __init__(self, key_id: int, key_name: str, max_light_level: int = max_light_level) -> None:
        self.physical_id = key_id
        self.key_name = key_name
        self.pressed = False
        self.color = (max_light_level, max_light_level, max_light_level)
        self.random_color(max_light_level)
        # TODO: add used mark to avoid conflict
    
    def random_color(self, max_light_level):
        self.color = (
            random.randint(0, max_light_level),
            random.randint(0, max_light_level),
            random.randint(0, max_light_level)
        )


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
        return pressed

    def press(self):
        self.pressed = True
        if self.pressed_function:
            pressed_function_result = self.pressed_function()
            if pressed_function_result is None:  # TODO
                return None
            return pressed_function_result
        return None
        
    def release(self):
        self.pressed = False
        return None


class VirtualKeyBoard:
    def __init__(self, mode=on_start_keyboard_mode, usb_timeout=1):
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
        # self.ble_keyboard = None

        # print("init usb_hid_keyboard")
        try:
            self.usb_hid_keyboard = Keyboard(usb_hid.devices, timeout=usb_timeout)
        except:
            # print("failed to init usb_hid_keyboard")
            self.usb_hid_keyboard = None

        # print("init ch9329_keyboard")
        self.ch9329_keyboard = CH9329(uart)
    
        self.set_mode(self.mode)
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


def generate_standard_layer():
    standard_layer = {
        physical_key.physical_id: VirtualKey(physical_key.key_name, getattr(Keycode, physical_key.key_name), bind_physical_key=physical_key) for physical_key in physical_keys if physical_key.key_name in dir(Keycode)
    }
    return standard_layer


def generate_custom_layer():
    layer = generate_standard_layer()
    mapping = json.load(open(mapping_config_path))  # TODO: debug light
    for k, v in mapping.items():
        layer[physical_key_map[k].physical_id] = VirtualKey(v, getattr(Keycode, v), physical_key_map[k])
    return layer


def generate_fn_layer():
    layer = generate_standard_layer()
    mapping = json.load(open(fn_mapping_config_path))  # TODO: debug light
    for k, v in mapping.items():
        layer[physical_key_map[k].physical_id] = VirtualKey(v, getattr(Keycode, v), physical_key_map[k])
    return layer


def read_shift_registers(delay=1e-6):
    pl.value = False
    time.sleep(delay)
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


def light_keys(keys, refresh=True, colors=[], color=(16, 16, 16)):
    if refresh:
        for i in range(num_pixels):
            pixels[i] = (0, 0, 0)
    while len(colors) < len(keys):
        colors.append(color)
    for key_id, key_color in zip(keys, colors):
        scaled_key_color = (int(key_color[0] * light_level / max_light_level), int(key_color[1] * light_level / max_light_level), int(key_color[2] * light_level / max_light_level))
        pixels[light_2_key.index(key_id)] = scaled_key_color
    pixels.show()


def change_light_level(number, set_mode=False):
    global light_level
    if set_mode:
        light_level = number
    else:
        light_level += number
    light_level = min(max(light_level, 0), max_light_level)
    return None


def change_light_mode(target_mode=None):  # TODO: refactor
    global light_mode, light_level
    if target_mode is None:
        if light_mode == "on_press":
            light_mode = "random_static"
            light_level = min(32, light_level)
        elif light_mode == "random_static":
            light_mode = "on_press"
            light_level = max(max_light_level, light_level)
        else:
            light_mode = "on_press"
    elif target_mode == "on_press":
        light_mode = "on_press"
        light_level = max(max_light_level, light_level)
    elif target_mode == "random_static":
        light_mode = "random_static"
        light_level = min(32, light_level)
    else:
        light_mode = "on_press"
    return None


def main():
    global physical_key_ids, physical_key_map, fn_key, physical_keys

    running = True

    physical_key_name_map = json.load(open(physical_key_config_path))
    id_key_map = {}
    for k, v in physical_key_name_map.items():
        id_key_map[v] = k

    on_start_pressed_key_ids = []
    for light_key_on_start in light_keys_on_start:
        if light_key_on_start in physical_key_name_map:
            on_start_pressed_key_ids.append(physical_key_name_map[light_key_on_start])
    colors = [(255, 0, 0) for _ in on_start_pressed_key_ids]
    light_keys(on_start_pressed_key_ids, colors=colors, refresh=True)

    kbd = VirtualKeyBoard()

    physical_key_map = {key_name: PhysicalKey(key_id, key_name) for key_name, key_id in physical_key_name_map.items()}
    fn_key = physical_key_map["Fn"]
    physical_keys = list(physical_key_map.values())

    physical_key_ids= list(physical_key_name_map.values())
    physical_key_id_map = {key.physical_id: key for key in physical_keys}

    virtual_key_layers = [
        generate_custom_layer(),
        generate_fn_layer(),
    ]
    fn_key_layer_id = 1
    # set fn layer key function
    virtual_key_layers[fn_key_layer_id][physical_key_map["Q"].physical_id].pressed_function = partial(kbd.set_mode, "usb_hid")  # TODO: getkey function
    virtual_key_layers[fn_key_layer_id][physical_key_map["W"].physical_id].pressed_function = partial(kbd.set_mode, "ch9329")
    virtual_key_layers[fn_key_layer_id][physical_key_map["E"].physical_id].pressed_function = partial(kbd.set_mode, "bluetooth")
    virtual_key_layers[fn_key_layer_id][physical_key_map["R"].physical_id].pressed_function = partial(kbd.set_mode, "dummy")
    virtual_key_layers[fn_key_layer_id][physical_key_map["BACKSPACE"].physical_id].pressed_function = kbd.erase_bonding
    virtual_key_layers[fn_key_layer_id][physical_key_map["UP_ARROW"].physical_id].pressed_function = partial(change_light_level, 32)
    virtual_key_layers[fn_key_layer_id][physical_key_map["DOWN_ARROW"].physical_id].pressed_function = partial(change_light_level, -32)
    virtual_key_layers[fn_key_layer_id][physical_key_map["TAB"].physical_id].pressed_function = change_light_mode
    
    virtual_key_layer_id = 0
    light_keys([], colors=[], refresh=True)
    change_light_mode(light_mode)

    while running:
        register_bits = read_shift_registers()
        pressed_key_ids = get_pressed_key_ids(register_bits)
        for key in physical_keys:
            if key.physical_id in pressed_key_ids:
                if key.pressed == False:
                    # kbd.press(key.keycode)
                    # print(f"Pressed PhysicalKey: {key.key_name}")
                    key.random_color(max_light_level)
                    pass
                key.pressed = True
                # physical_key_id_map[key.physical_id] = key
            elif key.pressed == True:
                key.pressed = False
                # kbd.release(key.keycode)
                # print(f"Released PhysicalKey: {key.key_name}")

        virtual_key_layer_id = int(fn_key.pressed)  # TODO: light conifg as well

        for key in virtual_key_layers[virtual_key_layer_id].values():
            if key.is_pressed():
                if key.pressed == False:
                    key.press()
                    if key.pressed_function is None:  # TODO: refactor
                        kbd.press(key.keycode)
                # key.pressed = True
                key.update_time = time.time()  # TODO: add an update function
            else:
                if key.pressed == True:
                    key.release()
                    kbd.release(key.keycode)
                # key.pressed = False
                key.update_time = time.time()

        light_key_ids = physical_key_ids if light_mode == "random_static" else pressed_key_ids
        colors = [physical_key_id_map[pressed_key_id].color for pressed_key_id in light_key_ids]
        light_keys(light_key_ids, colors=colors, refresh=True)
        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
