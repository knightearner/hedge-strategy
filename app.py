from flask import Flask, jsonify, render_template
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi



app = Flask(__name__)

# MongoDB connection
uri = "mongodb+srv://knightearner:vQ8LqztvG31nkFIC@mongodb.ksex2.mongodb.net/?retryWrites=true&w=majority&appName=MongoDB"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

db = client["app_db"]  # Database name
collection = db["switch"]  # Collection name


def get_switch_status():
    switch = collection.find_one({"name": "switch_status"})
    if switch:
        return switch["status"]
    else:
        return False

def get_logs():
    return [x['logs'] for x in collection.find({"name": "log"})]



app = Flask(__name__)

# Initial status is "OFF"
# status = get_switch_status()
# items = get_logs()
# items = [
#     "Item 1: Task completed",
#     "Item 2: Task in progress",
#     "Item 3: Waiting for approval",
#     "Item 4: Task not started",
#     "Item 5: Task on hold"
# ]



@app.route('/')
def index():
    return render_template('index.html')  # Serve the HTML page

@app.route('/api/status', methods=['GET'])
def get_status():
    status = get_switch_status()
    return jsonify({'status': status})  # Return the current status

@app.route('/api/items', methods=['GET'])
def get_items():
    items = get_logs()
    return jsonify({'items': items})  # Return list of items

@app.route('/api/status', methods=['POST'])
def toggle_status():
    # global status
    # Toggle the status between "ON" and "OFF"
    if get_switch_status():
        collection.find_one_and_update({"name": "switch_status"}, {"$set": { "status": False }})
    else:
        collection.find_one_and_update({"name": "switch_status"}, {"$set": { "status": True }})
    status=get_switch_status()
    return jsonify({'status': status})  # Return the new status

if __name__ == '__main__':
    app.run(debug=True)
