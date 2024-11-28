import logging
from flask import Flask
import threading
import time
import pytz
from datetime import datetime

app = Flask(__name__)

# Set up the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ist_time():
    # Get the current time in India Standard Time (IST)
    india_tz = pytz.timezone('Asia/Kolkata')
    return str(datetime.now(india_tz).strftime('%Y-%m-%d %H:%M:%S'))
    
@app.route('/')
def hello():
    return "Hello, World!"

# Infinite loop function with logging
def infinite_loop():
    while True:
        logger.info("Running in an infinite loop..."+get_ist_time())
        time.sleep(2)  # Sleep to avoid overwhelming the log with too many messages

# Start the infinite loop in a separate thread
loop_thread = threading.Thread(target=infinite_loop, daemon=True)
loop_thread.start()

if __name__ == "__main__":
    app.run(debug=True)
