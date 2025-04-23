import serial
import time
import threading
from datetime import datetime

# Configuration parameters – update these based on your setup:
COM_PORT = 'COM5'       # Replace with your assigned COM port (e.g., "COM5")
BAUD_RATE = 4800        # Use 4800 bps unless changed on the scale
TIMEOUT = 2             # Read timeout in seconds (increased if needed)

# Tare command (adjust spacing if necessary for your scale)
tare_command = b'ST\r\n'

# Global variable to store the latest measurement (decoded string, expected in grams)
latest_measurement = None
# Lock to protect the global variable
latest_lock = threading.Lock()

def reader_thread(ser):
    global latest_measurement
    while True:
        try:
            # Continuously read complete lines from the serial port
            data = ser.readline()
            if data:
                try:
                    decoded = data.decode('ascii').strip()
                except UnicodeDecodeError:
                    decoded = str(data)
                with latest_lock:
                    latest_measurement = decoded
        except serial.SerialException as e:
            print("Serial exception in reader:", e)
            break

def main():
    global latest_measurement
    try:
        ser = serial.Serial(
            COM_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT
        )
        print(f"Connected to scale on {COM_PORT} at {BAUD_RATE} bps.")
    except serial.SerialException as e:
        print("Error opening serial port:", e)
        return

    # Start the background thread that continuously reads from the scale
    thread = threading.Thread(target=reader_thread, args=(ser,), daemon=True)
    thread.start()

    cycle = 1
    try:
        while True:
            print(f"\n--- Cycle {cycle} start ---")
            # Stage 1: 0-10 seconds: Preparation period (prepare first container)
            time.sleep(10)
            
            # Stage 2: At 10s, send tare command
            ser.write(tare_command)
            print(f"{datetime.now().isoformat()} - Tare command sent.")
            # Allow a moment for the tare to complete
            time.sleep(5)
            print(f"{datetime.now().isoformat()} - Tare complete.")
            
            # Stage 3: 10-20 seconds: Wait for the item to be loaded
            time.sleep(9)  # Already waited 1 second after tare for stabilization
            
            # Stage 4: At 20s, record the measurement
            with latest_lock:
                measurement = latest_measurement
            print(f"{datetime.now().isoformat()} - Measurement complete: {measurement}.")
            
            # Stage 5: 20-30 seconds: Allow time to remove the item
            time.sleep(10)
            
            # Stage 6: At 30s, send tare command for the next item
            ser.write(tare_command)
            print(f"{datetime.now().isoformat()} - Tare command sent for next item.")
            time.sleep(1)
            print(f"{datetime.now().isoformat()} - Tare complete for next item.")
            
            cycle += 1
            if cycle == 2:
                print(f"{datetime.now().isoformat()} - Cycle 2 start.")
    except KeyboardInterrupt:
        print("\nTerminating cycle.")
    finally:
        if ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == "__main__":
    main()


