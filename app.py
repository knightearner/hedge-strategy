from py5paisa import *
from datetime import *
import pytz
import time
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





def option_hedge(client):

    time_now = datetime.now(pytz.timezone('Asia/Kolkata'))
    print('Time Now = ',time_now)
    to_ = time_now.date() + timedelta(days=2)
    from_ = time_now.date()
    timeframe='1m'


    first_instrument_script=1333
    second_instrument_script=4963

    NF_lot=550
    BNF_lot=700

    first_instrument_lot=NF_lot
    second_instrument_lot=BNF_lot

    first_instrument_name='HDFCBANK'
    second_instrument_name='ICICIBANK'

    print('first_instrument_name = ',first_instrument_name)
    print('second_instrument_name = ',second_instrument_name)


    bnf = client.historical_data('N', 'C', second_instrument_script, timeframe, str(from_),str(to_))
    nf = client.historical_data('N', 'C', first_instrument_script, timeframe, str(from_),str(to_))

    common_Datetime=nf.merge(bnf, on='Datetime', how='inner').Datetime.values.tolist()[4:]

    bnf=bnf[bnf.Datetime.isin(common_Datetime)].reset_index(drop=True)
    nf=nf[nf.Datetime.isin(common_Datetime)].reset_index(drop=True)

    bnf_close=bnf.Close.values.tolist()
    nf_close=nf.Close.values.tolist()
    
    st_bnf=bnf_close[0]
    st_nf=nf_close[0]
    
    x_axis=bnf.Datetime.values.tolist()
    
    ls_bnf=[x/st_bnf for x in bnf_close]
    ls_nf=[x/st_nf for x in nf_close]


    flag_bnf=''
    if ls_bnf[-2]>1.002 :
        flag_bnf='BUY'
    elif ls_bnf[-2]<0.998 :
        flag_bnf='SELL'


    flag_nf=''
    if ls_nf[-2]>1.002 :
        flag_nf='BUY'
    elif ls_nf[-2]<0.998 :
        flag_nf='SELL'




    df_first_instrument = client.historical_data('N', 'C', first_instrument_script, timeframe, str(from_),str(to_))
    df_second_instrument = client.historical_data('N', 'C', second_instrument_script, timeframe, str(from_),str(to_))
    


    df_first_instrument_close=df_first_instrument.Close.values.tolist()
    df_second_instrument_close=df_second_instrument.Close.values.tolist()
    
    st_df_first_instrument_close=df_first_instrument_close[0]
    st_df_second_instrument_close=df_second_instrument_close[0]

    

    first_instrument_option_chain=get_option_chain(client,first_instrument_name)
    second_instrument_option_chain=get_option_chain(client,second_instrument_name)

    first_instrument_ce=first_instrument_option_chain[0]
    first_instrument_pe=first_instrument_option_chain[1]

    second_instrument_ce=second_instrument_option_chain[0]
    second_instrument_pe=second_instrument_option_chain[1]
    



    First_instrument_ce_ScripCode = first_instrument_ce.loc[closest_index(list(first_instrument_ce.StrikeRate), st_df_first_instrument_close)].ScripCode
    First_instrument_pe_ScripCode = first_instrument_pe.loc[closest_index(list(first_instrument_pe.StrikeRate), st_df_first_instrument_close)].ScripCode

    
    Second_instrument_ce_ScripCode = second_instrument_ce.loc[closest_index(list(second_instrument_ce.StrikeRate), st_df_second_instrument_close)].ScripCode
    Second_instrument_pe_ScripCode = second_instrument_pe.loc[closest_index(list(second_instrument_pe.StrikeRate), st_df_second_instrument_close)].ScripCode

    print(First_instrument_ce_ScripCode,First_instrument_pe_ScripCode)
    print(Second_instrument_ce_ScripCode,Second_instrument_pe_ScripCode)
     


    flag_bnf_=''
    flag_nf_=''

    for pos in client.positions():

        if first_instrument_name in pos['ScripName'] and 'CE'in pos['ScripName'] and pos['NetQty']>0:
            flag_nf_='BUY'
        elif first_instrument_name in pos['ScripName'] and 'PE'in pos['ScripName'] and pos['NetQty']>0:
            flag_nf_='SELL'


        if second_instrument_name in pos['ScripName'] and 'CE'in pos['ScripName'] and pos['NetQty']>0:
            flag_bnf_='BUY'

        elif second_instrument_name in pos['ScripName'] and 'PE'in pos['ScripName'] and pos['NetQty']>0:
            flag_bnf_='SELL'




    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(First_instrument_ce_ScripCode)}]
    First_instrument_ce_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(First_instrument_pe_ScripCode)}]
    First_instrument_pe_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1


    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(Second_instrument_ce_ScripCode)}]
    Second_instrument_ce_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(Second_instrument_pe_ScripCode)}]
    Second_instrument_pe_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    
    if check_squareoff_timing():
        squareoff_all_positions(client)


    if flag_bnf=='':
        squareoff_positions(client,second_instrument_name)

    if flag_nf=='':
        squareoff_positions(client,first_instrument_name)


    if flag_bnf=='BUY' and flag_bnf_!='BUY' and check_squareoff_timing()==False:
        print('BUY ',second_instrument_name)
        squareoff_positions(client,second_instrument_name)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(Second_instrument_ce_ScripCode), Qty=second_instrument_lot, Price=Second_instrument_ce_Price)
        
    
    elif flag_bnf=='SELL' and flag_bnf_!='SELL' and check_squareoff_timing()==False:
        print('SELL ',second_instrument_name)
        squareoff_positions(client,second_instrument_name)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(Second_instrument_pe_ScripCode), Qty=second_instrument_lot, Price=Second_instrument_pe_Price)

    if flag_nf=='BUY' and flag_nf_!='BUY' and check_squareoff_timing()==False:
        print('BUY ',first_instrument_name)
        squareoff_positions(client,first_instrument_name)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_ce_ScripCode), Qty=first_instrument_lot, Price=First_instrument_ce_Price)
        
    
    elif flag_nf=='SELL' and flag_nf_!='SELL' and check_squareoff_timing()==False:
        print('SELL ',first_instrument_name)
        squareoff_positions(client,first_instrument_name)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_pe_ScripCode), Qty=first_instrument_lot, Price=First_instrument_pe_Price)




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
