# gripper_calibration.py
from pymycobot import MyCobot280
import time
import json
from datetime import datetime

# ——— CONFIGURATION ———
PORT        = "COM4"      # or "/dev/ttyUSB0"
BAUDRATE    = 115200
GRIP_SPEED  = 50           # 0–100
PROTECT_CUR = 200          # mA

# Filename to save calibration data
CAL_FILE    = "gripper_calibration.json"


def calibrate_gripper():
    """Standalone gripper zero-point calibration using init_gripper()."""
    print("Connecting to MyCobot280 for gripper calibration...")
    mc = MyCobot280(PORT, BAUDRATE)
    mc.power_on()
    time.sleep(2)

    # 1) Free-mode (torque OFF) so user can manually close gripper
    print(">> Entering FREE-MODE (torque OFF). Please pull the gripper FULLY CLOSED by hand.")
    mc.set_free_mode(1)
    input("Press Enter when gripper is fully closed...")

    # 2) Exit free-mode (torque ON)
    mc.set_free_mode(0)
    time.sleep(0.2)

    # 3) Initialize the adaptive gripper (homes encoder to current pos)
    print(">> Initializing gripper encoder (init_gripper())...")
    mc.init_gripper()  # use proper API call
    time.sleep(0.5)

    # 4) Set protection current to avoid stall oscillation
    mc.set_gripper_protect_current(PROTECT_CUR)
    time.sleep(0.2)

    # 5) Test open/close (ensure physical movement)
    print(">> Testing gripper movement...")
    # 5a) State-based open (spread)
    mc.set_gripper_state(0, GRIP_SPEED)
    time.sleep(1)
    # 5b) Value-based full open
    mc.set_gripper_value(100, GRIP_SPEED)
    time.sleep(1)
    # 5c) Close (clamp) and reopen
    mc.set_gripper_state(1, GRIP_SPEED)
    time.sleep(1)
    mc.set_gripper_value(0, GRIP_SPEED)
    time.sleep(1)
    mc.set_gripper_state(0, GRIP_SPEED)
    time.sleep(1)

    # 6) Read encoder value for confirmation
    val = mc.get_gripper_value()
    print(f"Calibration complete. Gripper encoder reading: {val}")

    # 7) Save calibration
    calibration = {
        "init_timestamp": datetime.now().isoformat(),
        "protect_current": PROTECT_CUR,
        "encoder_value_after_open": val
    }
    with open(CAL_FILE, 'w') as f:
        json.dump(calibration, f, indent=2)
    print(f"Calibration saved to {CAL_FILE}")


if __name__ == "__main__":
    calibrate_gripper()
# gripper_calibration.py
from pymycobot import MyCobot280
import time
import json
from datetime import datetime

# ——— CONFIGURATION ———
PORT        = "COM4"      # or "/dev/ttyUSB0"
BAUDRATE    = 115200
PROTECT_CUR = 200          # mA
CAL_FILE    = "gripper_calibration.json"


def calibrate_gripper():
    """Standalone gripper zero-point and range calibration."""
    print("Connecting to MyCobot280 for gripper calibration...")
    mc = MyCobot280(PORT, BAUDRATE)
    mc.power_on()
    time.sleep(2)

    # --- Calibrate CLOSED position (zero) ---
    print(">> Entering free-mode (torque OFF). Please pull the gripper FULLY CLOSED by hand.")
    mc.set_free_mode(1)
    input("Press Enter when gripper is fully CLOSED...")

    mc.set_free_mode(0)
    time.sleep(0.2)

    print(">> Stamping current closed position as zero...")
    mc.init_gripper()            # homes encoder to closed
    time.sleep(0.5)
    closed_zero = mc.get_gripper_value()
    print(f"   Closed encoder = {closed_zero}")

    # --- Calibrate OPEN position (max) ---
    print(">> Entering free-mode (torque OFF). Please pull the gripper FULLY OPEN by hand.")
    mc.set_free_mode(1)
    input("Press Enter when gripper is fully OPEN...")

    mc.set_free_mode(0)
    time.sleep(0.2)

    open_max = mc.get_gripper_value()
    print(f"   Open encoder = {open_max}")

    # --- Protection current ---
    mc.set_gripper_protect_current(PROTECT_CUR)
    time.sleep(0.2)

    # --- Save calibration data ---
    calibration = {
        "timestamp": datetime.now().isoformat(),
        "closed_zero": closed_zero,
        "open_max": open_max,
        "protect_current": PROTECT_CUR
    }
    with open(CAL_FILE, 'w') as f:
        json.dump(calibration, f, indent=2)
    print(f"Calibration saved to {CAL_FILE}")


if __name__ == "__main__":
    calibrate_gripper()



