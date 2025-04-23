import cv2
import time
import datetime
import os

def capture_photo():
    # Initialize the webcam (0 is usually the default camera)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return None

    # Read one frame from the webcam
    ret, frame = cap.read()
    if not ret:
        print("Error: Can't receive frame (stream end?).")
        cap.release()
        return None

    # Release the camera immediately after capturing
    cap.release()
    return frame

def save_photo(frame, directory="photos"):
    # Create a directory for photos if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Use the current timestamp for a unique filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(directory, f"photo_{timestamp}.png")
    
    # Save the image as a PNG file
    cv2.imwrite(filename, frame)
    print(f"Photo saved as {filename}")

def main():
    while True:
        print("Capturing photo...")
        frame = capture_photo()
        if frame is not None:
            save_photo(frame)
        else:
            print("Failed to capture photo.")
        
        # Wait for 20 minutes (20*60 seconds) before taking the next photo
        print("Waiting for 20 minutes...")
        time.sleep(10)

if __name__ == "__main__":
    main()


