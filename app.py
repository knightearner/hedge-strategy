import logging
from flask import Flask
import threading
import time

app = Flask(__name__)

# Set up the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def hello():
    return "Hello, World!"

# Infinite loop function with logging
def infinite_loop():
    while True:
        logger.info("Running in an infinite loop...")
        time.sleep(2)  # Sleep to avoid overwhelming the log with too many messages

# Start the infinite loop in a separate thread
loop_thread = threading.Thread(target=infinite_loop, daemon=True)
loop_thread.start()

if __name__ == "__main__":
    app.run(debug=True)
