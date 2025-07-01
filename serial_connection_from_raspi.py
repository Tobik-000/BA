import serial
import time
import subprocess


def get_serial_converter_address():
    try:
        result = subprocess.run(
            "dmesg | grep Moschip | grep attached",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        lines = [line for line in result.stdout.strip().split("\n") if line]
        if not lines:
            return None
        last_line = lines[-1]
        last_word = last_line.strip().split()[-1]
        return f"/dev/{last_word}"
    except Exception:
        return None


tty_path = get_serial_converter_address()
if not tty_path:
    raise RuntimeError("No Moschip device found.")

for attempt in range(10):
    try:
        ser = serial.Serial(tty_path, 9600)
        break
    except serial.SerialException:
        time.sleep(2)
else:
    raise RuntimeError("Could not open Moschip device after multiple attempts.")

try:
    while True:
        ser.write("from PI\n".encode("utf-8"))
        time.sleep(1)
finally:
    ser.close()
