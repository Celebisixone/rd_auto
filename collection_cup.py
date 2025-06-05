# collection_cup.py
from pymycobot import MyCobot280
import time
import json
import os
from datetime import datetime

# ——— CONFIGURATION ———
PORT        = "COM4"      # Change as needed (e.g., "/dev/ttyUSB0")
BAUDRATE    = 115200       # Baud rate for MyCobot280
TOTAL_CUPS  = 2            # Total number of cups (manual positioning)
OUTPUT_DIR  = "."          # Directory to save JSON
PREFIX      = "cup_collection_positions"

# ——— MOTION PARAMETERS ———
MOVE_SPEED  = 25            # Speed for movements

# ——— CONNECT TO ROBOT ———
print("="*60)
print("   MYCOBOT 280 CUP COLLECTION SCRIPT - MANUAL 12 CUPS")
print("="*60)
print("Connecting to MyCobot280...")
try:
    mc = MyCobot280(PORT, BAUDRATE)
    mc.power_on()
    time.sleep(3)
    print("Robot connected successfully")
    
    # Test connection
    try:
        if mc.is_controller_connected():
            print("Robot controller responding")
        else:
            print("Warning: Controller did not respond; proceeding anyway")
    except Exception as e:
        print(f"Warning: Unable to verify controller ({e}); proceeding anyway")
        
except Exception as e:
    print(f"Failed to connect to robot: {e}")
    print("Please check:")
    print("- COM port is correct")
    print("- Robot is powered on")
    print("- USB cable is connected")
    exit(1)

# Store all recorded positions
all_positions = {}

# ——— UTILITIES ———
def ensure_servos_released():
    """Ensure servos are released for manual movement."""
    try:
        print("   >> Ensuring servos are released...")
        mc.release_all_servos()
        time.sleep(0.5)
        print("   >> Servos released - robot can be moved manually")
    except Exception as e:
        print(f"   Warning: Could not release servos: {e}")

def get_angles_safe(retries=5, delay=1.0):
    """Read joint angles reliably with better error handling."""
    for attempt in range(retries):
        try:
            angles = mc.get_angles()
            if isinstance(angles, list) and len(angles) == 6:
                # Check if angles are valid
                if all(isinstance(a, (int, float)) for a in angles):
                    return [round(a, 2) for a in angles]
            elif angles == -1:
                print(f"   Attempt {attempt + 1}: Servos not responding (got -1)")
            elif angles is not None:
                print(f"   Attempt {attempt + 1}: Invalid angles format: {angles}")
            
            if attempt < retries - 1:
                print(f"   Retrying in {delay} seconds...")
                time.sleep(delay)
        except Exception as e:
            print(f"   Attempt {attempt + 1}: Error reading angles: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    
    print("   Failed to read valid joint angles after all attempts")
    return None

def get_coords_safe(retries=3, delay=0.5):
    """Try to read coordinates, return None if unreliable."""
    for attempt in range(retries):
        try:
            coords = mc.get_coords()
            if isinstance(coords, list) and len(coords) == 6:
                return [round(c, 2) for c in coords]
            elif coords == -1:
                return None
            time.sleep(delay)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
    return None

def record_pose(name, description, max_attempts=3):
    """Record a named pose with proper servo handling."""
    for attempt in range(max_attempts):
        print(f"\n{'='*60}")
        if attempt == 0:
            print(f"Recording '{name.upper()}'")
        else:
            print(f"Recording '{name.upper()}' - Attempt {attempt + 1}/{max_attempts}")
        print(f"{'='*60}")
        print(description)
        
        # ALWAYS start with servos released for manual positioning
        ensure_servos_released()
        
        if attempt == 0:
            input("\n   Move the robot to this pose, then press Enter to record...")
        else:
            print(f"\n   Previous attempt failed. Please try a different position.")
            input("   Adjust the robot position, then press Enter to record...")
        
        # Try to enable servos and read position
        print("   >> Attempting to read position...")
        success = False
        
        try:
            # Re-enable servos
            mc.power_on()
            time.sleep(2)  # Wait for servos to engage
            
            # Try to read angles
            angles = get_angles_safe(retries=5, delay=1.0)
            
            if angles is not None:
                # Success! Record the position
                coords = get_coords_safe()
                if coords is None:
                    coords = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    coord_mode = 'dummy'
                else:
                    coord_mode = 'actual'
                
                print(f"\n   Successfully recorded {name}!")
                print(f"      Angles: {angles}")
                if coord_mode == 'actual':
                    print(f"      Coords: {coords}")
                else:
                    print(f"      Coords: dummy (angles-only mode)")
                
                # IMPORTANT: Release servos after successful recording
                ensure_servos_released()
                
                return {
                    'angles': angles,
                    'coordinates': coords,
                    'coord_mode': coord_mode,
                    'description': description,
                    'timestamp': datetime.now().isoformat(),
                    'attempt_number': attempt + 1
                }
            else:
                print(f"\n   Failed to read angles for {name}")
                
        except Exception as e:
            print(f"\n   Error during recording: {e}")
        
        # CRITICAL: Always release servos after each attempt (success or failure)
        ensure_servos_released()
        
        # Handle failed attempt
        if attempt < max_attempts - 1:
            print(f"\n   Recording failed. {max_attempts - attempt - 1} attempts remaining.")
            
            while True:
                choice = input("   Choose: (R)etry, (S)kip this position, or (Q)uit script? [R/S/Q]: ").upper().strip()
                if choice in ['R', 'RETRY', '']:
                    break  # Continue to next attempt
                elif choice in ['S', 'SKIP']:
                    print(f"   Skipping {name}")
                    return None
                elif choice in ['Q', 'QUIT']:
                    print("   Exiting script as requested")
                    exit(0)
                else:
                    print("   Please enter R for retry, S for skip, or Q for quit")
        else:
            # Last attempt failed
            print(f"\n   All {max_attempts} attempts failed for {name}")
            
            while True:
                choice = input("   Choose: (T)ry more, (S)kip this position, or (Q)uit script? [T/S/Q]: ").upper().strip()
                if choice in ['T', 'TRY', 'TRYAGAIN']:
                    print("   Continuing with additional attempts...")
                    return record_pose(name, description, max_attempts=5)  # More attempts
                elif choice in ['S', 'SKIP']:
                    print(f"   Skipping {name}")
                    return None
                elif choice in ['Q', 'QUIT']:
                    print("   Exiting script as requested")
                    exit(0)
                else:
                    print("   Please enter T to try again, S to skip, or Q to quit")
    
    # Should not reach here, but just in case
    return None

# ——— MAIN COLLECTION PROCESS ———
print(f"\nManual Cup Collection Process:")
print(f"- Total cups: {TOTAL_CUPS}")
print(f"- Manual positioning: You will position each cup manually")
print(f"- Balance: Where cups are placed for weighing/measurement")
print(f"- Will record: 3 balance positions + {TOTAL_CUPS * 3} cup positions")
print(f"- Total positions to record: {3 + TOTAL_CUPS * 3} positions")
print(f"- Three-level approach: Safe Height → Right Above → Place Position")
print(f"- Servos will be released after each recording for easy manual movement")

print(f"\n{'='*60}")
print("STEP 1: RECORDING BALANCE POSITIONS")
print(f"{'='*60}")

# Start with servos released
ensure_servos_released()

# Record balance safe height first
balance_safe_data = record_pose(
    'balance_safe_height',
    'Move the robot to a SAFE HEIGHT above the balance.\n'
    'This should be high enough to clear the balance and any cups on it.\n'
    'Used for safe approach and departure from the balance during operations.\n'
    'This is the highest level for balance operations.',
    max_attempts=3
)

if balance_safe_data:
    all_positions['balance_safe_height'] = balance_safe_data
    print("Balance safe height recorded successfully!")
else:
    print("Warning: Balance safe height was not recorded!")

# Record balance right above position
balance_above_data = record_pose(
    'balance_right_above',
    'Move the robot to RIGHT ABOVE the balance.\n'
    'This should be directly above the balance, lower than safe height.\n'
    'Used for precise positioning before final placement/pickup.\n'
    'This is the intermediate level for balance operations.',
    max_attempts=3
)

if balance_above_data:
    all_positions['balance_right_above'] = balance_above_data
    print("Balance right above position recorded successfully!")
else:
    print("Warning: Balance right above position was not recorded!")

# Record balance position
balance_data = record_pose(
    'balance_position',
    'Move the robot to the BALANCE location where cups will be placed for measurement.\n'
    'Position the gripper where it can place and retrieve cups on the balance.\n'
    'This is the weighing/measurement station where each cup will be processed.\n'
    'This is the lowest level - actual contact with balance.',
    max_attempts=3
)

if balance_data:
    all_positions['balance_position'] = balance_data
    print("Balance position recorded successfully!")
else:
    print("Warning: Balance position was not recorded!")
    while True:
        choice = input("   Continue without balance position? This will limit functionality [Y/N]: ").upper().strip()
        if choice in ['Y', 'YES']:
            print("Continuing without balance position...")
            break
        elif choice in ['N', 'NO']:
            print("Please record the balance position to continue.")
            balance_data = record_pose(
                'balance_position',
                'Move the robot to the BALANCE location for cup measurement.',
                max_attempts=5
            )
            if balance_data:
                all_positions['balance_position'] = balance_data
                print("Balance position recorded successfully!")
                break
        else:
            print("   Please enter Y for yes or N for no")

print(f"\n{'='*60}")
print("STEP 2: RECORDING CUP POSITIONS")
print(f"{'='*60}")

# Collect positions for each cup
for cup_idx in range(1, TOTAL_CUPS + 1):
    print(f"\n{'='*80}")
    print(f"CUP #{cup_idx} POSITIONS")
    print(f"{'='*80}")
    
    # Record safe height position
    safe_height_key = f'cup_{cup_idx}_safe_height'
    safe_height_data = record_pose(
        safe_height_key,
        f"Position the robot at SAFE HEIGHT above Cup #{cup_idx}.\n"
        f"This should be high enough to clear the cup and allow safe movement.\n"
        f"The robot should be positioned above the cup area but at maximum safe distance.\n"
        f"This is the highest level for Cup #{cup_idx} operations.",
        max_attempts=3
    )
    
    if safe_height_data:
        all_positions[safe_height_key] = safe_height_data
        print(f"\nSafe height position for Cup {cup_idx} recorded successfully!")
    else:
        print(f"\nSafe height position for Cup {cup_idx} was skipped")
    
    # Record right above position
    right_above_key = f'cup_{cup_idx}_right_above'
    right_above_data = record_pose(
        right_above_key,
        f"Position the robot RIGHT ABOVE Cup #{cup_idx}.\n"
        f"This should be directly above the cup, lower than safe height.\n"
        f"Used for precise positioning before entering the cup.\n"
        f"The gripper should be aligned with the cup opening.\n"
        f"This is the intermediate level for Cup #{cup_idx} operations.",
        max_attempts=3
    )
    
    if right_above_data:
        all_positions[right_above_key] = right_above_data
        print(f"\nRight above position for Cup {cup_idx} recorded successfully!")
    else:
        print(f"\nRight above position for Cup {cup_idx} was skipped")
        
        # Ask if user wants to continue without this position
        while True:
            choice = input(f"   Continue to inside position for Cup {cup_idx}? [Y/N]: ").upper().strip()
            if choice in ['Y', 'YES', '']:
                break
            elif choice in ['N', 'NO']:
                print(f"Skipping Cup {cup_idx} entirely")
                continue  # Skip to next cup
            else:
                print("   Please enter Y for yes or N for no")
    
    # Record inside cup position
    cup_inside_key = f'cup_{cup_idx}_inside'
    cup_inside_data = record_pose(
        cup_inside_key,
        f"Position the gripper INSIDE Cup #{cup_idx}.\n"
        f"The gripper should be positioned ready to close around the cup for gripping.\n"
        f"Lower the robot so the gripper is inside the cup at the proper depth.\n"
        f"This is the lowest level - actual contact with Cup #{cup_idx}.",
        max_attempts=3
    )
    
    if cup_inside_data:
        all_positions[cup_inside_key] = cup_inside_data
        print(f"\nInside position for Cup {cup_idx} recorded successfully!")
    else:
        print(f"\nInside position for Cup {cup_idx} was skipped")
    
    # Summary for this cup
    safe_recorded = safe_height_key in all_positions
    above_recorded = right_above_key in all_positions
    inside_recorded = cup_inside_key in all_positions
    
    recorded_positions = []
    if safe_recorded:
        recorded_positions.append("safe height")
    if above_recorded:
        recorded_positions.append("right above")
    if inside_recorded:
        recorded_positions.append("inside")
    
    if len(recorded_positions) == 3:
        print(f"\nCup #{cup_idx} - All three positions recorded successfully!")
    elif len(recorded_positions) > 0:
        print(f"\nCup #{cup_idx} - Partial success (recorded: {', '.join(recorded_positions)})")
    else:
        print(f"\nCup #{cup_idx} - No positions recorded")
    
    # Brief pause and servo check between cups
    if cup_idx < TOTAL_CUPS:
        print(f"\nPreparing for Cup #{cup_idx + 1}...")
        ensure_servos_released()  # Make sure servos are released for next cup
        time.sleep(1)

# ——— FINAL SERVO RELEASE ———
print(f"\n{'='*60}")
print("COLLECTION COMPLETED - RELEASING SERVOS")
print(f"{'='*60}")
ensure_servos_released()

# ——— SUMMARY ———
print(f"\n{'='*80}")
print("                    COLLECTION COMPLETE!")
print(f"{'='*80}")

successful_positions = len([p for p in all_positions.values() if p is not None])
expected_positions = 3 + (TOTAL_CUPS * 3)  # 3 balance positions + 3 positions per cup

print(f"\nCollection Summary:")
print(f"- Successfully recorded: {successful_positions} positions")
print(f"- Expected total: {expected_positions} positions")
print(f"- Success rate: {successful_positions/expected_positions*100:.1f}%")
print(f"- Processed {TOTAL_CUPS} cups")

if successful_positions < expected_positions:
    print(f"Warning: Some positions were not recorded successfully")

# ——— SAVE TO JSON ———
if all_positions:
    data = {
        'calibration_info': {
            'robot_model': 'MyCobot 280',
            'collection_date': datetime.now().isoformat(),
            'collection_method': 'manual_positioning_12_cups_three_level',
            'coordinate_mode': 'angles_primary',
            'layout': {
                'type': 'manual',
                'total_cups': TOTAL_CUPS,
                'description': 'Manually positioned cups with three-level approach',
                'levels': ['safe_height', 'right_above', 'inside']
            },
            'positions_recorded': successful_positions,
            'position_types': ['safe_height', 'right_above', 'inside'],
            'gripper_mode': 'expandable_recommended'
        },
        'positions': all_positions
    }

    filename = os.path.join(
        OUTPUT_DIR,
        f"{PREFIX}.json"
    )
    
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nAll positions saved to: {filename}")
        
        # Display summary of positions
        print(f"\nSaved positions summary:")
        
        # Balance positions
        balance_safe_status = "OK" if 'balance_safe_height' in all_positions else "FAILED"
        balance_above_status = "OK" if 'balance_right_above' in all_positions else "FAILED"
        balance_status = "OK" if 'balance_position' in all_positions else "FAILED"
        print(f"  Balance safe height: {balance_safe_status}")
        print(f"  Balance right above: {balance_above_status}")
        print(f"  Balance position: {balance_status}")
        print()
        
        # Cup positions
        for cup_idx in range(1, TOTAL_CUPS + 1):
            safe_key = f'cup_{cup_idx}_safe_height'
            above_key = f'cup_{cup_idx}_right_above'
            inside_key = f'cup_{cup_idx}_inside'
            
            safe_status = "OK" if safe_key in all_positions else "FAILED"
            above_status = "OK" if above_key in all_positions else "FAILED"
            inside_status = "OK" if inside_key in all_positions else "FAILED"
            
            print(f"  Cup {cup_idx:2d}: Safe={safe_status}, Above={above_status}, Inside={inside_status}")
                
    except Exception as e:
        print(f"\nFailed to save JSON file: {e}")
        
else:
    print(f"\nNo positions were successfully recorded!")

print(f"\n{'='*80}")
print("Manual collection script completed!")
print("Servos are released - robot can be moved freely.")
print("Use the generated JSON file for automated cup operations.")
print(f"{'='*80}")