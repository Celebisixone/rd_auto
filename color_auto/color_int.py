#!/usr/bin/env python3
"""
Integrated Pump Initialization and Volume-Based Concentration Control

This script initializes a Masterflex L/S pump over RS-232 and uses it
to dispense solvent based on sample weight and calibration values.
"""

import serial
import time
import threading
import argparse
import sys
import os
import json

# ===== CONFIGURATION =====
BALANCE_PORT              = 'COM5'
BALANCE_BAUD              = 4800
BALANCE_TIMEOUT           = 2

PUMP_PORT                 = 'COM6'
PUMP_NUMBER               = 1
FLOW_RATE                 = 30.0     # RPM for dispensing
FILL_FLOW_RATE            = 60.0     # RPM for tubing fill
DIRECTION                 = "CCW"    # Direction setting: "CW" or "CCW"

SAMPLE_TO_SOLUTION_RATIO  = 1 / 20.9
DEFAULT_ML_PER_REVOLUTION = 2.7489      # ml/revolution from calibration (updated based on observed behavior)
MAX_PUMPING_TIME          = 60      # seconds
TARE_COMMAND              = b'ST\r\n'
CALIBRATION_FILE          = "pump_calibrations.json"

latest_measurement = None
latest_lock        = threading.Lock()
running            = True


class PumpController:
    """Control the Masterflex pump via RS-232"""

    def __init__(self, port, pump_number=1, ml_per_revolution=DEFAULT_ML_PER_REVOLUTION, verbose=False):
        self.pump_number = f"{pump_number:02d}"
        self.verbose = verbose
        self.ml_per_rev = ml_per_revolution
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=4800,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=2,
                rtscts=False, xonxoff=False, dsrdtr=False
            )
            print(f"Serial port {port} opened")
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            print(f"Error opening pump port: {e}")
            sys.exit(1)

    def send_command(self, cmd, read_response=True):
        """Send command to pump and get response"""
        pkt = b'\x02' + cmd.encode('ascii') + b'\x0D'
        if self.verbose:
            print(f"TX: {pkt!r}")
        self.ser.write(pkt)
        if read_response:
            time.sleep(0.3)
            if self.ser.in_waiting:
                r = self.ser.read(self.ser.in_waiting)
                if self.verbose:
                    print(f"RX: {r!r}")
                return r
            return b''
        return b''

    def assign_number(self):
        """Assign pump satellite number"""
        r = self.send_command(f"P{self.pump_number}")
        return r in (b'\x06', b'')

    def enable_remote(self):
        """Enable remote control mode"""
        return self.send_command(f"P{self.pump_number}R") == b'\x06'

    def enable_local(self):
        """Switch back to local control mode"""
        return self.send_command(f"P{self.pump_number}L") == b'\x06'

    def set_speed(self, rpm, direction=DIRECTION):
        """Set pump speed and direction"""
        sign = "+" if direction == "CW" else "-"
        if rpm < 100:
            cmd = f"P{self.pump_number}S{sign}{rpm:.1f}"
        else:
            cmd = f"P{self.pump_number}S{sign}{rpm:.0f}"
        return self.send_command(cmd) == b'\x06'

    def dispense_volume(self, revolutions):
        """Set pump to dispense a specific volume by revolutions"""
        cmd = f"P{self.pump_number}V{revolutions:.2f}"
        print(f"Setting exact volume: {revolutions:.2f} revolutions (expected to produce {revolutions * self.ml_per_rev:.4f}ml)")
        result = self.send_command(cmd)
        if self.verbose:
            print(f"Set volume to {revolutions:.2f} revolutions, response: {result!r}")
        return result == b'\x06'
       
    def start_pump(self):
        """Start the pump"""
        result = self.send_command(f"P{self.pump_number}G")
        if self.verbose:
            print(f"Start pump, response: {result!r}")
        return result == b'\x06'

    def stop_pump(self):
        """Stop the pump"""
        result = self.send_command(f"P{self.pump_number}H")
        if self.verbose:
            print(f"Stop pump, response: {result!r}")
        return result == b'\x06'
       
    def start_continuous(self):
        """Start pump in continuous mode (for tubing fill)"""
        if self.verbose:
            print("Starting continuous mode:")
       
        self.send_command(f"P{self.pump_number}H", read_response=False)
        time.sleep(0.1)
        self.send_command(f"P{self.pump_number}K{DIRECTION}", read_response=False)
        time.sleep(0.1)
        self.send_command(f"P{self.pump_number}Z")  # Zero revolutions counter
        time.sleep(0.1)
        self.set_speed(FILL_FLOW_RATE, DIRECTION)
        result = self.send_command(f"P{self.pump_number}G0")
        if self.verbose:
            print(f"Start continuous (G0), response: {result!r}")
        return result == b'\x06'
       
    def get_status(self):
        """Get pump status"""
        return self.send_command(f"P{self.pump_number}?")
       
    def get_revs_remaining(self):
        """Get revolutions remaining"""
        return self.send_command(f"P{self.pump_number}Y")

    def initialize_pump(self):
        """Initialize the pump"""
        print("\n====== PUMP INIT ======")
        self.assign_number()
        self.enable_remote()
        self.set_speed(FLOW_RATE, DIRECTION)
        print("Pump initialized")


def balance_reader_thread(ser):
    """Thread to continuously read balance data"""
    global latest_measurement, running
    while running:
        line = ser.readline()
        if not line:
            continue
        txt = line.decode(errors='ignore').strip()
        num = ''.join(c for c in txt if c.isdigit() or c in '.-')
        if num:
            try:
                float(num)
                with latest_lock:
                    latest_measurement = num
            except ValueError:
                pass


def get_weight():
    """Get the latest weight reading from the balance with 4 decimal places precision"""
    with latest_lock:
        try:
            return round(float(latest_measurement or 0.0), 4)
        except ValueError:
            return 0.0000


class CalibrationManager:
    """Load pump calibration profiles"""
   
    def __init__(self, filename=CALIBRATION_FILE):
        self.filename = filename
        self.profiles = self.load_profiles()
   
    def load_profiles(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    profiles = json.load(f)
                    if "profiles" not in profiles:
                        profiles["profiles"] = {}
                    return profiles
            except json.JSONDecodeError:
                print(f"Error: Calibration file corrupt")
                return {"profiles": {}}
        else:
            print(f"No calibration file found")
            return {"profiles": {}}
   
    def get_profile(self, name):
        if "profiles" in self.profiles and name in self.profiles["profiles"]:
            return self.profiles["profiles"][name]
        return None


def initialize_system(args):
    """Initialize the pump and balance systems"""
    print("\n====== SYSTEM INIT ======")
   
    # Initialize pump
    pump = PumpController(args.pump_port, args.pump_number, args.ml_per_rev, args.verbose)
    pump.initialize_pump()
   
    # Initialize balance
    try:
        bal_ser = serial.Serial(
            args.balance_port,
            baudrate=BALANCE_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=BALANCE_TIMEOUT
        )
        print(f"Connected to balance on {args.balance_port}")
    except serial.SerialException as e:
        print(f"Balance port error: {e}")
        pump.ser.close()
        return None, None

    return pump, bal_ser


def run_concentration_control(args):
    """Main function to run the concentration control process"""
    global running
   
    # Initialize
    pump, bal_ser = initialize_system(args)
    if not pump:
        return

    # Start balance reader thread
    threading.Thread(target=balance_reader_thread, args=(bal_ser,), daemon=True).start()

    # Auto-fill tubing if needed
    if not args.skip_fill:
        print(f"\n=== AUTO TUBING FILL ({args.fill_rate} RPM for 30 s) ===")
        if pump.start_continuous():
            print("Auto-fill: Pump running for 30 s...")
            time.sleep(30)
            pump.stop_pump()
            print("Auto-fill complete\n")
        else:
            print("Auto-fill failed\n")
    else:
        print("\nSkipping tubing fill\n")

    # Reset to dispensing speed
    pump.set_speed(args.flow_rate, DIRECTION)

    # Main cycle
    cycle = 1
    try:
        while True:
            print(f"\n=== Cycle {cycle} ({args.ratio*100:.2f}% w/w) ===")
           
            # Preparation countdown before tare
            print("\nPreparing for tare...")
            for i in range(10, 0, -1):
                print(f"Preparation: {i}s", end='\r')
                time.sleep(1)
            print("Preparation complete            ")
           
            # Tare balance
            print("Sending tare command to balance...")
            bal_ser.write(TARE_COMMAND)
            for i in range(args.tare_delay, 0, -1):
                print(f"Waiting for tare: {i}s", end='\r')
                time.sleep(1)
            print("Tare complete                   ")

            # Wait for sample
            for i in range(args.sample_time, 0, -1):
                w = get_weight()
                print(f"Add sample: {i}s, W={w:.4f}g", end='\r')
                time.sleep(1)
               
            # Get sample weight
            sample_w = get_weight()
            if sample_w <= 0:
                print("\nNo sample found, skipping")
                cycle += 1
                continue

            # Calculate volume needed
            solvent_ratio = 1 - args.ratio
            solvent_weight_needed = sample_w * solvent_ratio / args.ratio
            volume_needed_ml = solvent_weight_needed  # Assuming 1g/ml density
           
            # Calculate revolutions - adjust to match observed calibration
            revolutions_needed = volume_needed_ml / args.ml_per_rev
           
            # Ensure minimum revolutions
            MIN_REVOLUTIONS = 0.1
            if revolutions_needed < MIN_REVOLUTIONS:
                print(f"Warning: Setting to minimum {MIN_REVOLUTIONS} revolutions")
                revolutions_needed = MIN_REVOLUTIONS
           
            # Display calculations
            theoretical_total = sample_w + volume_needed_ml
            theoretical_conc = sample_w / theoretical_total * 100
           
            print(f"\nSample: {sample_w:.4f}g")
            print(f"Target volume to add: {volume_needed_ml:.4f}ml")
            print(f"Using calibration factor: {args.ml_per_rev:.4f}ml/revolution")
            print(f"Calculated revolutions needed: {revolutions_needed:.4f} revs")
           
            # Dispense by volume
            print("Dispensing by volume...")
            if pump.dispense_volume(revolutions_needed):
                if pump.start_pump():
                    print("Pump running - dispensing precise volume")
                   
                    # Monitor progress with improved status detection
                    start = time.time()
                    done = False
                    max_time = revolutions_needed / (args.flow_rate / 60) * 1.5
                    last_status_check = time.time() - 3  # Force immediate first check
                    force_stop_after = max_time * 1.1  # Emergency stop time

                    while not done and time.time() - start < args.timeout:
                        current_time = time.time()
                        cw = get_weight()
                        time_elapsed = current_time - start
                        time_pct = (time_elapsed / max_time * 100) if max_time > 0 else 0
                       
                        # More frequent status checks (every 1 second)
                        if current_time - last_status_check >= 1.0:
                            last_status_check = current_time
                           
                            # Check pump status more thoroughly
                            try:
                                # 1. Check status command
                                status = pump.get_status()
                                status_str = status.decode(errors='ignore')
                               
                                if args.verbose:
                                    print(f"\nDebug - Pump status: {status!r} decoded: {status_str}")
                               
                                # 2. Check revolutions remaining
                                revs_remaining = pump.get_revs_remaining()
                                revs_str = revs_remaining.decode(errors='ignore')
                               
                                if args.verbose:
                                    print(f"Debug - Revs remaining: {revs_remaining!r} decoded: {revs_str}")
                               
                                # Check multiple stopping conditions
                                stop_detected = False
                               
                                # Check for status indicators
                                if any(c in status_str for c in 'SXH') or b'\x06' in status:
                                    stop_detected = True
                                    print("\nDetected pump stop via status")
                               
                                # Check for revolutions counter = 0
                                if '0' in revs_str or '.0' in revs_str or b'\x06' in revs_remaining:
                                    stop_detected = True
                                    print("\nDetected pump stop via revolutions counter")
                               
                                # If any stop condition met
                                if stop_detected:
                                    done = True
                                    break
                               
                            except Exception as e:
                                print(f"\nWarning: Error checking pump status: {e}")
                       
                        # Forced stop after expected time
                        if time_elapsed >= force_stop_after:
                            pump.stop_pump()
                            done = True
                            print(f"\nForce stopping pump after {time_elapsed:.1f}s (expected {max_time:.1f}s)")
                            break
                       
                        print(f"Progress {time_pct:.1f}% W={cw:.4f}g T={time_elapsed:.1f}s", end='\r')
                        time.sleep(args.weight_interval)
                   
                    # Final stop if needed
                    if not done:
                        print("\nTimeout - forcing pump stop")
                        pump.stop_pump()
                    
                    # Force clear the balance input buffer to get fresh readings
                    bal_ser.reset_input_buffer()
                    
                    # Send a weight request command to the balance (SI command requests immediate weight)
                    bal_ser.write(b'SI\r\n')
                    
                    # Wait for 30 seconds
                    print("\nWaiting 30 seconds for fluid to settle...")
                    for i in range(30, 0, -1):
                        print(f"Waiting: {i}s", end='\r')
                        time.sleep(1)
                    
                    # Force another fresh reading after waiting
                    bal_ser.reset_input_buffer()
                    bal_ser.write(b'SI\r\n')
                    time.sleep(0.5)  # Give a moment for the balance to respond
                    
                    print("\nWait complete                                  ")
                    
                    # Just get the current weight
                    final_weight = get_weight()
                    
                    actual_volume = final_weight - sample_w
                    actual_conc = (sample_w / final_weight) * 100 if final_weight > 0 else 0
                   
                else:
                    print("Failed to start pump")
            else:
                print("Failed to set dispensing volume")
           
            # Final reporting with final weight
            print(f"\n===== RESULTS =====")
            print(f"Initial sample weight: {sample_w:.4f}g")
            print(f"Final weight reading: {final_weight:.4f}g")
            print(f"Commanded volume: {volume_needed_ml:.4f}ml ({revolutions_needed:.4f} revs)")
            print(f"Actual volume added: {actual_volume:.4f}ml")
            
            # Calculate concentration and target values
            target_conc = args.ratio * 100
            print(f"Target concentration: {target_conc:.4f}%")
            print(f"Actual concentration: {actual_conc:.4f}%")
            
            if abs(actual_conc - target_conc) > 1.0:
                error_percent = abs(actual_conc - target_conc) / target_conc * 100
                print(f"Warning: Concentration off by {abs(actual_conc - target_conc):.4f}% ({error_percent:.2f}% error)")
           
            # Wait for next cycle
            for i in range(15, 0, -1):
                print(f"Next {i}s", end='\r')
                time.sleep(1)
            cycle += 1

    except KeyboardInterrupt:
        print("\nTerminated by user")
    finally:
        running = False
        pump.enable_local()
        pump.ser.close()
        bal_ser.close()
        print("Connections closed")


def main():
    p = argparse.ArgumentParser(description="Pump-based concentration control system")
    p.add_argument("--pump-port", default=PUMP_PORT, help=f"Pump port (default: {PUMP_PORT})")
    p.add_argument("--balance-port", default=BALANCE_PORT, help=f"Balance port (default: {BALANCE_PORT})")
    p.add_argument("--pump-number", type=int, default=PUMP_NUMBER, help="Pump number (default: 1)")
    p.add_argument("--ratio", type=float, default=SAMPLE_TO_SOLUTION_RATIO, help="Sample/solution ratio (default: 1/20.9)")
    p.add_argument("--flow-rate", type=float, default=FLOW_RATE, help="Pump speed in RPM for dispensing")
    p.add_argument("--fill-rate", type=float, default=FILL_FLOW_RATE, help="Pump speed in RPM for initial fill")
    p.add_argument("--ml-per-rev", type=float, default=DEFAULT_ML_PER_REVOLUTION, help="ml/revolution from calibration")
    p.add_argument("--profile", help="Load calibration from saved profile")
    p.add_argument("--timeout", type=int, default=MAX_PUMPING_TIME, help="Maximum pumping time in seconds")
    p.add_argument("--tare-delay", type=int, default=20, help="Seconds to wait after tare")
    p.add_argument("--sample-time", type=int, default=20, help="Seconds for sample addition")
    p.add_argument("--weight-interval", type=float, default=0.5, help="Seconds between readings")
    p.add_argument("--skip-fill", action="store_true", help="Skip tubing fill step")
    p.add_argument("--verbose", action="store_true", help="Show detailed communication")
    args = p.parse_args()
   
    # Load calibration profile if specified
    if args.profile:
        try:
            cal_manager = CalibrationManager()
            profile = cal_manager.get_profile(args.profile)
            if profile:
                args.ml_per_rev = profile["ml_per_revolution"]
                print(f"Loaded profile '{args.profile}': {args.ml_per_rev} ml/revolution")
            else:
                print(f"Profile '{args.profile}' not found, using default")
        except Exception as e:
            print(f"Error loading profile: {e}")
   
    run_concentration_control(args)


if __name__ == "__main__":
    main()

