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
# time.sleep(5)  # Wait for the USB device to reset

# ------------------------
# Check if ttyUSB0 is available
# ------------------------

# # ------------------------
# # List available USB serial ports
# # ------------------------
# usb_ports = glob.glob("/dev/ttyUSB*")
# print("Available USB serial ports after reset:", usb_ports)
#
# subprocess.run("dmesg | grep ttyUSB", shell=True)


def is_zero_vector(vec):
    return all(v == 0 for v in vec)


# ------------------------
# GPIO setup for checking DAC15 output
# ------------------------
DAC_CHECK_PIN = 17  # GPIO pin number for checking DAC15 output
h = lgpio.gpiochip_open(0)  # Open GPIO chip
# lgpio.gpio_free(h, DAC_CHECK_PIN)  # Free the pin if it was previously used
lgpio.gpio_claim_input(h, DAC_CHECK_PIN)  # Set pin as input


# ------------------------
# Step 1: Initialize serial connection with retries
# ------------------------


def get_last_moschip_tty():
    try:
        # Run the shell pipeline
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


# Attempt to find the Moschip device
tty_path = get_last_moschip_tty()
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

# ------------------------
# Step 2: Get FTDI device URL
# ------------------------

device_url = f"ftdi:///1"
print("Using FTDI device:", device_url)

# ------------------------
# Step 3: Initialize RIS controller
# ------------------------

# ris_controller = MyRISController(device_url, unit_cell_num=[9,9],daisy_chain_device_num=1)
ris_controller = MyRISController(device_url)
# Attempt to configure the RIS controller - Exeptions will be caught and sent back to the serial port
try:
    ris_controller.configure("0-10V")
except Exception as e:
    ser.write(json.dumps({"error": str(e)}).encode("utf-8") + b"\n")


# ------------------------
# Step 4: Main loop for receiving and processing vectors
# ------------------------
try:
    while True:
        line = ser.readline().decode("utf-8").strip()
        if not line:
            continue

        try:
            vector = json.loads(line)
            print("Received vector:", vector)
        except json.JSONDecodeError:
            print("Invalid data received. Skipping.")
            continue

        try:
            ris_controller.set_pattern(np.array(vector).T)
        except Exception as e:
            ser.write(json.dumps({"error": str(e)}).encode("utf-8") + b"\n")

        # Check GPIO input for 3V signal on DAC15
        if lgpio.gpio_read(h, DAC_CHECK_PIN) == 0:
            warning_msg = json.dumps({"warning": "DAC15 output missing or low"}) + "\n"
            ser.write(warning_msg.encode("utf-8"))
            print("Warning: DAC15 output check failed. Message sent.")

        if is_zero_vector(vector):
            print("Zero vector received. Terminating program.")
            break


finally:
    # lgpio.gpio_free(h)
    lgpio.gpiochip_close(h)
    ser.close()
    print("Serial and GPIO connection closed.")
