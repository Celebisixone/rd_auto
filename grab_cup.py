# power_safe_grab_cup.py
from pymycobot import MyCobot280
import time
import json
import glob
import os

# ——— POWER-SAFE CONFIGURATION ———
PORT               = "COM4"       # Serial port
BAUDRATE           = 115200       # Baud rate
MOVE_SPEED         = 15           # REDUCED speed for power issues
WAIT               = 4            # INCREASED wait time
GRIP_SPEED         = 30           # REDUCED gripper speed
POWER_REST_TIME    = 2            # Rest between power-intensive moves
GRIP_CAL_FILE      = "gripper_calibration.json"
CUP_JSON_PATTERN   = "cup_collection_positions.json"

# ——— LOAD GRIPPER CALIBRATION ———
if not os.path.exists(GRIP_CAL_FILE):
    print(f"Error: Gripper calibration file '{GRIP_CAL_FILE}' not found. Run calibration first.")
    exit(1)

# ——— LOAD CUP POSITIONS ———
cup_files = glob.glob(CUP_JSON_PATTERN)
if not cup_files:
    print(f"Error: No cup positions JSON matching '{CUP_JSON_PATTERN}' found.")
    exit(1)

cuplist = glob.glob(CUP_JSON_PATTERN)
cup_file = max(cuplist, key=os.path.getctime)
print(f"Loading cup positions from: {cup_file}")

with open(cup_file, 'r') as f:
    cup_json_data = json.load(f)

cup_data = cup_json_data['positions']
print(f"Loaded {len(cup_data)} positions from JSON")

# ——— POWER-SAFE UTILITIES ———
def power_rest():
    """Give servos time to recover between movements."""
    print(f"   >> Power rest ({POWER_REST_TIME}s)...")
    time.sleep(POWER_REST_TIME)

def servo_health_check(mc):
    """Check if servos are responding properly."""
    try:
        angles = mc.get_angles()
        if angles and angles != -1:
            return True
        else:
            print("   WARNING: Servos not responding")
            return False
    except:
        print("   WARNING: Cannot communicate with servos")
        return False

def control_gripper_safe(mc, state, delay=2):
    """Power-safe gripper control with error handling."""
    action = "Opening" if state == 0 else "Closing"
    print(f"   >> {action} gripper (power-safe mode)...")
    
    try:
        # Check servo health before gripper operation
        if not servo_health_check(mc):
            print("   WARNING: Servo health check failed before gripper operation")
        
        mc.set_gripper_state(state, GRIP_SPEED)
        time.sleep(delay)
        
        # Rest after gripper operation
        power_rest()
        
    except Exception as e:
        print(f"   ERROR controlling gripper: {e}")
        # Try to recover
        time.sleep(3)
        raise

def move_to_position_safe(mc, position_name, description=""):
    """Power-safe movement with retries and health checks."""
    if position_name not in cup_data:
        raise KeyError(f"Position '{position_name}' not found in JSON")
    
    if description:
        print(f"-- {description} --")
    else:
        print(f"-- Moving to {position_name} --")
    
    angles = cup_data[position_name]['angles']
    print(f"   Target angles: {angles}")
    
    # Pre-movement servo check
    if not servo_health_check(mc):
        print("   WARNING: Servo health check failed before movement")
        print("   Attempting servo recovery...")
        mc.power_on()
        time.sleep(3)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"   Movement attempt {attempt + 1}/{max_retries}")
            mc.send_angles(angles, MOVE_SPEED)
            time.sleep(WAIT)
            
            # Verify movement
            current_angles = mc.get_angles()
            if current_angles and current_angles != -1:
                print(f"   Reached: {current_angles}")
                power_rest()  # Rest after successful movement
                return
            else:
                print(f"   Attempt {attempt + 1} failed - cannot verify position")
                if attempt < max_retries - 1:
                    print("   Retrying with servo reset...")
                    mc.power_on()
                    time.sleep(3)
                
        except Exception as e:
            print(f"   Movement attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("   Retrying after recovery delay...")
                time.sleep(5)
                mc.power_on()
                time.sleep(3)
            else:
                raise

# ——— POWER-SAFE CUP SEQUENCE ———
def cup_sequence_safe(mc, cup_num):
    """Power-safe cup handling sequence with enhanced error recovery."""
    
    # Validate cup number
    if cup_num < 1 or cup_num > 8:
        raise ValueError(f"Cup number must be between 1 and 8, got {cup_num}")
    
    # Check required positions exist
    safe_height_key = f'cup_{cup_num}_safe_height'
    right_above_key = f'cup_{cup_num}_right_above'
    inside_key = f'cup_{cup_num}_inside'
    
    required_positions = [
        'balance_position',
        'balance_right_above',
        'balance_safe_height', 
        safe_height_key,
        right_above_key,
        inside_key
    ]
    
    missing_positions = [pos for pos in required_positions if pos not in cup_data]
    if missing_positions:
        raise KeyError(f"Missing required positions: {missing_positions}")
    
    print(f"\n{'='*60}")
    print(f"STARTING POWER-SAFE SEQUENCE FOR CUP {cup_num}")
    print(f"{'='*60}")
    
    try:
        # Initial servo health check
        print("Initial servo health check...")
        if not servo_health_check(mc):
            print("Initial servo health check failed - attempting recovery...")
            mc.power_on()
            time.sleep(5)
        
        # Step 1: Home position
        print("Step 1: Move to Home Position")
        mc.send_angles([0, 0, 0, 0, 0, 0], MOVE_SPEED)
        time.sleep(WAIT)
        power_rest()
        
        # Step 2: Safe height above cup
        print(f"Step 2: Move to Safe Height Above Cup {cup_num}")
        move_to_position_safe(mc, safe_height_key, f"Safe Height Cup {cup_num}")
        
        # Step 3: Open gripper
        print("Step 3: Open Gripper (Prepare to Grab Cup)")
        control_gripper_safe(mc, 0)
        
        # Step 4: Right above cup
        print(f"Step 4: Move Right Above Cup {cup_num}")
        move_to_position_safe(mc, right_above_key, f"Right Above Cup {cup_num}")
        
        # Step 5: Move inside cup
        print(f"Step 5: Move Inside Cup {cup_num}")
        move_to_position_safe(mc, inside_key, f"Inside Cup {cup_num}")
        
        # Step 6: Close gripper
        print("Step 6: Close Gripper (Grab Cup)")
        control_gripper_safe(mc, 1)
        
        # Step 7: Lift to right above cup
        print(f"Step 7: Lift to Right Above Cup {cup_num}")
        move_to_position_safe(mc, right_above_key, f"Lift to Right Above Cup {cup_num}")
        
        # Step 8: Lift to safe height
        print(f"Step 8: Lift to Safe Height Above Cup {cup_num}")
        move_to_position_safe(mc, safe_height_key, f"Lift to Safe Height Cup {cup_num}")
        
        # Step 9: Move to balance safe height
        print("Step 9: Move to Balance Safe Height")
        move_to_position_safe(mc, 'balance_safe_height', "Balance Safe Height")
        
        # Step 10: Move to balance right above
        print("Step 10: Move to Balance Right Above")
        move_to_position_safe(mc, 'balance_right_above', "Balance Right Above")
        
        # Step 11: Move to balance position
        print("Step 11: Move to Balance Position")
        move_to_position_safe(mc, 'balance_position', "Balance Position")
        
        # Step 12: Open gripper
        print("Step 12: Open Gripper (Release Cup on Balance)")
        control_gripper_safe(mc, 0)
        
        # Step 13: Move to balance right above
        print("Step 13: Move to Balance Right Above")
        move_to_position_safe(mc, 'balance_right_above', "Balance Right Above (Retreat)")
        
        # Step 14: Move to balance safe height
        print("Step 14: Move to Balance Safe Height")
        move_to_position_safe(mc, 'balance_safe_height', "Balance Safe Height (Retreat)")
        
        # Step 15: Wait for measurement
        print("Step 15: Wait 5 seconds for measurement")
        for i in range(5, 0, -1):
            print(f"   Waiting... {i}s remaining", end="\r")
            time.sleep(1)
        print("\n   Measurement complete!")
        
        # Step 16: Return to balance right above
        print("Step 16: Return to Balance Right Above")
        move_to_position_safe(mc, 'balance_right_above', "Return to Balance Right Above")
        
        # Step 17: Return to balance position
        print("Step 17: Return to Balance Position")
        move_to_position_safe(mc, 'balance_position', "Return to Balance")
        
        # Step 18: Close gripper
        print("Step 18: Close Gripper (Grab Cup from Balance)")
        control_gripper_safe(mc, 1)
        
        # Step 19: Lift to balance right above
        print("Step 19: Lift to Balance Right Above")
        move_to_position_safe(mc, 'balance_right_above', "Lift to Balance Right Above")
        
        # Step 20: CRITICAL STEP - Move to balance safe height with cup
        print("Step 20: Move to Balance Safe Height (CRITICAL STEP)")
        print("   >> This is where failures typically occur due to power issues")
        print("   >> Using maximum power-safe protocols...")
        
        # Extra servo health check before critical step
        if not servo_health_check(mc):
            print("   >> Servo health check failed - performing extended recovery...")
            mc.power_on()
            time.sleep(5)
            power_rest()
        
        move_to_position_safe(mc, 'balance_safe_height', "Balance Safe Height (With Cup - CRITICAL)")
        
        # Extended rest after critical step
        print("   >> Critical step completed - extended recovery...")
        time.sleep(3)
        
        # Continue with remaining steps...
        print(f"Step 21: Move to Safe Height Above Cup {cup_num}")
        move_to_position_safe(mc, safe_height_key, f"Return to Safe Height Cup {cup_num}")
        
        print(f"Step 22: Move to Right Above Cup {cup_num}")
        move_to_position_safe(mc, right_above_key, f"Return to Right Above Cup {cup_num}")
        
        print(f"Step 23: Move Inside Cup {cup_num}")
        move_to_position_safe(mc, inside_key, f"Return Inside Cup {cup_num}")
        
        print("Step 24: Open Gripper (Release Cup)")
        control_gripper_safe(mc, 0)
        
        print(f"Step 25: Move to Right Above Cup {cup_num}")
        move_to_position_safe(mc, right_above_key, f"Final Right Above Cup {cup_num}")
        
        print(f"Step 26: Move to Safe Height Above Cup {cup_num}")
        move_to_position_safe(mc, safe_height_key, f"Final Safe Height Cup {cup_num}")
        
        print("Step 27: Return to Home Position")
        mc.send_angles([0, 0, 0, 0, 0, 0], MOVE_SPEED)
        time.sleep(WAIT)
        
        print(f"\nSUCCESS: Cup {cup_num} sequence completed!")
        
    except Exception as e:
        print(f"\nERROR: Cup {cup_num} sequence failed: {e}")
        print("Attempting power-safe recovery to home position...")
        try:
            mc.power_on()
            time.sleep(5)
            mc.send_angles([0, 0, 0, 0, 0, 0], 10)  # Very slow return
            time.sleep(6)
        except Exception as recovery_error:
            print(f"WARNING: Recovery failed: {recovery_error}")
        raise

# ——— OPERATION MODES ———
def single_sequence_safe():
    """Handle a single cup with power-safe protocols."""
    mc = MyCobot280(PORT, BAUDRATE)
    print("Initializing robot with power-safe protocols...")
    mc.power_on()
    time.sleep(5)  # Extended initialization time
    
    print("Available cups: 1-8")
    n = int(input("Enter cup number (1-8): "))
    
    if n < 1 or n > 8:
        print("Error: Cup number must be between 1 and 8")
        return
    
    cup_sequence_safe(mc, n)

def batch_sequence_safe():
    """Handle multiple cups with power-safe protocols."""
    print("Available cups: 1-8")
    s = input("Enter cup numbers (e.g. 1,3,5 or 1-4): ")
    
    # Parse input
    cups = []
    if '-' in s:
        try:
            parts = s.split('-')
            if len(parts) == 2:
                a, b = int(parts[0]), int(parts[1])
                if 1 <= a <= 8 and 1 <= b <= 8 and a <= b:
                    cups = list(range(a, b+1))
                else:
                    print("Error: Range must be between 1-8")
                    return
        except ValueError:
            print("Error: Invalid range format")
            return
    else:
        try:
            cups = [int(x.strip()) for x in s.split(',')]
            if not all(1 <= cup <= 8 for cup in cups):
                print("Error: All cup numbers must be between 1-8")
                return
        except ValueError:
            print("Error: Invalid cup number format")
            return
    
    print(f"Processing cups: {cups}")
    print("Power-safe batch mode: Extended recovery between cups")
    
    # Initialize robot once for entire batch
    mc = MyCobot280(PORT, BAUDRATE)
    print("Initializing robot with power-safe protocols...")
    mc.power_on()
    time.sleep(5)  # Extended initialization time
    
    successful_cups = []
    failed_cups = []
    
    for i, cup_num in enumerate(cups):
        try:
            print(f"\n{'='*80}")
            print(f"PROCESSING CUP {cup_num} ({i+1}/{len(cups)}) - POWER-SAFE MODE")
            print(f"{'='*80}")
            
            # Pre-cup servo health check and recovery
            print("Pre-cup system check...")
            if not servo_health_check(mc):
                print("System health check failed - performing recovery...")
                mc.power_on()
                time.sleep(5)
                power_rest()
            
            # Execute cup sequence
            cup_sequence_safe(mc, cup_num)
            successful_cups.append(cup_num)
            print(f"Cup {cup_num} completed successfully!")
            
            # Inter-cup recovery period (except for last cup)
            if i < len(cups) - 1:
                print(f"\n--- Inter-Cup Recovery Period ---")
                print("Allowing servos to cool down and recover...")
                
                # Extended rest between cups
                recovery_time = 10
                for j in range(recovery_time, 0, -1):
                    print(f"Recovery countdown: {j}s remaining", end="\r")
                    time.sleep(1)
                print("\nRecovery complete - ready for next cup")
                
                # Servo health check before next cup
                print("Pre-next-cup health check...")
                if not servo_health_check(mc):
                    print("Health check failed - performing extended recovery...")
                    mc.power_on()
                    time.sleep(5)
                    power_rest()
            
        except Exception as e:
            print(f"Error handling Cup {cup_num}: {e}")
            failed_cups.append(cup_num)
            
            # Enhanced error recovery for batch mode
            print("Performing error recovery...")
            try:
                mc.power_on()
                time.sleep(5)
                mc.send_angles([0, 0, 0, 0, 0, 0], 10)  # Slow return to home
                time.sleep(6)
                power_rest()
                print("Error recovery completed")
            except Exception as recovery_error:
                print(f"Error recovery failed: {recovery_error}")
            
            # Ask user if they want to continue
            print(f"\nCup {cup_num} failed. Remaining cups: {cups[i+1:]}")
            choice = input("Continue with remaining cups? (y/n): ").lower()
            if choice != 'y':
                break
    
    # Final batch summary
    print(f"\n{'='*80}")
    print("POWER-SAFE BATCH RESULTS")
    print(f"{'='*80}")
    print(f"Total cups processed: {len(successful_cups) + len(failed_cups)}/{len(cups)}")
    print(f"Successful: {successful_cups}")
    print(f"Failed: {failed_cups}")
    
    if failed_cups:
        success_rate = len(successful_cups) / len(cups) * 100
        print(f"Success rate: {success_rate:.1f}%")
        
        if success_rate < 50:
            print("\nLOW SUCCESS RATE - RECOMMENDATIONS:")
            print("1. Check power supply (should be 12V, 8A minimum)")
            print("2. Verify servo voltages (servos 4-6 showing low voltage)")
            print("3. Consider hardware service for internal power issues")
            print("4. Try processing fewer cups at once")
        elif success_rate < 80:
            print("\nMODERATE SUCCESS RATE - Consider:")
            print("1. Reducing batch size")
            print("2. Increasing recovery time between cups")
            print("3. Checking for overheating issues")
    else:
        print("All cups processed successfully!")
    
    print("Batch processing complete.")

def test_sequence_safe():
    """Test with Cup 1 using power-safe protocols."""
    mc = MyCobot280(PORT, BAUDRATE)
    print("Initializing robot for power-safe test...")
    mc.power_on()
    time.sleep(5)
    
    print("Running power-safe test sequence with Cup 1...")
    cup_sequence_safe(mc, 1)

def main():
    print("="*60)
    print("MyCobot 280 Power-Safe Cup Handler")
    print("="*60)
    print("This version includes power management for voltage issues")
    print("- Reduced speeds for lower power consumption")
    print("- Extended wait times for servo recovery")
    print("- Enhanced error handling and retries")
    print("- Special handling for Step 20 (critical failure point)")
    print("- Inter-cup recovery periods for batch processing")
    print()
    
    while True:
        print("Options:")
        print("1) Single Cup (Power-Safe Mode)")
        print("2) Batch Cups (Power-Safe Mode)")
        print("3) Test (Cup 1, Power-Safe Mode)")
        print("4) Exit")
        
        choice = input("Select option (1-4): ").strip()
        
        if choice == '1':
            single_sequence_safe()
        elif choice == '2':
            batch_sequence_safe()
        elif choice == '3':
            test_sequence_safe()
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please select 1-4.")
        
        print()  # Add spacing between operations

if __name__ == "__main__":
    main()