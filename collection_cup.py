# collection_20_containers_shared_safe.py
from pymycobot import MyCobot280
import time
import json
import os
from datetime import datetime

# ——— CONFIGURATION ———
PORT        = "COM4"      # Change as needed
BAUDRATE    = 115200      # Baud rate for MyCobot280
TOTAL_CONTAINERS = 6     # Total number of containers
OUTPUT_DIR  = "."         # Directory to save JSON
PREFIX      = "cup_collection_positions"

# ——— CONNECT TO ROBOT ———
print("="*70)
print("   MYCOBOT 280 - 20 CONTAINER COLLECTION (SHARED SAFE HEIGHT)")
print("="*70)
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
        print(f"\n{'='*70}")
        if attempt == 0:
            print(f"Recording '{name.upper()}'")
        else:
            print(f"Recording '{name.upper()}' - Attempt {attempt + 1}/{max_attempts}")
        print(f"{'='*70}")
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
    
    return None

# ——— MAIN COLLECTION PROCESS ———
print(f"\n20-Container Collection Process with SHARED SAFE HEIGHT:")
print(f"- Total containers: {TOTAL_CONTAINERS}")
print(f"- Positions to record: 1 shared safe height + {TOTAL_CONTAINERS} pickup positions + 1 balance")
print(f"- Total positions to record: {TOTAL_CONTAINERS + 2}")
print(f"- Much more efficient than individual safe heights!")
print(f"- Intelligent Power Management will handle all routing automatically")

print(f"\n{'='*70}")
print("STEP 1: RECORDING SHARED SAFE HEIGHT")
print(f"{'='*70}")

# Start with servos released
ensure_servos_released()

# Record shared safe height position
shared_safe_data = record_pose(
    'shared_safe_height',
    'Move the robot to a SHARED SAFE HEIGHT position.\n'
    'This position should be:\n'
    '- High enough to clear ALL containers in your workspace\n'
    '- Positioned centrally to minimize travel time\n'
    '- A "parking" position for safe movement between containers\n'
    '- Clear of any obstacles or collision hazards\n'
    'This single position will be used for safe transitions between all containers.',
    max_attempts=3
)

if shared_safe_data:
    all_positions['shared_safe_height'] = shared_safe_data
    print("Shared safe height recorded successfully!")
else:
    print("ERROR: Shared safe height is REQUIRED for safe operation!")
    while True:
        choice = input("   Record shared safe height? (Y/N): ").upper().strip()
        if choice in ['Y', 'YES']:
            shared_safe_data = record_pose(
                'shared_safe_height',
                'Move to a safe height position that clears all containers.',
                max_attempts=5
            )
            if shared_safe_data:
                all_positions['shared_safe_height'] = shared_safe_data
                print("Shared safe height recorded successfully!")
                break
        elif choice in ['N', 'NO']:
            print("Cannot proceed without shared safe height. Exiting.")
            exit(1)

print(f"\n{'='*70}")
print("STEP 2: RECORDING BALANCE POSITION")
print(f"{'='*70}")

# Record balance position
balance_data = record_pose(
    'balance_position',
    'Move the robot to the BALANCE location where containers will be placed for measurement.\n'
    'Position the gripper where it can place and retrieve containers on the balance.\n'
    'This is the weighing/measurement station where each container will be processed.',
    max_attempts=3
)

if balance_data:
    all_positions['balance_position'] = balance_data
    print("Balance position recorded successfully!")
else:
    print("WARNING: Balance position was not recorded!")
    while True:
        choice = input("   Continue without balance position? This will limit functionality [Y/N]: ").upper().strip()
        if choice in ['Y', 'YES']:
            print("Continuing without balance position...")
            break
        elif choice in ['N', 'NO']:
            print("Please record the balance position to continue.")
            balance_data = record_pose(
                'balance_position',
                'Move the robot to the BALANCE location for container measurement.',
                max_attempts=5
            )
            if balance_data:
                all_positions['balance_position'] = balance_data
                print("Balance position recorded successfully!")
                break
        else:
            print("   Please enter Y for yes or N for no")

print(f"\n{'='*70}")
print("STEP 3: RECORDING CONTAINER PICKUP POSITIONS")
print(f"{'='*70}")
print("For each container, you will record ONLY the pickup position.")
print("The shared safe height will be used for all collision avoidance.")
print("The Intelligent Power Management will automatically:")
print("- Route via shared_safe_height between containers")
print("- Calculate optimal movement paths")
print("- Manage power consumption during transitions")

print(f"\n{'='*70}")
print("STEP 2B: RECORDING BALANCE SAFE HEIGHT")
print(f"{'='*70}")

# Record balance safe height position
balance_safe_data = record_pose(
    'balance_safe_height',
    'Move the robot to a SAFE HEIGHT above the balance.\n'
    'This should be high enough to clear the balance and any containers on it.\n'
    'Used for safe approach and departure from the balance during operations.\n'
    'This is a safe intermediate position above the balance.',
    max_attempts=3
)

if balance_safe_data:
    all_positions['balance_safe_height'] = balance_safe_data
    print("Balance safe height recorded successfully!")
else:
    print("Warning: Balance safe height was not recorded!")

# Collect pickup positions for each container
for container_idx in range(1, TOTAL_CONTAINERS + 1):
    print(f"\n{'='*80}")
    print(f"CONTAINER #{container_idx} PICKUP POSITION ({container_idx}/{TOTAL_CONTAINERS})")
    print(f"{'='*80}")
    
    # Record pickup position only
    pickup_key = f'container_{container_idx}_pickup'
    pickup_data = record_pose(
        pickup_key,
        f"Position the gripper to PICKUP Container #{container_idx}.\n"
        f"The gripper should be positioned ready to close around the container for gripping.\n"
        f"Position where the robot will actually grab and lift the container.\n"
        f"Ensure the gripper is properly aligned for reliable pickup.\n"
        f"NOTE: The robot will approach this position via the shared safe height.",
        max_attempts=3
    )
    
    if pickup_data:
        all_positions[pickup_key] = pickup_data
        print(f"\nPickup position for Container {container_idx} recorded successfully!")
    else:
        print(f"\nPickup position for Container {container_idx} was skipped")
        
        # Ask if user wants to continue
        while True:
            choice = input(f"   Continue to next container? [Y/N]: ").upper().strip()
            if choice in ['Y', 'YES', '']:
                break
            elif choice in ['N', 'NO']:
                print("Stopping collection process.")
                break
            else:
                print("   Please enter Y for yes or N for no")
        
        if choice in ['N', 'NO']:
            break
    
    # Progress indicator
    remaining = TOTAL_CONTAINERS - container_idx
    if remaining > 0:
        print(f"\n--- PROGRESS: {container_idx}/{TOTAL_CONTAINERS} completed, {remaining} containers remaining ---")
        
        # Brief pause and servo check between containers
        print(f"Preparing for Container #{container_idx + 1}...")
        ensure_servos_released()  # Make sure servos are released for next container
        time.sleep(1)

# ——— FINAL SERVO RELEASE ———
print(f"\n{'='*70}")
print("COLLECTION COMPLETED - RELEASING SERVOS")
print(f"{'='*70}")
ensure_servos_released()

# ——— SUMMARY ———
print(f"\n{'='*80}")
print("    20-CONTAINER COLLECTION COMPLETE (SHARED SAFE HEIGHT)")
print(f"{'='*80}")

successful_positions = len([p for p in all_positions.values() if p is not None])
expected_positions = TOTAL_CONTAINERS + 3  # containers + shared_safe + balance

print(f"\nCollection Summary:")
print(f"- Successfully recorded: {successful_positions} positions")
print(f"- Expected total: {expected_positions} positions")
print(f"- Success rate: {successful_positions/expected_positions*100:.1f}%")
print(f"- Processed {TOTAL_CONTAINERS} containers")

if successful_positions < expected_positions:
    print(f"Warning: Some positions were not recorded successfully")

# Count complete containers
complete_containers = 0
for container_idx in range(1, TOTAL_CONTAINERS + 1):
    pickup_key = f'container_{container_idx}_pickup'
    if pickup_key in all_positions:
        complete_containers += 1

print(f"- Complete containers (pickup positions): {complete_containers}/{TOTAL_CONTAINERS}")
print(f"- Shared safe height: {'OK' if 'shared_safe_height' in all_positions else 'MISSING'}")
print(f"- Balance position: {'OK' if 'balance_position' in all_positions else 'MISSING'}")

# ——— SAVE TO JSON ———
if all_positions:
    data = {
        'calibration_info': {
            'robot_model': 'MyCobot 280',
            'collection_date': datetime.now().isoformat(),
            'collection_method': 'manual_positioning_20_containers_shared_safe',
            'coordinate_mode': 'angles_primary',
            'layout': {
                'type': 'shared_safe_height_layout',
                'total_containers': TOTAL_CONTAINERS,
                'description': 'Manually positioned 20 containers with shared safe height for efficient routing',
                'position_types': ['shared_safe_height', 'pickup', 'balance'],
                'shared_safe_height': True
            },
            'positions_recorded': successful_positions,
            'intelligent_power_management': True,
            'power_management_info': {
                'description': 'Optimized for intelligent power management with shared safe height',
                'routing': 'All movements route via shared_safe_height for collision avoidance',
                'power_optimization': 'Sequential and gradual movement support',
                'efficiency': 'Reduced position count from shared safe height approach'
            }
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
        
        # Shared positions
        shared_safe_status = "OK" if 'shared_safe_height' in all_positions else "FAILED"
        balance_status = "OK" if 'balance_position' in all_positions else "FAILED"
        print(f"  Shared safe height: {shared_safe_status}")
        print(f"  Balance position: {balance_status}")
        print()
        
        # Container positions
        print("  Container pickup positions:")
        for container_idx in range(1, TOTAL_CONTAINERS + 1):
            pickup_key = f'container_{container_idx}_pickup'
            pickup_status = "OK" if pickup_key in all_positions else "FAILED"
            print(f"    Container {container_idx:2d}: {pickup_status}")
                
    except Exception as e:
        print(f"\nFailed to save JSON file: {e}")
        
else:
    print(f"\nNo positions were successfully recorded!")

print(f"\n{'='*80}")
print("READY FOR INTELLIGENT POWER MANAGEMENT!")
print(f"{'='*80}")
print("Optimized routing pattern:")
print("1. Home → Shared_Safe_Height")
print("2. Shared_Safe_Height → Container_X_Pickup")
print("3. Container_X_Pickup → Shared_Safe_Height") 
print("4. Shared_Safe_Height → Balance_Position")
print("5. Balance_Position → Shared_Safe_Height")
print("6. Shared_Safe_Height → Container_X_Pickup (return)")
print("7. Container_X_Pickup → Shared_Safe_Height")
print("8. Ready for next container")
print()
print("Benefits of shared safe height:")
print("✅ Only need to record 22 positions instead of 41")
print("✅ Consistent collision avoidance for all containers")
print("✅ Simplified path planning")
print("✅ Faster setup and calibration")
print("✅ Intelligent Power Management handles all routing")
print(f"{'='*80}")
print("Manual collection script completed!")
print("Servos are released - robot can be moved freely.")
print(f"{'='*80}")# collection_20_containers_shared_safe.py
from pymycobot import MyCobot280
import time
import json
import os
from datetime import datetime

# ——— CONFIGURATION ———
PORT        = "COM4"      # Change as needed
BAUDRATE    = 115200      # Baud rate for MyCobot280
TOTAL_CONTAINERS = 20     # Total number of containers
OUTPUT_DIR  = "."         # Directory to save JSON
PREFIX      = "container_20_positions_shared_safe"

# ——— CONNECT TO ROBOT ———
print("="*70)
print("   MYCOBOT 280 - 20 CONTAINER COLLECTION (SHARED SAFE HEIGHT)")
print("="*70)
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
        print(f"\n{'='*70}")
        if attempt == 0:
            print(f"Recording '{name.upper()}'")
        else:
            print(f"Recording '{name.upper()}' - Attempt {attempt + 1}/{max_attempts}")
        print(f"{'='*70}")
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
    
    return None

# ——— MAIN COLLECTION PROCESS ———
print(f"\n20-Container Collection Process with SHARED SAFE HEIGHT:")
print(f"- Total containers: {TOTAL_CONTAINERS}")
print(f"- Positions to record: 1 shared safe height + {TOTAL_CONTAINERS} pickup positions + 2 balance")
print(f"- Total positions to record: {TOTAL_CONTAINERS + 2}")
print(f"- Much more efficient than individual safe heights!")
print(f"- Intelligent Power Management will handle all routing automatically")

print(f"\n{'='*70}")
print("STEP 1: RECORDING SHARED SAFE HEIGHT")
print(f"{'='*70}")

# Start with servos released
ensure_servos_released()

# Record shared safe height position
shared_safe_data = record_pose(
    'shared_safe_height',
    'Move the robot to a SHARED SAFE HEIGHT position.\n'
    'This position should be:\n'
    '- High enough to clear ALL containers in your workspace\n'
    '- Positioned centrally to minimize travel time\n'
    '- A "parking" position for safe movement between containers\n'
    '- Clear of any obstacles or collision hazards\n'
    'This single position will be used for safe transitions between all containers.',
    max_attempts=3
)

if shared_safe_data:
    all_positions['shared_safe_height'] = shared_safe_data
    print("Shared safe height recorded successfully!")
else:
    print("ERROR: Shared safe height is REQUIRED for safe operation!")
    while True:
        choice = input("   Record shared safe height? (Y/N): ").upper().strip()
        if choice in ['Y', 'YES']:
            shared_safe_data = record_pose(
                'shared_safe_height',
                'Move to a safe height position that clears all containers.',
                max_attempts=5
            )
            if shared_safe_data:
                all_positions['shared_safe_height'] = shared_safe_data
                print("Shared safe height recorded successfully!")
                break
        elif choice in ['N', 'NO']:
            print("Cannot proceed without shared safe height. Exiting.")
            exit(1)

print(f"\n{'='*70}")
print("STEP 2: RECORDING BALANCE POSITION")
print(f"{'='*70}")

# Record balance position
balance_data = record_pose(
    'balance_position',
    'Move the robot to the BALANCE location where containers will be placed for measurement.\n'
    'Position the gripper where it can place and retrieve containers on the balance.\n'
    'This is the weighing/measurement station where each container will be processed.',
    max_attempts=3
)

if balance_data:
    all_positions['balance_position'] = balance_data
    print("Balance position recorded successfully!")
else:
    print("WARNING: Balance position was not recorded!")
    while True:
        choice = input("   Continue without balance position? This will limit functionality [Y/N]: ").upper().strip()
        if choice in ['Y', 'YES']:
            print("Continuing without balance position...")
            break
        elif choice in ['N', 'NO']:
            print("Please record the balance position to continue.")
            balance_data = record_pose(
                'balance_position',
                'Move the robot to the BALANCE location for container measurement.',
                max_attempts=5
            )
            if balance_data:
                all_positions['balance_position'] = balance_data
                print("Balance position recorded successfully!")
                break
        else:
            print("   Please enter Y for yes or N for no")

print(f"\n{'='*70}")
print("STEP 3: RECORDING CONTAINER PICKUP POSITIONS")
print(f"{'='*70}")
print("For each container, you will record ONLY the pickup position.")
print("The shared safe height will be used for all collision avoidance.")
print("The Intelligent Power Management will automatically:")
print("- Route via shared_safe_height between containers")
print("- Calculate optimal movement paths")
print("- Manage power consumption during transitions")

# Collect pickup positions for each container
for container_idx in range(1, TOTAL_CONTAINERS + 1):
    print(f"\n{'='*80}")
    print(f"CONTAINER #{container_idx} PICKUP POSITION ({container_idx}/{TOTAL_CONTAINERS})")
    print(f"{'='*80}")
    
    # Record pickup position only
    pickup_key = f'container_{container_idx}_pickup'
    pickup_data = record_pose(
        pickup_key,
        f"Position the gripper to PICKUP Container #{container_idx}.\n"
        f"The gripper should be positioned ready to close around the container for gripping.\n"
        f"Position where the robot will actually grab and lift the container.\n"
        f"Ensure the gripper is properly aligned for reliable pickup.\n"
        f"NOTE: The robot will approach this position via the shared safe height.",
        max_attempts=3
    )
    
    if pickup_data:
        all_positions[pickup_key] = pickup_data
        print(f"\nPickup position for Container {container_idx} recorded successfully!")
    else:
        print(f"\nPickup position for Container {container_idx} was skipped")
        
        # Ask if user wants to continue
        while True:
            choice = input(f"   Continue to next container? [Y/N]: ").upper().strip()
            if choice in ['Y', 'YES', '']:
                break
            elif choice in ['N', 'NO']:
                print("Stopping collection process.")
                break
            else:
                print("   Please enter Y for yes or N for no")
        
        if choice in ['N', 'NO']:
            break
    
    # Progress indicator
    remaining = TOTAL_CONTAINERS - container_idx
    if remaining > 0:
        print(f"\n--- PROGRESS: {container_idx}/{TOTAL_CONTAINERS} completed, {remaining} containers remaining ---")
        
        # Brief pause and servo check between containers
        print(f"Preparing for Container #{container_idx + 1}...")
        ensure_servos_released()  # Make sure servos are released for next container
        time.sleep(1)

# ——— FINAL SERVO RELEASE ———
print(f"\n{'='*70}")
print("COLLECTION COMPLETED - RELEASING SERVOS")
print(f"{'='*70}")
ensure_servos_released()

# ——— SUMMARY ———
print(f"\n{'='*80}")
print("    20-CONTAINER COLLECTION COMPLETE (SHARED SAFE HEIGHT)")
print(f"{'='*80}")

successful_positions = len([p for p in all_positions.values() if p is not None])
expected_positions = TOTAL_CONTAINERS + 2  # containers + shared_safe + balance

print(f"\nCollection Summary:")
print(f"- Successfully recorded: {successful_positions} positions")
print(f"- Expected total: {expected_positions} positions")
print(f"- Success rate: {successful_positions/expected_positions*100:.1f}%")
print(f"- Processed {TOTAL_CONTAINERS} containers")

if successful_positions < expected_positions:
    print(f"Warning: Some positions were not recorded successfully")

# Count complete containers
complete_containers = 0
for container_idx in range(1, TOTAL_CONTAINERS + 1):
    pickup_key = f'container_{container_idx}_pickup'
    if pickup_key in all_positions:
        complete_containers += 1

print(f"- Complete containers (pickup positions): {complete_containers}/{TOTAL_CONTAINERS}")
print(f"- Shared safe height: {'OK' if 'shared_safe_height' in all_positions else 'MISSING'}")
print(f"- Balance position: {'OK' if 'balance_position' in all_positions else 'MISSING'}")

# ——— SAVE TO JSON ———
if all_positions:
    data = {
        'calibration_info': {
            'robot_model': 'MyCobot 280',
            'collection_date': datetime.now().isoformat(),
            'collection_method': 'manual_positioning_20_containers_shared_safe',
            'coordinate_mode': 'angles_primary',
            'layout': {
                'type': 'shared_safe_height_layout',
                'total_containers': TOTAL_CONTAINERS,
                'description': 'Manually positioned 20 containers with shared safe height for efficient routing',
                'position_types': ['shared_safe_height', 'pickup', 'balance'],
                'shared_safe_height': True
            },
            'positions_recorded': successful_positions,
            'intelligent_power_management': True,
            'power_management_info': {
                'description': 'Optimized for intelligent power management with shared safe height',
                'routing': 'All movements route via shared_safe_height for collision avoidance',
                'power_optimization': 'Sequential and gradual movement support',
                'efficiency': 'Reduced position count from shared safe height approach'
            }
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
        
        # Shared positions
        shared_safe_status = "OK" if 'shared_safe_height' in all_positions else "FAILED"
        balance_status = "OK" if 'balance_position' in all_positions else "FAILED"
        print(f"  Shared safe height: {shared_safe_status}")
        print(f"  Balance position: {balance_status}")
        print()
        
        # Container positions
        print("  Container pickup positions:")
        for container_idx in range(1, TOTAL_CONTAINERS + 1):
            pickup_key = f'container_{container_idx}_pickup'
            pickup_status = "OK" if pickup_key in all_positions else "FAILED"
            print(f"    Container {container_idx:2d}: {pickup_status}")
                
    except Exception as e:
        print(f"\nFailed to save JSON file: {e}")
        
else:
    print(f"\nNo positions were successfully recorded!")

print(f"\n{'='*80}")
print("READY FOR INTELLIGENT POWER MANAGEMENT!")
print(f"{'='*80}")
print("Optimized routing pattern:")
print("1. Home → Shared_Safe_Height")
print("2. Shared_Safe_Height → Container_X_Pickup")
print("3. Container_X_Pickup → Shared_Safe_Height") 
print("4. Shared_Safe_Height → Balance_Position")
print("5. Balance_Position → Shared_Safe_Height")
print("6. Shared_Safe_Height → Container_X_Pickup (return)")
print("7. Container_X_Pickup → Shared_Safe_Height")
print("8. Ready for next container")
print()
print("Benefits of shared safe height:")
print("✅ Only need to record 22 positions instead of 41")
print("✅ Consistent collision avoidance for all containers")
print("✅ Simplified path planning")
print("✅ Faster setup and calibration")
print("✅ Intelligent Power Management handles all routing")
print(f"{'='*80}")
print("Manual collection script completed!")
print("Servos are released - robot can be moved freely.")
print(f"{'='*80}")