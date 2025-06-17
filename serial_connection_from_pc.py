import serial
import json

# Configure your serial port
ser = serial.Serial('/dev/ttyUSB0', 9600)  # Change as needed
print("Waiting for data...")

# Read until newline (sender adds '\n')
line = ser.readline().decode('utf-8').strip()
vector = json.loads(line)

print("Received vector:", vector)
ser.close()
