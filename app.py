from py5paisa import *
from datetime import *
import pytz
import time
import numpy as np
import pandas as pd
import pyotp
import json
import os

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


# MongoDB connection
mongo_uri = "mongodb+srv://knightearner:vQ8LqztvG31nkFIC@mongodb.ksex2.mongodb.net/?retryWrites=true&w=majority&appName=MongoDB"

# Create a new client and connect to the server
mongo_client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = mongo_client["app_db"]  # Database name
collection = db["switch"]  # Collection name


def get_switch_status():
    switch = collection.find_one({"name": "switch_status"})
    if switch:
        return switch["status"]
    else:
        return False

def get_logs():
    return [x['logs'] for x in collection.find({"name": "log"})][-20:]


def append_logs(st):
    collection.insert_many([{"name": "log", "logs": st}])



def get_BookedPL(client):
    BookedPL=0
    for pos in client.positions():
        BookedPL+=pos['BookedPL']
        BookedPL+=pos['MTOM']
    return BookedPL



def check_market_timing():
    if datetime.now(pytz.timezone('Asia/Kolkata')).hour == 9:
        if datetime.now(pytz.timezone('Asia/Kolkata')).minute >=20  and get_switch_status():
            return True
    elif datetime.now(pytz.timezone('Asia/Kolkata')).hour > 9 and datetime.now(pytz.timezone('Asia/Kolkata')).hour < 16 and get_switch_status():
        return True
    return False


def check_squareoff_timing():
    if datetime.now(pytz.timezone('Asia/Kolkata')).hour == 15:
        if datetime.now(pytz.timezone('Asia/Kolkata')).minute >=15:
            return True
    return False

def squareoff_all_positions(client):
    for pos in client.positions():
        NetQty=pos['NetQty']
        if NetQty>0:
            LTP=pos['LTP']-1
            ScripCode=int(pos['ScripCode'])
            client.place_order(OrderType='S', Exchange='N', ExchangeType="D", ScripCode=ScripCode, Qty=NetQty, Price=LTP)
            print('SquareOff '+pos['ScripName'])
    # update_switch_OFF()


def squareoff_positions(client,instrument_name):
    
    for pos in client.positions():
        NetQty=pos['NetQty']
        if NetQty>0 and instrument_name in pos['ScripName']:
            LTP=pos['LTP']-1
            ScripCode=int(pos['ScripCode'])
            client.place_order(OrderType='S', Exchange='N', ExchangeType="D", ScripCode=ScripCode, Qty=NetQty, Price=LTP)
            print('SquareOff '+pos['ScripName'])


def closest_index(lst, K):
    return min(range(len(lst)), key=lambda i: abs(lst[i] - K))

def get_option_chain(client,asset):
    k=client.get_expiry("N",asset)
    print(k)
    latest_expiry=[]
    for i in k['Expiry']:
        latest_expiry.append(i['ExpiryDate'][6:19])
    # print(latest_expiry)
            
    k = client.get_option_chain("N", asset, latest_expiry[0])
    k = (k['Options'])
    df = pd.DataFrame(k)[['CPType','LastRate','StrikeRate','ScripCode']]
    ce_df=df[df.CPType=='CE']
    ce_df.reset_index(inplace=True,drop=True)
    pe_df=df[df.CPType=='PE']
    pe_df.reset_index(inplace=True,drop=True)

    return [ce_df,pe_df]


def broker_login():

    totp = pyotp.TOTP(os.environ['TOTP']).now()
    cred = {
            "APP_NAME": os.environ['APP_NAME'],
            "APP_SOURCE": os.environ['APP_SOURCE'],
            "USER_ID": os.environ['USER_ID'],
            "PASSWORD": os.environ['PASSWORD'],
            "USER_KEY": os.environ['USER_KEY'],
            "ENCRYPTION_KEY": os.environ['ENCRYPTION_KEY']
        }


    client = FivePaisaClient(cred=cred)

    totp_str=str(totp)
    print(totp_str)
    client.get_totp_session(os.environ['client_code'],totp_str,os.environ['pin'])

    return client



def calculate_ema(prices, period=20):
    return prices.ewm(span=period, adjust=False).mean()


def option_hedge(client):

    time_now = datetime.now(pytz.timezone('Asia/Kolkata'))
    print('Time Now = ',time_now)
    to_ = time_now.date() + timedelta(days=2)
    from_ = time_now.date()
    timeframe='1m'


    first_instrument_script=999920005

    first_instrument_lot=15

    first_instrument_name='BANKNIFTY'
    print('first_instrument_name = ',first_instrument_name)

    df = client.historical_data('N', 'C', first_instrument_script, timeframe, str(from_),str(to_))

    df['diff']=abs(df['Close']-df['Open'])
    df['20_EMA_diff']=calculate_ema(df['diff'])
    df['signal']=df['diff']>df['20_EMA_diff']
    df['sig_dir']=df['Close']-df['Open']
    df['sig_dir']=df['sig_dir'].apply(lambda x: 1 if x>0 else 0)


    flag=''

    if df['signal'].values.tolist()[-2]==True and df['sig_dir'].values.tolist()[-2]==1:
        flag='BUY'
    elif df['signal'].values.tolist()[-2]==True and df['sig_dir'].values.tolist()[-2]==0:
        flag='SELL'

    close=df.Close.values.tolist()

    print(df['signal'].values.tolist()[-5:],df['sig_dir'].values.tolist()[-5:])
    

    first_instrument_option_chain=get_option_chain(client,first_instrument_name)

    first_instrument_ce=first_instrument_option_chain[0]
    first_instrument_pe=first_instrument_option_chain[1]    



    First_instrument_ce_ScripCode = first_instrument_ce.loc[closest_index(list(first_instrument_ce.StrikeRate), close[-1])].ScripCode
    First_instrument_pe_ScripCode = first_instrument_pe.loc[closest_index(list(first_instrument_pe.StrikeRate), close[-1])].ScripCode

    print(First_instrument_ce_ScripCode,First_instrument_pe_ScripCode)


    flag_=''

    for pos in client.positions():

        if 'CE'in pos['ScripName'] and pos['NetQty']>0:
            flag_='BUY'
        elif 'PE'in pos['ScripName'] and pos['NetQty']>0:
            flag_='SELL'



    if check_squareoff_timing() or flag=='' or get_BookedPL(client)<-(100*15):
        flag=''
        print('------------------------------- No More position -------------------------------')
        client.squareoff_all()

    print('Signal = ',flag)
    print('Open Position Signal = ',flag_)

    if flag=='BUY' and flag_!='BUY' and check_squareoff_timing()==False:
        print(flag,flag_,'BUY___________')
        client.squareoff_all()
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_ce_ScripCode), Qty=first_instrument_lot, Price=0)
        
    
    elif flag=='SELL' and flag_!='SELL' and check_squareoff_timing()==False:
        print(flag,flag_,'SELL___________')
        client.squareoff_all()
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_pe_ScripCode), Qty=first_instrument_lot, Price=0)



    BookedPL=get_BookedPL(client)
    print('------------------------------------------')
    print('BookedPL = ',BookedPL)
    print('------------------------------------------')

    append_logs(str(datetime.now(pytz.timezone('Asia/Kolkata')))+' : BookedPL = '+str(BookedPL))
    



if __name__ == '__main__':
    # broker = broker_login()
    # option_hedge(broker)
    # time.sleep(10)


  while True:
    # broker = broker_login()
    # option_hedge(broker)

    day_number=datetime.now(pytz.timezone('Asia/Kolkata')).weekday()
    print('Loop Time ', datetime.now(pytz.timezone('Asia/Kolkata')))
    time.sleep(10)
    if check_market_timing() and (day_number not in [5,6]) and get_switch_status():
      broker = broker_login()
      while True:
        print('Running ', datetime.now(pytz.timezone('Asia/Kolkata')))
        # time.sleep(290)
        time.sleep(10)
        print(check_market_timing() and get_switch_status())
        print(get_switch_status())
        if check_market_timing() and get_switch_status():
            option_hedge(broker)
        else:
          break
from flask import Flask, jsonify, render_template
import threading
import time

app = Flask(__name__)

# Define the function for the infinite loop
def infinite_loop():
    while True:
        day_number=datetime.now(pytz.timezone('Asia/Kolkata')).weekday()
        print('Loop Time ', datetime.now(pytz.timezone('Asia/Kolkata')),flush=True)
        append_logs('Loop Time = '+str(datetime.now(pytz.timezone('Asia/Kolkata'))))
        time.sleep(10)
        if check_market_timing() and (day_number not in [5,6]) and get_switch_status():
            broker = broker_login()
            while True:
                append_logs('Running = '+str(datetime.now(pytz.timezone('Asia/Kolkata'))))
                print('Running ', datetime.now(pytz.timezone('Asia/Kolkata')),flush=True)
                # time.sleep(290)
                time.sleep(10)
                if check_market_timing() and get_switch_status():
                    option_hedge(broker)
                else:
                    break


# Function to start the infinite loop in a separate thread
def start_infinite_loop():
    thread = threading.Thread(target=infinite_loop)
    thread.daemon = True  # This makes the thread exit when the main program exits
    thread.start()




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


# Start the infinite loop in a separate thread
loop_thread = threading.Thread(target=infinite_loop, daemon=True)
loop_thread.start()

if __name__ == "__main__":
    app.run(debug=True)
