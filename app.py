from py5paisa import *
from datetime import *
import pytz
import time
import pandas as pd
import pyotp
import json

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


# MongoDB connection
mongo_uri = "mongodb+srv://knightearner:vQ8LqztvG31nkFIC@mongodb.ksex2.mongodb.net/?retryWrites=true&w=majority&appName=MongoDB"

# Create a new client and connect to the server
mongo_client = MongoClient(mongo_uri, server_api=ServerApi('1'))
db = mongo_client["app_db"]  # Database name
collection = db["switch"]  # Collection name


def get_switch_status():
    return True
    switch = collection.find_one({"name": "switch_status"})
    if switch:
        return switch["status"]
    else:
        return False



def get_BookedPL(client):
    BookedPL=0
    for pos in client.positions():
        BookedPL+=pos['BookedPL']
        BookedPL+=pos['MTOM']
    return BookedPL



def check_market_timing():
    if datetime.now(pytz.timezone('Asia/Kolkata')).hour == 9:
        if datetime.now(pytz.timezone('Asia/Kolkata')).minute >=16  and get_switch_status():
            return True
    elif datetime.now(pytz.timezone('Asia/Kolkata')).hour > 9 and datetime.now(pytz.timezone('Asia/Kolkata')).hour < 16 and get_switch_status():
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




def find_stoploss_diff(current_diff,stoploss_diff):
    if (current_diff-stoploss_diff)>0.01:
        stoploss_diff=stoploss_diff+(current_diff-stoploss_diff)*0.6
    return stoploss_diff

def date_IN_range(dt):
    # print(dt)
    for i in ['15:25:00', '15:30:00','09:15:00']:
        if i in dt:
            return True
    return False


def option_hedge(client):

    time_now = datetime.now(pytz.timezone('Asia/Kolkata'))
    print('Time Now = ',time_now)
    to_ = time_now.date() + timedelta(days=2)

    # Find the last Sunday
    days_since_sunday = (time_now.weekday() - 6) % 7
    last_sunday = time_now - timedelta(days=days_since_sunday)
    from_=last_sunday.strftime('%Y-%m-%d')
    
    timeframe='5m'
    # from_='2024-10-18'
    diff_threshold=0.01
    print(from_)

    # from_ = time_now.date() - timedelta(days=2)

    first_instrument_script=1333
    second_instrument_script=1594

    NF_lot=550
    BNF_lot=400

    first_instrument_lot=NF_lot
    second_instrument_lot=BNF_lot

    first_instrument_name='HDFCBANK'
    second_instrument_name='INFY'

    print('first_instrument_name = ',first_instrument_name)
    print('second_instrument_name = ',second_instrument_name)


    bnf = client.historical_data('N', 'C', second_instrument_script, timeframe, str(from_),str(to_))
    nf = client.historical_data('N', 'C', first_instrument_script, timeframe, str(from_),str(to_))

    common_Datetime=nf.merge(bnf, on='Datetime', how='inner').Datetime.values.tolist()

    bnf=bnf[bnf.Datetime.isin(common_Datetime)].reset_index(drop=True)
    nf=nf[nf.Datetime.isin(common_Datetime)].reset_index(drop=True)

    bnf_close=bnf.Close.values.tolist()
    nf_close=nf.Close.values.tolist()
    
    st_bnf=bnf_close[0]
    st_nf=nf_close[0]
    
    x_axis=bnf.Datetime.values.tolist()
    
    ls_bnf=[x/st_bnf for x in bnf_close]
    ls_nf=[x/st_nf for x in nf_close]
    
    diff_=[]
    for i in range(len(ls_bnf)):
        diff_.append(abs(ls_bnf[i]-ls_nf[i]))





    profit=[]
    pf=0

    nf_price=0
    bnf_price=0
    
    flag=''
    position_diff=0
    position_flag=False
    stoploss_diff=0.005
    final_list_2=[]

    for i in range(1,len(ls_bnf)-1):
        
        if date_IN_range(x_axis[i]):
            continue
        if ls_nf[i]>ls_bnf[i] and diff_[i]>0.01 and flag!='BUY':            
            if nf_price!=0 and bnf_price!=0:
                pf+=(bnf_close[i]-bnf_price)*BNF_lot+(nf_price-nf_close[i])*NF_lot
            nf_price=nf_close[i]
            bnf_price=bnf_close[i]
            flag='BUY'
            position_diff=diff_[i]
            stoploss_diff=position_diff-0.005

        elif ls_nf[i]<ls_bnf[i] and diff_[i]>0.01 and flag!='SELL':
            if nf_price!=0 and bnf_price!=0:
                pf+=(nf_close[i]-nf_price)*NF_lot+(bnf_price-bnf_close[i])*BNF_lot
            nf_price=nf_close[i]
            bnf_price=bnf_close[i]
            flag='SELL'
            position_diff=diff_[i]
            stoploss_diff=position_diff-0.005

        elif diff_[i]<stoploss_diff and flag!='':
            
            if flag=='SELL':            
                if nf_price!=0 and bnf_price!=0:
                    pf+=(bnf_close[i]-bnf_price)*BNF_lot+(nf_price-nf_close[i])*NF_lot
            elif flag=='BUY':
                if nf_price!=0 and bnf_price!=0:
                    pf+=(nf_close[i]-nf_price)*NF_lot+(bnf_price-bnf_close[i])*BNF_lot   
            nf_price=0
            bnf_price=0
            flag=''
            
        if flag=='SELL':            
            if nf_price!=0 and bnf_price!=0:
                profit.append(pf+(bnf_close[i]-bnf_price)*BNF_lot+(nf_price-nf_close[i])*NF_lot)
        elif flag=='BUY':
            if nf_price!=0 and bnf_price!=0:
                profit.append(pf+(nf_close[i]-nf_price)*NF_lot+(bnf_price-bnf_close[i])*BNF_lot)     
        
        stoploss_diff=find_stoploss_diff(diff_[i],stoploss_diff)        
    
        window_size=20
        numbers_series = pd.Series(profit)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean()
        moving_averages_list = moving_averages.tolist()
        final_list = moving_averages_list[window_size - 1:]

        final_list_2=[0]*window_size
        final_list_2.extend(final_list)
        



    # variable_object=read_json()

    # profit=variable_object['profit']
    # pf=variable_object['pf']
    # nf_price=variable_object['nf_price']
    # bnf_price=variable_object['bnf_price']
    # flag=variable_object['flag']
    # position_diff=variable_object['position_diff']
    # position_flag=variable_object['position_flag']
    # stoploss_diff=variable_object['stoploss_diff']
    # final_flag=variable_object['final_flag']

    skip_flag= False
    if date_IN_range(x_axis[-2]):
        skip_flag= True





    final_flag=''
    if len(profit)>2:
        if profit[-2]>final_list_2[-2]:
            if flag=='BUY':
                final_flag='BUY'
                position_flag=True
            if flag=='SELL':
                final_flag='SELL'
                position_flag=True

        elif profit[-2]<final_list_2[-2] and position_flag:

            if flag=='SELL':
                final_flag=''
            elif flag=='BUY':
                final_flag=''
            position_flag=False




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


    _flag=''
    if final_flag=='BUY':
        _flag='First'
    elif final_flag=='SELL':
        _flag='Second'
    else:
        _flag='Square Off All Positions'
        squareoff_all_positions(client)
     


    open_flag=''
    for pos in client.positions():
        # print(pos)
        if first_instrument_name in pos['ScripName'] and 'CE'in pos['ScripName'] and pos['NetQty']>0:
            open_flag='First'
            break
        elif second_instrument_name in pos['ScripName'] and 'CE'in pos['ScripName'] and pos['NetQty']>0:
            open_flag='Second'
            break
        else:
            open_flag='No_Open_Positions'
    
    print('------------------------------------------------------------',flush=True)
            
    print('flag = ',flag,flush=True)
    print('open_flag = ',open_flag,flush=True)
    print('_flag = ',_flag,flush=True)
    print(ls_nf[-5:],flush=True)
    print(ls_bnf[-5:],flush=True)
    print(diff_[-5:],flush=True)
    print(len(final_list_2),flush=True)
    print(len(profit),flush=True)
    print(len(bnf_close),flush=True)
    print(final_list_2[-5:],flush=True)
    print(profit[-5:],flush=True)

    print('------------------------------------------------------------',flush=True)

    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(First_instrument_ce_ScripCode)}]
    First_instrument_ce_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(First_instrument_pe_ScripCode)}]
    First_instrument_pe_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1


    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(Second_instrument_ce_ScripCode)}]
    Second_instrument_ce_Price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    req_list_ = [{"Exch": "N", "ExchType": "D", "ScripCode": str(Second_instrument_pe_ScripCode)}]
    Second_instrument_pe_price=(client.fetch_market_feed_scrip(req_list_)['Data'][0]['LastRate'])+1

    # print(_flag,open_flag,skip_flag)
    
    if _flag=='First' and open_flag !='First' and skip_flag==False:
        print('First Long start')
        # client.squareoff_all()
        squareoff_all_positions(client)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_ce_ScripCode), Qty=first_instrument_lot, Price=First_instrument_ce_Price)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(Second_instrument_pe_ScripCode), Qty=second_instrument_lot, Price=Second_instrument_pe_price)
        
    if _flag=='Second' and open_flag!='Second' and skip_flag==False:
        print('Second Long start')
        # client.squareoff_all()
        squareoff_all_positions(client)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(Second_instrument_ce_ScripCode), Qty=second_instrument_lot, Price=Second_instrument_ce_Price)
        client.place_order(OrderType='B', Exchange='N', ExchangeType="D", ScripCode=int(First_instrument_pe_ScripCode), Qty=first_instrument_lot, Price=First_instrument_pe_Price)
        

    BookedPL=get_BookedPL(client)
    print('------------------------------------------')
    print('BookedPL = ',BookedPL,flush=True)
    print('------------------------------------------')
    # insert_val(BookedPL,first_instrument_Close,second_instrument_Close)
    

    # _variable_object={
    # "profit":profit,
    # "pf":pf,
    # "nf_price":nf_price,
    # "bnf_price":bnf_price,  
    # "flag":flag,
    # "position_diff":position_diff,
    # "position_flag":position_flag,
    # "stoploss_diff":stoploss_diff,
    # "final_flag":final_flag,
    # 'last_candle':x_axis[-2]
    # }

    print('=====================================================')
    # print(_variable_object)
    print(bnf_close[-2],nf_close[-2],flush=True)
    print('=====================================================')




from flask import Flask
import threading
import time

app = Flask(__name__)

# Define the function for the infinite loop
def infinite_loop():
    while True:
        day_number=datetime.now(pytz.timezone('Asia/Kolkata')).weekday()
        print('Loop Time ', datetime.now(pytz.timezone('Asia/Kolkata')),flush=True)
        time.sleep(10)
        if check_market_timing() and (day_number not in [5,6]) and get_switch_status():
            broker = broker_login()
            while True:
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

# Define a simple route for the Flask app
@app.route('/')
def index():
    return "Flask is running. The infinite loop is also running in the background."

if __name__ == '__main__':
    # Start the infinite loop in a separate thread before the app runs
    start_infinite_loop()
    app.run(debug=True)
