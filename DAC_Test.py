from pyftdi.ftdi import Ftdi as F
import numpy as np
from ris_controller import MyRISController

print("Testrun")

# List all FTDI devices
F.show_devices()

# device_url = "ftdi:///1"
# 
# ris_controller = MyRISController(device_url)
# 
# ris_controller.configure("0-10V")
# 
# # ris_controller.set_pattern(np.array([1, 2, 3, 4, 5, 6, 7, 8, 9]).T)
# 
# ris_controller.set_pattern(np.array([6,6,6,7,7,7,8,8,8]).T)
