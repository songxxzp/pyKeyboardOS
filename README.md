# pyKeyboardOS

A Real-Time OS built for Keyboard using CircuitPython.

### Changes

#### 2024.10.08
- [Middle Term Report](https://docs.qq.com/slide/DUnJsUXBYbUl4WGhJ)
- Final Goal: Basic Keyboard + Sleep Mode + At Least One Modular Module (Camera, Screen, Numpad, etc.).

##### Basic Keyboard
- Connection via USB or BLE.
- Basic RGB lighting
- Basic key mapping

##### Sleep Mode
- Auto-sleep (low power mode)
- Low-latency waking

##### Modular Modules
- Camera
- Screen
- Numpad
- Knobs
- Motor

#### 2024.10.05
- Add independent camera code

#### 2024.09.27

- Set the CH9329 as the default connection.
- When using the CH9329 connection, if more than six keys are pressed simultaneously, the additional (beyond six) keys will be released in the order they were pressed.

### Acknowledgments

- circuitpython-ch9329: https://github.com/74th/circuitpython-ch9329

### Tracking

- wpa2 enterprise support: https://github.com/zephyrproject-rtos/zephyr/pull/78921
