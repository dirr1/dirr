import cv2
import subprocess
import numpy as np

# FFmpeg command to capture video from Decklink
ffmpeg_command = [
    'ffmpeg',
    '-f', 'decklink',
    '-i', 'DeckLink Mini Recorder 4K',  # Replace with your device name
    '-pix_fmt', 'bgr24',
    '-vcodec', 'rawvideo',
    '-an', '-sn',
    '-f', 'image2pipe',
    '-'
]

# Start FFmpeg process
ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Read frames in a loop
while True:
    # Read a frame from the FFmpeg process
    in_bytes = ffmpeg_process.stdout.read(1920 * 1080 * 3)  # Adjust resolution as needed
    if not in_bytes:
        break

    # Convert bytes to a NumPy array
    frame = np.frombuffer(in_bytes, np.uint8).reshape([1080, 1920, 3])  # Adjust resolution as needed

    # Display the frame using OpenCV
    cv2.namedWindow("Frame",cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Frame", cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
    cv2.imshow('Frame', frame)

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
ffmpeg_process.stdout.close()
ffmpeg_process.wait()
cv2.destroyAllWindows()