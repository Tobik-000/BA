import subprocess
import os
import time

def get_bus_id(device_keyword):
    # Step 1: run `lsusb` to list all connected USB devices
    result = subprocess.run(['lsusb'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')

    for line in lines:
        if device_keyword.lower() in line.lower():
            parts = line.split()
            bus = parts[1]
            device = parts[3].strip(':')

            # Path to the device in sysfs
            usb_path = f"/dev/bus/usb/{bus}/{device}"
            
            # Get the corresponding sysfs path (e.g., 1-1.2)
            # We look inside /sys/bus/usb/devices/ for the correct devnum
            for dev in os.listdir("/sys/bus/usb/devices/"):
                devpath = os.path.join("/sys/bus/usb/devices", dev)
                try:
                    with open(os.path.join(devpath, "busnum")) as f:
                        busnum = int(f.read().strip())
                    with open(os.path.join(devpath, "devnum")) as f:
                        devnum = int(f.read().strip())

                    if int(bus) == busnum and int(device) == devnum:
                        return dev  # This is the bus_id for binding/unbinding
                except FileNotFoundError:
                    continue
    return None

def usb_reset():
    device_keyword = "UART"
    bus_id = get_bus_id(device_keyword)
    if not bus_id:
        print(f"Device '{device_keyword}' not found.")
        return

    print(f"Resetting device with bus ID: {bus_id}")
    try:
        with open("/sys/bus/usb/drivers/usb/unbind", 'w') as f:
            f.write(bus_id)
        time.sleep(1)
        with open("/sys/bus/usb/drivers/usb/bind", 'w') as f:
            f.write(bus_id)
        print("USB device reinitialized successfully.")
    except Exception as e:
        print(f"Failed to reinitialize USB device: {e}")



if __name__ == "__main__":
    usb_reset()
