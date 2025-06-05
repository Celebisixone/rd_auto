from pymycobot import MyCobot280
import time

# ——— User configuration ———
PORT     = "COM4"    # e.g. "COM4" on Windows or "/dev/ttyUSB0" on Linux/Mac
BAUDRATE = 115200

# ——— Initialize and power on ———
mc = MyCobot280(PORT, BAUDRATE)
mc.power_on()
time.sleep(2)  # allow servos to spin up

# ——— Simple zero‐point calibration ———
# This records each joint’s current angle as its new “zero” reference.
for joint_id in range(1, 7):
    mc.set_servo_calibration(joint_id)
    time.sleep(0.1)

print("All joints calibrated to zero reference.") 

