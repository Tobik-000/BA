from pyftdi.ftdi import Ftdi
import numpy as np
from ris_controller import MyRISController
import serial
import json
import time
import subprocess
import lgpio
import os
import glob

# Rebind USB device if needed using a subprocess call for sudo permissions
subprocess.run(
    ["sudo", "python3", "-c", "from rebind_usb import usb_reset; usb_reset()"]
)
# subprocess.run("dmesg | grep ttyUSB", shell=True)


def is_zero_vector(vec):
    return all(v == 0 for v in vec)


def send_message(ser, msg, is_error=True):
    """
    Send a message as JSON over the serial interface.
    If is_error is True, sends as {"error": ...}, else as {"message": ...}
    """
    key = "error" if is_error else "message"
    try:
        ser.write(json.dumps({key: str(msg)}).encode("utf-8") + b"\n")
        ser.flush()
    except Exception as exc:
        print(f"Failed to send message over serial: {exc}")


def get_serial_converter_address():
    try:
        # search for the Serial to USB converter in dmesg logs (Moschip is the Manufacturer)
        result = subprocess.run(
            "dmesg | grep Moschip | grep attached",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Split output into lines and get the last non-empty one
        lines = [line for line in result.stdout.strip().split("\n") if line]
        if not lines:
            return None

        last_line = lines[-1]
        # Extract the last word (device name)
        last_word = last_line.strip().split()[-1]
        return f"/dev/{last_word}"

    except Exception as e:
        print("Error:", e)
        return None


def DAC_Config(device_url, daisy_chain_device_num=0, voltage_range="0-10V"):
    try:
        if daisy_chain_device_num == 0:
            ris_controller = MyRISController(device_url)
            ris_controller.configure(voltage_range)
        else:
            unit_cell_num = [9] * (daisy_chain_device_num + 1)
            ris_controller = MyRISController(
                device_url,
                unit_cell_num=unit_cell_num,
                daisy_chain_device_num=daisy_chain_device_num,
            )
            ris_controller.configure(voltage_range)
    except Exception as e:
        send_message(ser, f"DAC configuration failed: {e}", is_error=True)


# ------------------------
# GPIO setup for checking DAC15 output
# ------------------------
DAC_CHECK_PIN = 17  # GPIO pin number for checking DAC15 output
h = lgpio.gpiochip_open(0)  # Open GPIO chip
lgpio.gpio_claim_input(h, DAC_CHECK_PIN)  # Set pin as input


# Attempt to find the Moschip device
tty_path = get_serial_converter_address()
if tty_path:
    print("Moschip device path:", tty_path)
else:
    print("No Moschip device found.")


for attempt in range(10):
    try:
        ser = serial.Serial(tty_path, 9600)
        break
    except serial.SerialException:
        print("USB device not found, retrying...")
        time.sleep(2)
else:
    raise RuntimeError("Could not open Moschip device after multiple attempts.")

send_message(ser, "USB device opened successfully", is_error=False)


# ------------------------
# Step 2: Get FTDI device URL
# ------------------------
device_url = f"ftdi:///1"
print("Using FTDI device:", device_url)

# ------------------------
# Step 3: Initialize RIS controller
# ------------------------

ris_controller = MyRISController(
    device_url, unit_cell_num=[9, 9], daisy_chain_device_num=1
)
ris_controller = MyRISController(device_url)
# Attempt to configure the RIS controller - Exceptions will be caught and sent back to the serial port
try:
    ris_controller.configure("0-10V")
except Exception as e:
    send_message(ser, e)


# ------------------------
# Step 4: Main loop for receiving and processing vectors
# ------------------------
try:
    while True:
        line = ser.readline().decode("utf-8").strip()
        if not line:
            continue

        if "Config" in line:
            config_params = json.loads(line)
            DAC_Config(device_url, config_params.get("daisy_chain_device_num"), config_params.get("voltage_range"))

        try:
            vector = json.loads(line)
            print("Received vector:", vector)
        except json.JSONDecodeError:
            print("Invalid data received. Skipping.")
            continue

        try:
            ris_controller.set_pattern(np.array(vector).T)
            send_message(ser, "Pattern set successfully", is_error=False)
        except Exception as e:
            send_message(ser, e)

        # Check GPIO input for 3V signal on DAC15
        if lgpio.gpio_read(h, DAC_CHECK_PIN) == 0:
            send_message(ser, "DAC15 output missing or low", is_error=False)
            print("Warning: DAC15 output check failed. Message sent.")

        if is_zero_vector(vector):
            print("Zero vector received. Terminating program.")
            break


finally:
    # lgpio.gpio_free(h)
    lgpio.gpiochip_close(h)
    ser.close()
    print("Serial and GPIO connection closed.")
