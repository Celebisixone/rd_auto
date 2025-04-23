#!/usr/bin/env python3
"""
Simple Pump Calibration Script

This script runs the pump for 10 revolutions and measures the weight change on the balance.
It then calculates and displays the g/rev value with 4 decimal places.
"""

import serial
import time
import threading
import argparse
import sys

# Default settings for pump
PUMP_PORT = 'COM6'
PUMP_NUMBER = 1
FLOW_RATE = 30  
DIRECTION = "CCW"

# Default settings for balance
BALANCE_PORT = 'COM5'
BALANCE_BAUD = 4800
BALANCE_TIMEOUT = 2
TARE_COMMAND = b'ST\r\n'

# Global variables for balance reading
latest_measurement = None
latest_lock = threading.Lock()
running = True

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
    """Get the latest weight reading from the balance"""
    with latest_lock:
        try:
            return float(latest_measurement or 0.0)
        except ValueError:
            return 0.0

class PumpController:
    """Simple pump control class"""

    def __init__(self, port, pump_number=1):
        self.pump_number = f"{pump_number:02d}"
        
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=4800,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=2
            )
            print(f"Connected to pump on {port}")
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Enable remote control
            self.enable_remote()
            
        except serial.SerialException as e:
            print(f"Error opening pump port: {e}")
            sys.exit(1)

    def send_command(self, cmd, read_response=True):
        """Send command to pump and get response"""
        pkt = b'\x02' + cmd.encode('ascii') + b'\x0D'
        self.ser.write(pkt)
        
        if read_response:
            time.sleep(0.3)
            if self.ser.in_waiting:
                return self.ser.read(self.ser.in_waiting)
            return b''
        return b''

    def enable_remote(self):
        """Enable remote control mode"""
        print("Enabling remote control...")
        return self.send_command(f"P{self.pump_number}R") == b'\x06'

    def enable_local(self):
        """Switch back to local control mode"""
        print("Returning to local control...")
        return self.send_command(f"P{self.pump_number}L") == b'\x06'

    def set_speed(self, rpm, direction=DIRECTION):
        """Set pump speed and direction"""
        print(f"Setting speed to {rpm} RPM, direction: {direction}")
        sign = "+" if direction == "CW" else "-"
        
        if rpm >= 100:
            cmd = f"P{self.pump_number}S{sign}{rpm:.0f}"
        else:
            cmd = f"P{self.pump_number}S{sign}{rpm:.1f}"
        
        return self.send_command(cmd) == b'\x06'

    def dispense_revolutions(self, revolutions):
        """Run pump for specific number of revolutions"""
        print(f"Setting volume to {revolutions:.2f} revolutions")
        cmd = f"P{self.pump_number}V{revolutions:.2f}"
        
        if self.send_command(cmd) == b'\x06':
            return self.start_pump()
        return False

    def start_pump(self):
        """Start the pump"""
        print("Starting pump...")
        return self.send_command(f"P{self.pump_number}G") == b'\x06'

    def stop_pump(self):
        """Stop the pump"""
        print("Stopping pump...")
        return self.send_command(f"P{self.pump_number}H") == b'\x06'
        
    def close(self):
        """Close the serial connection"""
        if hasattr(self, 'ser') and self.ser.is_open:
            self.enable_local()
            self.ser.close()
            print("Pump connection closed")

def run_simple_calibration(pump_port, balance_port, revolutions=10.0):
    """Run a simple calibration: dispense specified revolutions and measure weight change"""
    global running
    
    print("\n==== SIMPLE PUMP CALIBRATION ====")
    
    # Connect to pump
    pump = PumpController(pump_port, PUMP_NUMBER)
    
    # Connect to balance
    try:
        bal_ser = serial.Serial(
            balance_port,
            baudrate=BALANCE_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=BALANCE_TIMEOUT
        )
        print(f"Connected to balance on {balance_port}")
    except serial.SerialException as e:
        print(f"Balance port error: {e}")
        pump.close()
        return
    
    # Start balance reader thread
    threading.Thread(target=balance_reader_thread, args=(bal_ser,), daemon=True).start()
    
    try:
        # Set pump speed
        pump.set_speed(FLOW_RATE, DIRECTION)
        
        # First, tare the balance
        print("\nTaring the balance...")
        bal_ser.write(TARE_COMMAND)
        time.sleep(5)  # Wait for tare to complete
        
        # Get initial weight
        initial_weight = get_weight()
        print(f"Initial weight reading: {initial_weight:.4f}g")
        
        # Prepare for dispensing
        print("\nPreparing to dispense. Make sure container is properly positioned.")
        input("Press Enter to start dispensing...")
        
        # Run pump for specified number of revolutions
        if not pump.dispense_revolutions(revolutions):
            print("Failed to start dispensing")
            return
        
        # Wait for pump to complete
        print("\nDispensing... Please wait.")
        waiting_time = (60 / FLOW_RATE) * revolutions * 1.5  # Estimated time plus 50% margin
        start_time = time.time()
        
        while time.time() - start_time < waiting_time:
            current_weight = get_weight()
            elapsed = time.time() - start_time
            print(f"Time: {elapsed:.1f}s, Weight: {current_weight:.4f}g", end="\r")
            time.sleep(0.5)
        
        # Ensure pump is stopped
        pump.stop_pump()
        
        # Wait for balance to stabilize
        print("\n\nWaiting for balance to stabilize...")
        time.sleep(10)
        
        # Get final weight
        final_weight = get_weight()
        weight_change = final_weight - initial_weight
        
        # Calculate grams per revolution
        grams_per_rev = weight_change / revolutions
        
        print("\n==== CALIBRATION RESULTS ====")
        print(f"Initial weight:   {initial_weight:.4f}g")
        print(f"Final weight:     {final_weight:.4f}g")
        print(f"Weight change:    {weight_change:.4f}g")
        print(f"Revolutions:      {revolutions:.2f}")
        print(f"CALIBRATION:      {grams_per_rev:.4f} g/rev\n")
        
    except KeyboardInterrupt:
        print("\nCalibration interrupted by user")
    finally:
        # Clean up
        running = False
        pump.close()
        bal_ser.close()
        print("Connections closed")

def main():
    parser = argparse.ArgumentParser(description="Simple Pump Calibration Tool")
    parser.add_argument("--pump-port", default=PUMP_PORT, help=f"Pump serial port (default: {PUMP_PORT})")
    parser.add_argument("--balance-port", default=BALANCE_PORT, help=f"Balance serial port (default: {BALANCE_PORT})")
    parser.add_argument("--revolutions", type=float, default=10.0, help="Revolutions for calibration (default: 10.0)")
    args = parser.parse_args()
    
    run_simple_calibration(args.pump_port, args.balance_port, args.revolutions)

if __name__ == "__main__":
    main()

