
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
