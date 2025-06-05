from pymycobot import MyCobot280
import time
import json
from datetime import datetime

# Initialize robot connection with error handling
print("Connecting to MyCobot 280...")
try:
    mc = MyCobot280("COM4", 115200)  # Change COM port as needed
    print("Robot object created")
    
    mc.power_on()
    print("Power on command sent")
    time.sleep(3)  # Give more time for initialization
    
    # Test connection
    print("Testing robot connection...")
    test_connection = False
    for attempt in range(3):
        try:
            if mc.is_controller_connected():
                print("Robot controller is connected and responding")
                test_connection = True
                break
            else:
                print(f"Attempt {attempt + 1}: Controller not responding")
                time.sleep(2)
        except Exception as e:
            print(f"Attempt {attempt + 1}: Connection test error: {e}")
            time.sleep(2)
    
    if not test_connection:
        print("Warning: Cannot verify robot connection")
        print("Continuing anyway - robot may still work...")
        
except Exception as e:
    print(f"Failed to initialize robot: {e}")
    print("\nTroubleshooting tips:")
    print("- Check COM port (Windows: Device Manager)")
    print("- Ensure robot is powered on")
    print("- Check USB cable connection")
    print("- Verify robot firmware is properly installed")
    exit(1)

print("="*60)
print("   MYCOBOT 280 VIAL TRANSFER CALIBRATION SCRIPT")
print("="*60)
print("This script will collect positions for:")
print("1. Start/Home position (0°)")
print("2. Above vial position (safe approach)")
print("3. Grab vial position (surface level)")
print("4. Lift vial position (after grabbing)")
print("5. Above balance position (safe approach)")
print("6. Place on balance position")
print("7. Retreat from balance position")
print("8. Return to home position")
print("="*60)

# Dictionary to store all positions
positions = {}

def safe_get_position():
    """Safely get robot position with proper error handling"""
    angles = None
    coords = None
    
    for attempt in range(5):  # Try more times
        try:
            print(f"    Reading position (attempt {attempt + 1})...")
            
            # Clear any pending data
            time.sleep(0.5)
            
            # Try to get angles
            angles_raw = mc.get_angles()
            coords_raw = mc.get_coords()
            
            # Debug: Print raw data type and value
            print(f"    Raw angles type: {type(angles_raw)}, value: {angles_raw}")
            print(f"    Raw coords type: {type(coords_raw)}, value: {coords_raw}")
            
            # Handle different return types
            if angles_raw is not None:
                if isinstance(angles_raw, list) and len(angles_raw) == 6:
                    angles = angles_raw
                    print(f"    Angles OK: {angles}")
                elif isinstance(angles_raw, (int, float)):
                    print(f"    Warning: Got single value for angles: {angles_raw}")
                    continue
                else:
                    print(f"    Warning: Unexpected angles format: {angles_raw}")
                    continue
            
            if coords_raw is not None:
                if isinstance(coords_raw, list) and len(coords_raw) == 6:
                    coords = coords_raw
                    print(f"    Coords OK: {coords}")
                elif isinstance(coords_raw, (int, float)):
                    print(f"    Warning: Got single value for coords: {coords_raw}")
                    continue
                else:
                    print(f"    Warning: Unexpected coords format: {coords_raw}")
                    continue
            
            # If we got both valid readings, return them
            if angles is not None and coords is not None:
                return angles, coords
            
            print(f"    Attempt {attempt + 1} failed, retrying...")
            time.sleep(1)
            
        except Exception as e:
            print(f"    Attempt {attempt + 1}: Error reading position: {e}")
            time.sleep(1)
    
    print("    Failed to get valid position data after 5 attempts")
    return None, None

def reset_to_zero():
    """Reset all joints to zero position"""
    print("\nResetting all joints to ZERO position...")
    for i in range(1, 7):
        print(f"  Setting joint {i} to 0°...")
        mc.send_angle(i, 0, 30)
        time.sleep(1.5)
    
    print("  Waiting for movements to complete...")
    time.sleep(4)  # Longer wait
    
    # Verify zero position with better error handling
    print("  Reading current position...")
    angles, coords = safe_get_position()
    
    if angles is None or coords is None:
        print("  Warning: Could not verify zero position")
        print("  Using default zero values...")
        angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        coords = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    else:
        print(f"  Zero Position - Angles: {[round(a, 2) for a in angles]}")
        print(f"  Zero Position - Coords: {[round(c, 2) for c in coords]}")
    
    return angles, coords

def record_position(position_name, description):
    """Record current position with user confirmation"""
    print(f"\n{position_name.upper()}:")
    print(f"   {description}")
    
    # Release servos for manual positioning
    mc.release_all_servos()
    time.sleep(0.5)
    print("   Joints are FREE for manual movement")
    
    input(f"   Move robot to {position_name}, then press Enter...")
    
    # Record position with better error handling
    print("   Recording position...")
    angles, coords = safe_get_position()
    
    if angles is not None and coords is not None:
        positions[position_name] = {
            'angles': [round(a, 2) for a in angles],
            'coordinates': [round(c, 2) for c in coords],
            'description': description,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"   Recorded - Angles: {[round(a, 2) for a in angles]}")
        print(f"   Recorded - Coords: {[round(c, 2) for c in coords]}")
        return True
    else:
        print(f"   Failed to record {position_name}")
        retry = input("   Try again? (y/n): ").lower().strip()
        if retry == 'y':
            return record_position(position_name, description)
        return False

# Step 1: Start with zero position
print("\n" + "="*50)
print("STEP 1: ZERO/HOME POSITION")
print("="*50)

zero_angles, zero_coords = reset_to_zero()
positions['home_position'] = {
    'angles': [round(a, 2) for a in zero_angles],
    'coordinates': [round(c, 2) for c in zero_coords],
    'description': 'Starting home position (all joints at 0°)',
    'timestamp': datetime.now().isoformat()
}

# Step 2: Above vial position
print("\n" + "="*50)
print("STEP 2: ABOVE VIAL POSITION")
print("="*50)

success = record_position('above_vial', 
    "Position robot ABOVE the vial on surface (safe height ~50mm above vial)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 3: Grab vial position
print("\n" + "="*50)
print("STEP 3: GRAB VIAL POSITION")
print("="*50)

success = record_position('grab_vial', 
    "Position gripper AT SURFACE LEVEL to grab the vial (gripper open)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 4: Lift vial position
print("\n" + "="*50)
print("STEP 4: LIFT VIAL POSITION")
print("="*50)

success = record_position('lift_vial', 
    "Lift vial UP from surface (safe height after grabbing)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 5: Above balance position
print("\n" + "="*50)
print("STEP 5: ABOVE BALANCE POSITION")
print("="*50)

success = record_position('above_balance', 
    "Position robot ABOVE the balance (safe approach height)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 6: Place on balance position
print("\n" + "="*50)
print("STEP 6: PLACE ON BALANCE POSITION")
print("="*50)

success = record_position('place_balance', 
    "Position to PLACE vial ON the balance (gripper touching balance surface)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 7: Retreat from balance
print("\n" + "="*50)
print("STEP 7: RETREAT FROM BALANCE")
print("="*50)

success = record_position('retreat_balance', 
    "Move UP/BACK from balance after releasing vial (safe retreat position)")
if not success:
    print("Skipping this position - continuing with calibration")

# Step 8: Final verification - return to zero
print("\n" + "="*50)
print("STEP 8: RETURN TO HOME VERIFICATION")
print("="*50)

print("Returning robot to home position for verification...")
final_angles, final_coords = reset_to_zero()

# Display complete summary
print("\n" + "="*80)
print("                           CALIBRATION COMPLETE!")
print("="*80)

print("\nCOLLECTED POSITIONS SUMMARY:")
print("-" * 80)

if positions:
    for i, (pos_name, pos_data) in enumerate(positions.items(), 1):
        print(f"\n{i}. {pos_name.upper().replace('_', ' ')}:")
        print(f"   Description: {pos_data['description']}")
        print(f"   Angles: {pos_data['angles']}")
        print(f"   Coords: {pos_data['coordinates']}")
else:
    print("No positions were successfully recorded!")

# Generate movement sequence code if we have positions
if positions:
    print(f"\nGENERATED MOVEMENT SEQUENCE:")
    print("-" * 80)
    print("# Copy this code for your vial transfer automation:")
    print("""
from pymycobot import MyCobot280
import time

def control_gripper(mc, state, speed=40, delay=2):
    \"\"\"Control gripper - 0=open, 1=close\"\"\"
    action = "Closing" if state else "Opening"
    print(f"{action} gripper...")
    mc.set_gripper_state(state, speed)
    time.sleep(delay)

def vial_transfer_sequence():
    \"\"\"Complete vial transfer sequence using collected positions\"\"\"
    mc = MyCobot280("COM4", 115200)
    mc.power_on()
    time.sleep(2)
    
    # Movement speed (adjust as needed)
    speed = 25
    
    print("Starting vial transfer sequence...")""")
    
    # Generate position moves
    for pos_name, pos_data in positions.items():
        step_name = pos_name.replace('_', ' ').title()
        print(f"""
    # {step_name}
    print("Moving to {step_name}...")
    mc.send_angles({pos_data['angles']}, speed)
    time.sleep(3)""")
    
    print("""
    print("Vial transfer sequence completed!")

# Run the sequence
vial_transfer_sequence()
""")

# Save data to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"vial_transfer_positions.json"

try:
    with open(filename, 'w') as f:
        json.dump({
            'calibration_info': {
                'robot_model': 'MyCobot 280',
                'calibration_date': datetime.now().isoformat(),
                'total_positions': len(positions)
            },
            'positions': positions
        }, f, indent=2)
    print(f"\nPosition data saved to: {filename}")
except Exception as e:
    print(f"\nFailed to save file: {e}")

print(f"\nCalibration completed!")
print(f"Total positions recorded: {len(positions)}")
print(f"Robot returned to home position")
print("="*80)
