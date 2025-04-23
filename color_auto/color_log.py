#!/usr/bin/env python3
"""
Concentration Control Data Logger

This script records sample weights, final weights, and concentration data
from the pump control system to a CSV file. It works alongside the 
pump_initialization.py script, monitoring the same serial port to collect data.
"""

import serial
import time
import csv
import os
import argparse
import datetime
import threading
import re

# Default configuration, matching the main script
DEFAULT_BALANCE_PORT = 'COM5'
DEFAULT_BALANCE_BAUD = 4800
DEFAULT_CSV_FILENAME = 'concentration_data.csv'

# Global variables for thread communication
latest_sample_weight = None
latest_final_weight = None
sample_weight_lock = threading.Lock()
final_weight_lock = threading.Lock()
running = True

def parse_weight_from_line(line):
    """Parse a weight value from a balance output line"""
    try:
        txt = line.decode(errors='ignore').strip()
        num = ''.join(c for c in txt if c.isdigit() or c in '.-')
        if num:
            return round(float(num), 4)
    except (ValueError, AttributeError):
        pass
    return None

def balance_monitor_thread(port, baud_rate):
    """
    Monitor the balance serial port for weight readings.
    This runs independently of the main pump control script,
    capturing the same data for logging purposes.
    """
    global latest_sample_weight, latest_final_weight, running

    print(f"Starting balance monitor on {port} at {baud_rate} baud")
    try:
        bal_ser = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2
        )
        
        # Variables to track state
        in_sample_phase = False
        in_final_phase = False
        
        while running:
            if bal_ser.in_waiting:
                line = bal_ser.readline()
                weight = parse_weight_from_line(line)
                
                if weight is not None:
                    # Also check the raw line for state indicators
                    line_str = line.decode(errors='ignore').lower()
                    
                    # Detect sample weight phase (after tare, before pumping)
                    if "add sample" in line_str:
                        in_sample_phase = True
                        in_final_phase = False
                    
                    # Detect final weight phase (after pumping)
                    elif "wait complete" in line_str or "stabilized" in line_str:
                        in_sample_phase = False
                        in_final_phase = True
                    
                    # Save the appropriate weight based on phase
                    if in_sample_phase and weight > 0:
                        with sample_weight_lock:
                            latest_sample_weight = weight
                            print(f"Logged sample weight: {weight}g")
                    
                    elif in_final_phase and weight > 0:
                        with final_weight_lock:
                            latest_final_weight = weight
                            print(f"Logged final weight: {weight}g")
                            
                            # After capturing final weight, we have a complete cycle
                            if latest_sample_weight is not None:
                                save_data_to_csv(port)
                                
                                # Reset for next cycle
                                latest_sample_weight = None
                                latest_final_weight = None
                                in_sample_phase = False
                                in_final_phase = False
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
    except serial.SerialException as e:
        print(f"Error with balance serial port: {e}")
    finally:
        if 'bal_ser' in locals():
            bal_ser.close()

def save_data_to_csv(port, filename=DEFAULT_CSV_FILENAME):
    """Save the weight and concentration data to a CSV file"""
    with sample_weight_lock, final_weight_lock:
        sample_weight = latest_sample_weight
        final_weight = latest_final_weight
    
    if sample_weight is None or final_weight is None:
        return
    
    # Calculate derived values
    actual_volume_added = final_weight - sample_weight
    actual_concentration = (sample_weight / final_weight * 100) if final_weight > 0 else 0
    
    # Get current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepare data row
    data_row = [
        timestamp,
        sample_weight,
        final_weight,
        actual_volume_added,
        actual_concentration
    ]
    
    # Create header if file doesn't exist
    file_exists = os.path.isfile(filename)
    
    # Write to CSV file
    with open(filename, 'a', newline='') as csv_file:
        writer = csv.writer(csv_file)
        
        # Write header if new file
        if not file_exists:
            writer.writerow([
                'Timestamp', 
                'Sample Weight (g)', 
                'Final Weight (g)', 
                'Volume Added (ml)', 
                'Concentration (%)'
            ])
        
        # Write data row
        writer.writerow(data_row)
        print(f"Data saved to {filename}")

def main():
    """Main entry point for the logging script"""
    global running
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Concentration Control Data Logger")
    parser.add_argument("--port", default=DEFAULT_BALANCE_PORT, 
                        help=f"Balance port (default: {DEFAULT_BALANCE_PORT})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BALANCE_BAUD, 
                        help=f"Balance baud rate (default: {DEFAULT_BALANCE_BAUD})")
    parser.add_argument("--file", default=DEFAULT_CSV_FILENAME, 
                        help=f"CSV filename (default: {DEFAULT_CSV_FILENAME})")
    args = parser.parse_args()
    
    print(f"Concentration Control Data Logger")
    print(f"--------------------------------")
    print(f"Balance Port: {args.port}")
    print(f"CSV File: {args.file}")
    print(f"Starting monitoring...")
    
    # Start balance monitor thread
    monitor_thread = threading.Thread(
        target=balance_monitor_thread, 
        args=(args.port, args.baud),
        daemon=True
    )
    monitor_thread.start()
    
    try:
        # Keep main thread alive to handle keyboard interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down logger...")
        running = False
        monitor_thread.join(timeout=2)
        print("Logger shutdown complete")

if __name__ == "__main__":
    main()

