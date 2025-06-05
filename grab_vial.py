from pymycobot import MyCobot280
import time
import json
import os
import glob


# ——— CONFIG ———
PORT            = "COM4"      # or "/dev/ttyUSB0"
BAUDRATE        = 115200
GRIPPER_ID      = 1           # gripper port ID (L/R). Usually 1 for the only gripper.
OPEN_FLAG       = 0           # 0=open, 1=close
CLOSE_FLAG      = 1
GRIP_SPEED      = 50          # 0–100
PROTECT_CURRENT = 200         # mA (1–500)
MOVE_SPEED      = 25          # joint motion speed
WAIT            = 3           # seconds between moves


def control_gripper(mc, flag, delay=1):
    mc.set_gripper_state(flag, GRIP_SPEED)
    time.sleep(delay)


def load_positions():
    files = glob.glob("vial_transfer_positions*.json")
    if not files:
        raise FileNotFoundError("No calibration JSON found")
    latest = max(files, key=os.path.getctime)
    with open(latest) as f:
        data = json.load(f)
    mapping = {
        'home_position':    'home',
        'above_vial':       'above_vial',
        'grab_vial':        'grab_vial',
        'lift_vial':        'lift_vial',
        'above_balance':    'above_balance',
        'place_balance':    'place_balance',
        'retreat_balance':  'retreat_balance'
    }
    pos = {}
    for jn, key in mapping.items():
        try:
            pos[key] = data['positions'][jn]['angles']
        except KeyError:
            raise KeyError(f"Missing {jn} in JSON")
    return pos


def vial_transfer_sequence():
    poses = load_positions()


    mc = MyCobot280(PORT, BAUDRATE)
    mc.power_on()
    time.sleep(2)


    # ——— Gripper zero‐calibration ———
    print(">> Entering free‐mode (torque OFF). Pull gripper fully open, then Enter.")
    mc.set_free_mode(1)                      # torque OFF
    input()


    mc.set_free_mode(0)                      # torque ON
    time.sleep(0.2)


    print(">> Stamping this as ‘open’ position (encoder→0)")
    mc.set_gripper_calibration()   # gripper zero = current pos
    time.sleep(0.2)


    mc.set_gripper_protect_current(PROTECT_CURRENT)
    time.sleep(0.2)


    print(">> Ensuring gripper is open…")
    control_gripper(mc, OPEN_FLAG, delay=1)


    # ——— Pick‐and‐place steps ———
    print("\n1) HOME")
    mc.send_angles(poses['home'], MOVE_SPEED);    time.sleep(WAIT)


    print("2) ABOVE VIAL")
    mc.send_angles(poses['above_vial'], MOVE_SPEED); time.sleep(WAIT)


    print("3) GRAB VIAL (close)")
    mc.send_angles(poses['grab_vial'], MOVE_SPEED);   time.sleep(WAIT)
    control_gripper(mc, CLOSE_FLAG)


    print("4) LIFT VIAL")
    mc.send_angles(poses['lift_vial'], MOVE_SPEED);    time.sleep(WAIT)


    print("5) ABOVE BALANCE")
    mc.send_angles(poses['above_balance'], MOVE_SPEED); time.sleep(WAIT)


    print("6) PLACE ON BALANCE (open)")
    mc.send_angles(poses['place_balance'], MOVE_SPEED); time.sleep(WAIT)
    control_gripper(mc, OPEN_FLAG)


    print("7) RETREAT")
    mc.send_angles(poses['retreat_balance'], MOVE_SPEED); time.sleep(WAIT)


    print("8) WAIT 10s")
    for i in range(10, 0, -1):
        print(f"   {i}s...", end="\r"); time.sleep(1)
    print()


    print("9) PICK UP FROM BALANCE (close)")
    mc.send_angles(poses['place_balance'], MOVE_SPEED); time.sleep(WAIT)
    control_gripper(mc, CLOSE_FLAG)


    print("10) LIFT FROM BALANCE")
    mc.send_angles(poses['retreat_balance'], MOVE_SPEED); time.sleep(WAIT)


    print("11) RETURN ABOVE VIAL")
    mc.send_angles(poses['above_vial'], MOVE_SPEED); time.sleep(WAIT)


    print("12) PLACE ON TABLE (open)")
    mc.send_angles(poses['grab_vial'], MOVE_SPEED); time.sleep(WAIT)
    control_gripper(mc, OPEN_FLAG)


    print("13) SAFE RETRACT")
    mc.send_angles(poses['above_vial'], MOVE_SPEED); time.sleep(WAIT)


    print("14) BACK TO HOME")
    mc.send_angles(poses['home'], MOVE_SPEED); time.sleep(WAIT)


    print("\n✅ Sequence complete!")


if __name__ == "__main__":
    if input("Proceed with vial transfer? (y/n): ").lower()=="y":
        vial_transfer_sequence()
    else:
        print("Aborted.")
