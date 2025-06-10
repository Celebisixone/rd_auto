# grab_container_minimal_hang_free.py - Eliminate All Hanging Points
from pymycobot import MyCobot280
import time
import json
import glob
import os

# ——— MINIMAL CONFIGURATION ———
PORT = "COM4"
BAUDRATE = 115200
MOVE_SPEED = 10
MOVE_WAIT = 8  # Realistic time for robot movements to complete
GRIPPER_WAIT = 3  # Time for gripper to fully open/close
GRIP_SPEED = 40
CONTAINER_JSON_PATTERN = "cup_collection_positions.json"

# ——— LOAD POSITIONS ———
container_files = glob.glob(CONTAINER_JSON_PATTERN)
container_file = max(container_files, key=os.path.getctime)
print(f"Loading: {container_file}")

with open(container_file, 'r') as f:
    container_json_data = json.load(f)

container_data = container_json_data['positions']
total_containers = container_json_data['calibration_info']['layout']['total_containers']

# ——— MINIMAL HANG-FREE MANAGER ———
class MinimalHangFreeManager:
    def __init__(self):
        self.mc = None
        self.step_count = 0
        
    def connect(self):
        """Minimal connection - no verification checks."""
        print("Connecting...")
        self.mc = MyCobot280(PORT, BAUDRATE, timeout=0.05, thread_lock=False)
        time.sleep(1)
        print("Connected")
    
    def send_command_fire_and_forget(self, command_func, *args, custom_wait=None):
        """Send command with realistic wait times for actual robot movement."""
        self.step_count += 1
        print(f"   >> Command {self.step_count}: Sending...")
        
        try:
            command_func(*args)
            print(f"   >> Command {self.step_count}: Sent - Robot moving...")
        except Exception as e:
            print(f"   >> Command {self.step_count}: Error {e} - continuing")
        
        # Use custom wait time if provided, otherwise use movement wait
        wait_time = custom_wait if custom_wait is not None else MOVE_WAIT
        
        # Show realistic progress during wait
        for i in range(wait_time):
            time.sleep(1)
            print(f"   >> Waiting... {i+1}/{wait_time}s")
        
        print(f"   >> Command {self.step_count}: Movement complete")
    
    def move_direct(self, position_name, description="", extra_wait=0):
        """Direct movement with realistic timing."""
        if position_name not in container_data:
            print(f"   >> {position_name} not found - SKIP")
            return
        
        if description:
            print(f"-- {description} --")
        
        target_angles = container_data[position_name]['angles']
        print(f"   Target: {target_angles}")
        
        # Direct movement with realistic wait time
        self.send_command_fire_and_forget(self.mc.send_angles, target_angles, MOVE_SPEED)
        
        # Extra wait at specific positions if needed
        if extra_wait > 0:
            print(f"   >> Extra wait at position: {extra_wait}s")
            for i in range(extra_wait):
                time.sleep(1)
                print(f"   >> Position wait... {i+1}/{extra_wait}s")
            print("   >> Position wait complete")
    
    def grip_direct(self, state, description=""):
        """Direct gripper with proper timing."""
        action = "Open" if state == 0 else "Close"
        if description:
            print(f"   >> {description}")
        else:
            print(f"   >> {action} gripper")
        
        # Always use gripper wait time for gripper operations
        self.send_command_fire_and_forget(self.mc.set_gripper_state, state, GRIP_SPEED, custom_wait=GRIPPER_WAIT)

# ——— MINIMAL CONTAINER SEQUENCE ———
def minimal_container_sequence(mgr, container_num):
    """Minimal sequence - no verification, no complex logic."""
    
    print(f"\n{'='*60}")
    print(f"MINIMAL HANG-FREE - CONTAINER {container_num}")
    print(f"{'='*60}")
    
    pickup_key = f'container_{container_num}_pickup'
    
    print("OUTBOUND")
    print("-" * 20)
    
    # 1. Home
    print("1. Home")
    mgr.send_command_fire_and_forget(mgr.mc.send_angles, [0,0,0,0,0,0], MOVE_SPEED)
    
    # 2. Shared safe
    print("2. Shared Safe")
    mgr.move_direct('shared_safe_height', "Start")
    
    # 3. Open gripper
    print("3. Open Gripper")
    mgr.grip_direct(0, "Prepare pickup")
    
    # 4. Container pickup - WITH 2s WAIT AT POSITION
    print(f"4. Container {container_num}")
    mgr.move_direct(pickup_key, f"Container {container_num} - stopping for 2s", extra_wait=2)
    
    # 5. Close gripper
    print("5. Close Gripper")
    mgr.grip_direct(1, "Grab container")
    
    # 6. Shared safe
    print("6. Shared Safe")
    mgr.move_direct('shared_safe_height', "With container")
    
    # 7. Balance safe
    print("7. Balance Safe")
    mgr.move_direct('balance_safe_height', "Approach")
    
    # 8. Balance
    print("8. Balance")
    mgr.move_direct('balance_position', "Drop")
    
    # 9. Open gripper
    print("9. Open Gripper")
    mgr.grip_direct(0, "Release")
    
    # 10. Balance safe
    print("10. Balance Safe")
    mgr.move_direct('balance_safe_height', "Retreat")
    
    # 11. Shared safe
    print("11. Shared Safe")
    mgr.move_direct('shared_safe_height', "Wait")
    
    print("MEASURE")
    print("-" * 20)
    
    # 12. Wait
    print("12. Measure")
    time.sleep(3)
    print("   >> Measure done")
    
    print("RETURN")
    print("-" * 20)
    
    # 13. Balance safe
    print("13. Balance Safe")
    mgr.move_direct('balance_safe_height', "Return approach")
    
    # 14. Balance
    print("14. Balance")
    mgr.move_direct('balance_position', "Pickup")
    
    # 15. Close gripper
    print("15. Close Gripper")
    mgr.grip_direct(1, "Grab from balance")
    
    # 16. Balance safe
    print("16. Balance Safe")
    mgr.move_direct('balance_safe_height', "Return with container")
    
    # 17. Shared safe
    print("17. Shared Safe")
    mgr.move_direct('shared_safe_height', "Return transit")
    
    # 18. Container return - WITH 2s WAIT AT POSITION
    print(f"18. Container {container_num}")
    mgr.move_direct(pickup_key, f"Return container {container_num} - stopping for 2s", extra_wait=2)
    
    # 19. Open gripper
    print("19. Open Gripper")
    mgr.grip_direct(0, "Release container")
    
    # 20. Shared safe
    print("20. Shared Safe")
    mgr.move_direct('shared_safe_height', "Final")
    
    # 21. Home
    print("21. Home")
    mgr.send_command_fire_and_forget(mgr.mc.send_angles, [0,0,0,0,0,0], MOVE_SPEED)
    
    print(f"\nCOMPLETE: Container {container_num}")
    print(f"Total commands: {mgr.step_count}")
    return True

# ——— EVEN MORE MINIMAL VERSION ———
def ultra_minimal_sequence(container_num):
    """Ultra minimal - direct PyMyCobot calls."""
    
    print(f"\n{'='*60}")
    print(f"ULTRA MINIMAL - CONTAINER {container_num}")
    print(f"{'='*60}")
    
    # Direct connection
    mc = MyCobot280(PORT, BAUDRATE, timeout=0.05, thread_lock=False)
    time.sleep(1)
    
    pickup_key = f'container_{container_num}_pickup'
    
    def send_and_wait(command_func, *args, is_gripper=False):
        print("   >> Sending...")
        try:
            command_func(*args)
            print("   >> Sent - Robot moving...")
        except Exception as e:
            print(f"   >> Error: {e}")
        
        # Use appropriate wait time
        wait_time = GRIPPER_WAIT if is_gripper else MOVE_WAIT
        
        # Show progress during wait
        for i in range(wait_time):
            time.sleep(1)
            print(f"   >> Waiting... {i+1}/{wait_time}s")
        
        print("   >> Movement complete")
    
    def move_to(pos_name, extra_wait=0):
        if pos_name in container_data:
            angles = container_data[pos_name]['angles']
            print(f"   Target: {angles}")
            send_and_wait(mc.send_angles, angles, MOVE_SPEED)
            
            # Extra wait at specific positions if needed
            if extra_wait > 0:
                print(f"   >> Extra wait at position: {extra_wait}s")
                for i in range(extra_wait):
                    time.sleep(1)
                    print(f"   >> Position wait... {i+1}/{extra_wait}s")
                print("   >> Position wait complete")
        else:
            print(f"   {pos_name} missing - skip")
    
    print("1. Home")
    send_and_wait(mc.send_angles, [0,0,0,0,0,0], MOVE_SPEED)
    
    print("2. Shared Safe")
    move_to('shared_safe_height')
    
    print("3. Open Gripper")
    send_and_wait(mc.set_gripper_state, 0, GRIP_SPEED, is_gripper=True)
    
    print(f"4. Container {container_num} - WITH 2s WAIT")
    move_to(pickup_key, extra_wait=2)
    
    print("5. Close Gripper")
    send_and_wait(mc.set_gripper_state, 1, GRIP_SPEED, is_gripper=True)
    
    print("6. Shared Safe")
    move_to('shared_safe_height')
    
    print("7. Balance Safe")
    move_to('balance_safe_height')
    
    print("8. Balance")
    move_to('balance_position')
    
    print("9. Open Gripper")
    send_and_wait(mc.set_gripper_state, 0, GRIP_SPEED, is_gripper=True)
    
    print("10. Balance Safe")
    move_to('balance_safe_height')
    
    print("12. Measure")
    time.sleep(3)
    
    print("14. Balance")
    move_to('balance_position')
    
    print("15. Close Gripper")
    send_and_wait(mc.set_gripper_state, 1, GRIP_SPEED, is_gripper=True)
    
    print("16. Balance Safe")
    move_to('balance_safe_height')
    
    print("17. Shared Safe")
    move_to('shared_safe_height')
    
    print(f"18. Container {container_num} - WITH 2s WAIT")
    move_to(pickup_key, extra_wait=2)
    
    print("19. Open Gripper")
    send_and_wait(mc.set_gripper_state, 0, GRIP_SPEED, is_gripper=True)
    
    print("20. Shared Safe")
    move_to('shared_safe_height')
    
    print("21. Home")
    send_and_wait(mc.send_angles, [0,0,0,0,0,0], MOVE_SPEED)
    
    print(f"ULTRA MINIMAL COMPLETE: Container {container_num}")
    
    # Close connection
    try:
        mc.close()
    except:
        pass
    
    return True

# ——— OPERATION MODES ———
def single_minimal():
    """Single container - minimal version."""
    mgr = MinimalHangFreeManager()
    mgr.connect()
    
    n = int(input(f"Container (1-{total_containers}): "))
    if 1 <= n <= total_containers:
        minimal_container_sequence(mgr, n)
    else:
        print("Invalid number")

def single_ultra_minimal():
    """Single container - ultra minimal version."""
    n = int(input(f"Container (1-{total_containers}): "))
    if 1 <= n <= total_containers:
        ultra_minimal_sequence(n)
    else:
        print("Invalid number")

def batch_ultra_minimal():
    """Batch - ultra minimal."""
    s = input("Containers (e.g. 1,2): ")
    try:
        containers = [int(x.strip()) for x in s.split(',')]
        if all(1 <= c <= total_containers for c in containers):
            for i, n in enumerate(containers):
                print(f"\nBATCH {i+1}/{len(containers)}")
                ultra_minimal_sequence(n)
                if i < len(containers) - 1:
                    print("--- 3s pause ---")
                    time.sleep(3)
            print("BATCH COMPLETE")
        else:
            print("Invalid numbers")
    except:
        print("Invalid format")

def main():
    print("="*60)
    print("MINIMAL HANG-FREE Container Handler")
    print("="*60)
    print("DESIGNED TO NEVER HANG:")
    print("✓ No position verification")
    print("✓ No 3-step movements")  
    print("✓ No retry loops")
    print("✓ No complex error handling")
    print("✓ Direct command + wait pattern")
    print("✓ Ultra-short timeout (0.05s)")
    print("✓ No thread locks")
    print("✓ Realistic movement timing (8s per move)")
    print("✓ 2s wait at container positions before gripper actions")
    print()
    
    while True:
        print("Options:")
        print("1) Single Container (Minimal)")
        print("2) Single Container (Ultra Minimal)")
        print("3) Batch Containers (Ultra Minimal)")
        print("4) Exit")
        
        choice = input("Select (1-4): ").strip()
        
        if choice == '1':
            single_minimal()
        elif choice == '2':
            single_ultra_minimal()
        elif choice == '3':
            batch_ultra_minimal()
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()