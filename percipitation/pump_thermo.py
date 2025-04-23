from Phidget22.Phidget import *
from Phidget22.PhidgetException import *
from Phidget22.Devices.TemperatureSensor import *
from Phidget22.Devices.DCMotor import *
from Phidget22.Net import Net
import time


# Constants
TARGET_TEMP = 15.0       # Target temperature in Celsius
PUMP_RATE = 2.0          # Flow rate in mL/second at full motor power
TARGET_VOLUME = 30.0     # Volume to dispense in mL
MOTOR_POWER = 1.0        # Power level for the motor (1.0 = 100%)
TEMP_VINT_PORT = 5       # VINT port where temperature sensor is connected
MOTOR_VINT_PORT = 0      # VINT port where DC motor controller is connected


# Wireless VINT Hub connection details
# Update with your actual hub name
HUB_HOSTNAME = "P2"  # Replace with your hub's actual name
PASSWORD = "sixone1485!"               # Use empty string if no password set
SERVER_NAME = "PhidgetServer"


def main():
    # Connect directly to the wireless VINT hub without server discovery
    print(f"Attempting to connect to server: {HUB_HOSTNAME}")
    try:
        Net.addServer(SERVER_NAME, HUB_HOSTNAME, 5661, PASSWORD, 0)
        print(f"Successfully added server {SERVER_NAME}")
    except PhidgetException as e:
        print(f"Failed to add server: {e.details}")
        return
   
    # Give the network connection time to establish
    print("Waiting for connection to establish...")
    time.sleep(2)
   
    # Initialize Phidget Temperature Sensor
    temp_sensor = TemperatureSensor()
    temp_sensor.setHubPort(TEMP_VINT_PORT)
    temp_sensor.setIsRemote(True)
    # Remove setIsHubPortDevice as it's not necessary and might cause issues
   
    # Initialize the DC Motor controller
    motor = DCMotor()
    motor.setHubPort(MOTOR_VINT_PORT)
    motor.setIsRemote(True)
    # Remove setIsHubPortDevice as it's not necessary and might cause issues
   
    print("Opening connections to devices...")
   
    try:
        # Attach temperature sensor
        print("Connecting to temperature sensor...")
        temp_sensor.openWaitForAttachment(10000)
        print("Temperature sensor attached successfully")
       
        # Attach motor
        print("Connecting to motor controller...")
        motor.openWaitForAttachment(10000)
        print("Motor controller attached successfully")
    except PhidgetException as e:
        print(f"Failed to open devices: {e.details}")
        print("Troubleshooting tips:")
        print("1. Verify the hostname of your wireless VINT hub")
        print("2. Check that the hub is powered on and connected to your network")
        print("3. Ensure the VINT ports specified match where devices are connected")
        print("4. Check the Phidget Control Panel to see if devices are detected")
       
        # Clean up
        try:
            Net.removeServer(SERVER_NAME)
        except PhidgetException as e:
            print(f"Error removing server: {e.details}")
        return
   
    # Ensure motor is stopped at start
    motor.setTargetVelocity(0.0)
   
    print("Monitoring temperature...")
    print(f"Target temperature: {TARGET_TEMP}°C")
    print(f"Will dispense {TARGET_VOLUME}mL when target is reached")
   
    try:
        # Main loop
        while True:
            current_temp = temp_sensor.getTemperature()
            print(f"Current temperature: {current_temp:.2f}°C", end="\r")
           
            # Check if target temperature is reached
            if current_temp >= TARGET_TEMP:
                print(f"\nTarget temperature reached: {current_temp:.2f}°C")
                dispense_liquid(motor)
                break
               
            time.sleep(1)
           
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except PhidgetException as e:
        print(f"Phidget Exception: {e.details}")
    finally:
        # Clean up
        try:
            if temp_sensor.getAttached():
                temp_sensor.close()
                print("Temperature sensor closed")
           
            if motor.getAttached():
                motor.setTargetVelocity(0.0)  # Ensure motor is stopped
                motor.close()
                print("Motor controller closed")
           
            # Remove the server connection
            Net.removeServer(SERVER_NAME)
            print("Removed server connection")
        except PhidgetException as e:
            print(f"Error during cleanup: {e.details}")


def dispense_liquid(motor):
    print(f"Dispensing {TARGET_VOLUME}mL of liquid...")
   
    # Calculate time needed to pump the target volume
    pump_time = TARGET_VOLUME / (PUMP_RATE * MOTOR_POWER)
   
    # Start the pump by setting motor velocity
    motor.setTargetVelocity(MOTOR_POWER)
   
    # Wait for the calculated time
    time.sleep(pump_time)
   
    # Stop the pump by setting motor velocity to 0
    motor.setTargetVelocity(0.0)
   
    print("Dispensing complete!")


if __name__ == "__main__":
    main()

