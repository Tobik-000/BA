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
#subprocess.run("dmesg | grep ttyUSB", shell=True)
time.sleep(5)  # Wait for the USB device to reset

# ------------------------
# Check if ttyUSB0 is available
# ------------------------

for i in range(10):
    if os.path.exists("/dev/ttyUSB0"):
        break
    print("Waiting for /dev/ttyUSB0 to appear...")
    time.sleep(1)
else:
    raise RuntimeError("/dev/ttyUSB0 did not appear after reset")


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
for attempt in range(10):
    try:
        ser = serial.Serial("/dev/ttyUSB0", 9600)
        break
    except serial.SerialException:
        print("USB device not found, retrying...")
        time.sleep(2)
else:
    raise RuntimeError("Could not open /dev/ttyUSB0 after multiple attempts.")

# ------------------------
# Step 2: Get FTDI device URL
# ------------------------

device_url = f"ftdi:///1"
print("Using FTDI device:", device_url)

# ------------------------
# Step 3: Initialize RIS controller
# ------------------------
ris_controller = MyRISController(device_url)
# Attempt to configure the RIS controller - Exeptions will be caught and sent back to the serial port
try:
    ris_controller.configure("0-10V")
except Exception as e:
    ser.write(
        json.dumps({"error": str(e)}).encode("utf-8") + b"\n"
    )

# ------------------------
# List available USB serial ports
# ------------------------
usb_ports = glob.glob("/dev/ttyUSB*")
print("Available USB serial ports after reset:", usb_ports)

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
            ser.write(
                json.dumps({"error": str(e)}).encode("utf-8") + b"\n"
            )

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
