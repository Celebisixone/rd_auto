# voltage_troubleshoot.py
from pymycobot import MyCobot280
import time
import json
import os
from datetime import datetime

# ——— CONFIGURATION ———
PORT = "COM4"
BAUDRATE = 115200
LOG_FILE = "voltage_troubleshoot_log.txt"

class VoltageMonitor:
    def __init__(self, port=PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.mc = None
        self.log_data = []
        
    def log(self, message, level="INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.log_data.append(log_entry)
        
    def save_log(self):
        """Save log to file."""
        try:
            with open(LOG_FILE, 'w') as f:
                f.write("\n".join(self.log_data))
            self.log(f"Log saved to {LOG_FILE}")
        except Exception as e:
            self.log(f"Failed to save log: {e}", "ERROR")
    
    def connect(self):
        """Connect to robot with error handling."""
        try:
            self.log("Attempting to connect to MyCobot280...")
            self.mc = MyCobot280(self.port, self.baudrate)
            self.log("Robot object created successfully")
            
            # Test basic communication
            self.log("Testing basic communication...")
            if self.mc.is_controller_connected():
                self.log("Controller communication: OK")
                return True
            else:
                self.log("Controller communication: FAILED", "WARNING")
                self.log("Proceeding anyway - some functions may still work")
                return True
                
        except Exception as e:
            self.log(f"Failed to connect: {e}", "ERROR")
            return False
    
    def power_on_test(self):
        """Test power on functionality."""
        self.log("\n=== POWER ON TEST ===")
        try:
            self.log("Sending power_on command...")
            self.mc.power_on()
            time.sleep(3)
            self.log("Power on command sent successfully")
            
            # Test if servos respond
            self.log("Testing servo response...")
            angles = self.mc.get_angles()
            if angles and angles != -1:
                self.log(f"Servos responding - Current angles: {angles}")
                return True
            else:
                self.log("Servos not responding to get_angles()", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Power on test failed: {e}", "ERROR")
            return False
    
    def voltage_monitoring_test(self):
        """Monitor voltage-related parameters."""
        self.log("\n=== VOLTAGE MONITORING TEST ===")
        
        # Check if robot has voltage monitoring capabilities
        try:
            # Some MyCobot models support voltage reading
            voltage = getattr(self.mc, 'get_system_voltage', lambda: None)()
            if voltage:
                self.log(f"System voltage: {voltage}V")
            else:
                self.log("Direct voltage reading not available")
        except:
            self.log("Voltage monitoring method not supported")
        
        # Check servo states
        self.log("Checking individual servo states...")
        for servo_id in range(1, 7):
            try:
                # Check if servo is powered
                servo_status = getattr(self.mc, 'is_servo_enable', lambda x: None)(servo_id)
                if servo_status is not None:
                    self.log(f"Servo {servo_id} enabled: {servo_status}")
                
                # Try to get servo voltage if available
                servo_voltage = getattr(self.mc, 'get_servo_voltages', lambda: None)()
                if servo_voltage and len(servo_voltage) >= servo_id:
                    self.log(f"Servo {servo_id} voltage: {servo_voltage[servo_id-1]}V")
                    
            except Exception as e:
                self.log(f"Could not check servo {servo_id}: {e}")
    
    def movement_stress_test(self):
        """Test movements that commonly fail due to voltage issues."""
        self.log("\n=== MOVEMENT STRESS TEST ===")
        
        # Store original position
        try:
            original_angles = self.mc.get_angles()
            if not original_angles or original_angles == -1:
                self.log("Cannot read original position", "ERROR")
                return False
            self.log(f"Original position: {original_angles}")
        except Exception as e:
            self.log(f"Failed to read original position: {e}", "ERROR")
            return False
        
        # Test sequence of movements that stress the power system
        test_movements = [
            ([0, 0, 0, 0, 0, 0], "Home position"),
            ([45, 30, -60, 30, 45, 0], "Mid-range position"),
            ([90, 45, -90, 45, 90, 0], "Higher power position"),
            ([0, 0, 0, 0, 0, 0], "Return to home"),
        ]
        
        for i, (angles, description) in enumerate(test_movements):
            try:
                self.log(f"Test {i+1}: Moving to {description}")
                self.log(f"Target angles: {angles}")
                
                # Send movement command
                self.mc.send_angles(angles, 20)  # Slow speed to reduce power draw
                time.sleep(4)
                
                # Verify movement completed
                current_angles = self.mc.get_angles()
                if current_angles and current_angles != -1:
                    self.log(f"Reached: {current_angles}")
                    
                    # Check if movement was accurate (within tolerance)
                    tolerance = 5.0  # degrees
                    accurate = all(abs(target - actual) < tolerance 
                                 for target, actual in zip(angles, current_angles))
                    
                    if accurate:
                        self.log(f"Movement {i+1}: SUCCESS")
                    else:
                        self.log(f"Movement {i+1}: INACCURATE (possible power issue)", "WARNING")
                else:
                    self.log(f"Movement {i+1}: FAILED - Cannot read position", "ERROR")
                    
                time.sleep(2)  # Rest between movements
                
            except Exception as e:
                self.log(f"Movement {i+1} failed: {e}", "ERROR")
                return False
        
        return True
    
    def gripper_power_test(self):
        """Test gripper functionality which is sensitive to power issues."""
        self.log("\n=== GRIPPER POWER TEST ===")
        
        try:
            # Test gripper open
            self.log("Testing gripper open...")
            self.mc.set_gripper_state(0, 50)
            time.sleep(2)
            
            # Test gripper close
            self.log("Testing gripper close...")
            self.mc.set_gripper_state(1, 50)
            time.sleep(2)
            
            # Test gripper open again
            self.log("Testing gripper open (final)...")
            self.mc.set_gripper_state(0, 50)
            time.sleep(2)
            
            self.log("Gripper test completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Gripper test failed: {e}", "ERROR")
            return False
    
    def continuous_monitoring(self, duration=30):
        """Monitor robot status continuously for voltage drops."""
        self.log(f"\n=== CONTINUOUS MONITORING ({duration}s) ===")
        
        start_time = time.time()
        sample_count = 0
        failures = 0
        
        while time.time() - start_time < duration:
            try:
                # Try to read angles
                angles = self.mc.get_angles()
                sample_count += 1
                
                if angles and angles != -1:
                    if sample_count % 10 == 0:  # Log every 10th sample
                        self.log(f"Sample {sample_count}: Angles = {angles}")
                else:
                    failures += 1
                    self.log(f"Sample {sample_count}: FAILED to read angles", "WARNING")
                
                time.sleep(1)
                
            except Exception as e:
                failures += 1
                self.log(f"Monitoring error: {e}", "ERROR")
                time.sleep(1)
        
        failure_rate = (failures / sample_count) * 100 if sample_count > 0 else 100
        self.log(f"Monitoring complete: {failures}/{sample_count} failures ({failure_rate:.1f}%)")
        
        if failure_rate > 10:
            self.log("High failure rate detected - possible voltage/power issue", "ERROR")
        elif failure_rate > 5:
            self.log("Moderate failure rate - monitor power supply", "WARNING")
        else:
            self.log("Low failure rate - power seems stable")
    
    def power_supply_recommendations(self):
        """Provide power supply recommendations based on test results."""
        self.log("\n=== POWER SUPPLY RECOMMENDATIONS ===")
        
        recommendations = [
            "1. Check power adapter specifications:",
            "   - MyCobot 280 requires 12V DC power supply",
            "   - Minimum 5A current rating (8A recommended for heavy loads)",
            "   - Use only the official power adapter or equivalent quality",
            "",
            "2. Check connections:",
            "   - Ensure power cable is firmly connected",
            "   - Check for loose connections at both ends",
            "   - Inspect cable for damage or wear",
            "",
            "3. Environmental factors:",
            "   - Ensure adequate ventilation around power supply",
            "   - Check ambient temperature (high temp can cause voltage drops)",
            "   - Avoid extension cords or power strips when possible",
            "",
            "4. Load considerations:",
            "   - Heavy payloads increase power consumption",
            "   - Fast movements draw more current",
            "   - Multiple simultaneous servo movements are power-intensive",
            "",
            "5. If problems persist:",
            "   - Try a different power outlet",
            "   - Test with minimal load (no gripper payload)",
            "   - Consider upgrading to higher-capacity power supply",
            "   - Contact technical support with this log file"
        ]
        
        for rec in recommendations:
            self.log(rec)
    
    def run_full_diagnostics(self):
        """Run complete voltage troubleshooting sequence."""
        self.log("="*60)
        self.log("MYCOBOT 280 VOLTAGE TROUBLESHOOTING")
        self.log("="*60)
        
        # Connect to robot
        if not self.connect():
            self.log("Cannot connect to robot - check connection and try again", "ERROR")
            self.save_log()
            return
        
        # Run tests
        tests = [
            ("Power On Test", self.power_on_test),
            ("Voltage Monitoring", self.voltage_monitoring_test),
            ("Movement Stress Test", self.movement_stress_test),
            ("Gripper Power Test", self.gripper_power_test),
        ]
        
        test_results = {}
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                test_results[test_name] = result
            except Exception as e:
                self.log(f"{test_name} crashed: {e}", "ERROR")
                test_results[test_name] = False
        
        # Continuous monitoring (optional)
        try:
            user_input = input("\nRun 30-second continuous monitoring? (y/n): ").lower()
            if user_input in ['y', 'yes']:
                self.continuous_monitoring(30)
        except:
            pass
        
        # Summary
        self.log("\n=== TEST SUMMARY ===")
        for test_name, result in test_results.items():
            status = "PASS" if result else "FAIL"
            self.log(f"{test_name}: {status}")
        
        # Recommendations
        self.power_supply_recommendations()
        
        # Save log
        self.save_log()
        
        return test_results

def main():
    """Main menu for voltage troubleshooting."""
    monitor = VoltageMonitor()
    
    while True:
        print("\n" + "="*50)
        print("MyCobot 280 Voltage Troubleshooting")
        print("="*50)
        print("1) Full Diagnostics")
        print("2) Quick Power Test")
        print("3) Movement Stress Test Only")
        print("4) Continuous Monitoring (30s)")
        print("5) Gripper Test Only")
        print("6) View Recommendations")
        print("7) Exit")
        
        choice = input("\nSelect option (1-7): ").strip()
        
        if choice == '1':
            monitor.run_full_diagnostics()
            
        elif choice == '2':
            if monitor.connect():
                monitor.power_on_test()
                monitor.save_log()
            
        elif choice == '3':
            if monitor.connect():
                monitor.power_on_test()
                monitor.movement_stress_test()
                monitor.save_log()
            
        elif choice == '4':
            if monitor.connect():
                monitor.power_on_test()
                monitor.continuous_monitoring(30)
                monitor.save_log()
            
        elif choice == '5':
            if monitor.connect():
                monitor.power_on_test()
                monitor.gripper_power_test()
                monitor.save_log()
            
        elif choice == '6':
            monitor.power_supply_recommendations()
            
        elif choice == '7':
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please select 1-7.")

if __name__ == "__main__":
    main()