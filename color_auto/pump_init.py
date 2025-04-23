#!/usr/bin/env python3
"""
Masterflex L/S Digital Pump Drive Troubleshooting Script
This script tests basic communication with the pump to diagnose connection issues.
"""

import serial
import time
import sys


class PumpTester:
    """Class to test Masterflex pump communication"""

    def __init__(self, port, pump_number=1, verbose=True):
        self.pump_number = f"{pump_number:02d}"
        self.verbose = verbose

        print(f"Attempting to connect to pump on {port}...")
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=4800,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=2
            )
            print(f"Serial port {port} opened successfully")
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print("Serial buffers cleared")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            sys.exit(1)


    def debug_print(self, message):
        if self.verbose:
            print(message)


    def hex_dump(self, data):
        return ' '.join(f"{b:02x}" for b in data)


    def read_response(self, timeout=2.0):
        start = time.time()
        resp = b''
        while time.time() - start < timeout:
            if self.ser.in_waiting:
                chunk = self.ser.read(self.ser.in_waiting)
                resp += chunk
                self.debug_print(f"Received: {chunk!r} (hex: {self.hex_dump(chunk)})")
            if resp and time.time() - start > 0.5:
                time.sleep(0.1)
                if self.ser.in_waiting == 0:
                    break
            time.sleep(0.1)
        return resp


    def send_raw(self, data, read_response=True):
        self.debug_print(f"Sending raw: {data!r} (hex: {self.hex_dump(data)})")
        self.ser.write(data)
        if read_response:
            resp = self.read_response()
            self.debug_print(f"Raw response: {resp!r} (hex: {self.hex_dump(resp)})")
            return resp
        return b''


    def send_command(self, cmd, read_response=True):
        packet = b'\x02' + cmd.encode() + b'\x0D'
        self.debug_print(f"Sending command: {cmd} (hex: {self.hex_dump(packet)})")
        self.ser.write(packet)
        if read_response:
            resp = self.read_response()
            self.debug_print(f"Response: {resp!r} (hex: {self.hex_dump(resp)})")
            return resp
        return b''


    def send_enquiry(self):
        """Test ENQ and accept either P? or status frame."""
        print("\n--- Testing ENQ (Enquiry) Communication ---")
        resp = self.send_raw(b'\x05')
        # Accept P?xx or PnnIxxxxx as valid
        if resp.startswith(b'\x02P?') or resp.startswith(b'\x02P' + self.pump_number.encode()):
            print("SUCCESS: Received expected response to ENQ")
            return True
        else:
            print(f"WARNING: Unexpected response to ENQ: {resp!r}")
            return False


    def assign_pump_number(self):
        print("\n--- Testing Pump Number Assignment ---")
        print(f"Assigning pump number {self.pump_number}...")
        response = self.send_command(f"P{self.pump_number}")
    
        # If we get ACK, or no response (already numbered), consider it OK
        if response == b'\x06' or response == b'':
            print("SUCCESS: Pump number assigned or already set")
            return True
        else:
            print(f"WARNING: Unexpected response to pump number assignment: {response!r}")
            return False




    def test_remote_control(self):
        print("\n--- Testing Remote Control Mode ---")
        resp = self.send_command(f"P{self.pump_number}R")
        if resp == b'\x06':
            print("SUCCESS: Remote control enabled")
            return True
        print(f"WARNING: Remote control failed: {resp!r}")
        return False


    def test_status_request(self):
        print("\n--- Testing Status Request ---")
        resp = self.send_command(f"P{self.pump_number}I")
        if resp.startswith(b'\x02P') and len(resp) > 5:
            print(f"SUCCESS: Status response: {resp!r}")
            return True
        print(f"WARNING: Status request failed: {resp!r}")
        return False


    def test_speed_setting(self):
        print("\n--- Testing Speed Setting ---")
        resp = self.send_command(f"P{self.pump_number}S+010.0")
        if resp == b'\x06':
            print("SUCCESS: Speed set")
            return True
        print(f"WARNING: Speed set failed: {resp!r}")
        return False


    def test_get_speed(self):
        print("\n--- Testing Get Speed ---")
        resp = self.send_command(f"P{self.pump_number}S")
        if resp.startswith(b'\x02S'):
            print(f"SUCCESS: Get speed returned: {resp!r}")
            return True
        print(f"WARNING: Get speed failed: {resp!r}")
        return False


    def test_volume_setting(self):
        print("\n--- Testing Volume Setting ---")
        for fmt in [f"P{self.pump_number}V1.00",
                    f"P{self.pump_number}V01.00",
                    f"P{self.pump_number}V001.00"]:
            print(f"Trying format: {fmt}")
            resp = self.send_command(fmt)
            if resp == b'\x06':
                print(f"SUCCESS: Volume set with {fmt}")
                return True
            print(f"WARNING: {fmt} failed: {resp!r}")
        return False


    def test_start_stop(self):
        print("\n--- Testing Start/Stop Commands ---")
        start = self.send_command(f"P{self.pump_number}G")
        if start == b'\x06':
            print("SUCCESS: Pump started")
            time.sleep(3)
            stop = self.send_command(f"P{self.pump_number}H")
            if stop == b'\x06':
                print("SUCCESS: Pump stopped")
                return True
            print(f"WARNING: Stop failed: {stop!r}")
            return False
        print(f"WARNING: Start failed: {start!r}")
        return False


    def enable_local(self):
        print("\n--- Returning to Local Control ---")
        resp = self.send_command(f"P{self.pump_number}L")
        if resp == b'\x06':
            print("SUCCESS: Local control enabled")
            return True
        print(f"WARNING: Local control failed: {resp!r}")
        return False


    def run_diagnostic(self):
        print("\n====== MASTERFLEX PUMP DIAGNOSTIC TEST ======\n")
        # Force LOCAL mode at start to reset STOP latch & numbering :contentReference[oaicite:4]{index=4}&#8203;:contentReference[oaicite:5]{index=5}
        print("Forcing LOCAL mode before tests…")
        self.send_command(f"P{self.pump_number}L")
        time.sleep(0.5)

        tests = [
            (self.send_enquiry,     "Initial communication"),
            (self.assign_pump_number, "Pump number assignment"),
            (self.test_remote_control,"Remote control mode"),
            (self.test_status_request,"Status request"),
            (self.test_speed_setting, "Speed setting"),
            (self.test_get_speed,    "Get speed"),
            (self.test_volume_setting,"Volume setting"),
            (self.test_start_stop,   "Start/Stop commands"),
            (self.enable_local,      "Return to local control"),
        ]

        results = []
        for fn, name in tests:
            print("\n" + "="*50)
            ok = fn()
            results.append((name, ok))

        # Summary
        print("\n\n====== DIAGNOSTIC SUMMARY ======")
        passed = sum(1 for _, ok in results if ok)
        for name, ok in results:
            print(f"{name}: {'PASSED' if ok else 'FAILED'}")
        rate = passed / len(results) * 100
        print(f"\nOverall: {rate:.1f}% ({passed}/{len(results)})")

        if rate == 100:
            print("\nAll tests passed. Communication is healthy.")
        elif rate >= 70:
            print("\nMost tests passed. Minor issues only.")
        else:
            print("\nSignificant communication issues detected.")

        return rate


    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="Serial port (e.g., COM6)")
    parser.add_argument("--pump", type=int, default=1, help="Pump number")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    tester = PumpTester(args.port, args.pump, args.verbose)
    try:
        tester.run_diagnostic()
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        tester.close()


if __name__ == "__main__":
    main()



