from pyftdi.ftdi import Ftdi
import numpy as np
from Utilities.ris_controller import MyRISController
import serial
import json
import time
import subprocess
import lgpio

# Rebind USB device if needed using a subprocess call for sudo permissions
subprocess.run(
    ["sudo", "python3", "-c", "from Utilities.rebind_usb import usb_reset; usb_reset()"]
)


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
    """
    Get the serial to USB converter address from dmesg logs.

    Returns:
        str: The device path of the serial converter or None if not found.
    """
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
    """Configure the DAC device.

    Args:
        device_url (str): The device URL.
        daisy_chain_device_num (int, optional): The daisy chain device number. Defaults to 0.
        voltage_range (str, optional): The voltage range. Defaults to "0-10V".

    Returns:
        MyRISController: The configured RIS controller.
    """
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

        return ris_controller
    except Exception as e:
        send_message(ser, f"DAC configuration failed: {e}", is_error=True)


# Configure GPIO for checking DAC15 output
DAC_CHECK_PIN = 4  # GPIO 4 (Physical pin 7)
chip = lgpio.gpiochip_open(0)
lgpio.gpio_claim_input(chip, DAC_CHECK_PIN, lgpio.SET_PULL_DOWN)


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


# Get FTDI device URL
device_url = f"ftdi:///1"
print("Using FTDI device:", device_url)


# Configure the RIS controller before entering the main loop
ris_controller = MyRISController(device_url)
# ris_controller = MyRISController(device_url, unit_cell_num=[9, 9], daisy_chain_device_num=1) # Example for 2 devices

# Attempt to configure the RIS controller - Exceptions will be caught and sent back to the serial port
try:
    ris_controller.configure("0-10V")
except Exception as e:
    send_message(ser, e)


# Main loop to read from serial and control the DAC
try:
    while True:
        # Read a line from the serial interface
        line = ser.readline().decode("utf-8").strip()
        if not line:
            continue

        # Check if the line contains configuration parameters
        if "Config" in line:
            config_params = json.loads(line)
            ris_controller = DAC_Config(
                device_url,
                config_params.get("daisy_chain_device_num"),
                config_params.get("voltage_range"),
            )
            send_message(ser, "Config received", is_error=False)
            continue

        # Parse the received line as a JSON array
        try:
            vector = json.loads(line)
            print("Received vector:", vector)
        except json.JSONDecodeError:
            print("Invalid data received. Skipping.")
            send_message(ser, "Invalid data received. Skipping", is_error=True)
            continue

        # Set the pattern on the RIS controller (DAC)
        try:
            ris_controller.set_pattern(np.array(vector).T)
            send_message(ser, "Pattern received", is_error=False)
        except Exception as e:
            send_message(ser, e)

        # Check GPIO input for 3V signal on DAC15
        value = lgpio.gpio_read(chip, DAC_CHECK_PIN)
        if value == 0:
            send_message(ser, "DAC15 output missing or low", is_error=True)
            print("Warning: DAC15 output check failed. Message sent.")
        # If output is good and vector was set, send success message
        else:
            send_message(ser, "Pattern set successfully", is_error=False)
            print("Pattern set successfully.")


# Final cleanup
finally:
    send_message(ser, "Powering down", is_error=False)
    lgpio.gpiochip_close(chip)
    ser.close()
