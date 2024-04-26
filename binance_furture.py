import ccxt
import numpy as np
import pandas as pd
import talib
import tkinter as tk
import threading
import time
import requests
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os

# Global variables
df = None
exchange = None
symbol = None
trading_active = False
current_price_label = None
current_price = None
canvas = None

# Function to save user data to file
def save_user_data(api_key, api_secret, line_token, symbol, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct):
    with open('user_data.txt', 'w') as file:
        file.write(f"API Key: {api_key}\n")
        file.write(f"API Secret: {api_secret}\n")
        file.write(f"Line Token: {line_token}\n")
        file.write(f"Symbol: {symbol}\n")
        file.write(f"Total USDT Percentage: {total_usdt_pct}\n")
        file.write(f"Amount Per Trade Percentage: {amount_per_trade_pct}\n")
        file.write(f"Leverage: {leverage}\n")
        file.write(f"Take Profit Percentage: {take_profit_pct}\n")
        file.write(f"Stop Loss Percentage: {stop_loss_pct}\n")
    print("User data saved successfully.")

def get_binance_balance(api_key, api_secret):
    # Initialize Binance exchange
    binance_exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret
    })
    
    try:
        # Load account balance
        balance = binance_exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        return usdt_balance
    except Exception as e:
        print("Error fetching Binance balance:", str(e))
        return None

def submit_form():
    # Get values from Entry widgets
    api_key = api_key_entry.get()
    api_secret = api_secret_entry.get()
    line_token = line_token_entry.get()
    symbol = symbol_entry.get()
    total_usdt_pct = total_usdt_pct_entry.get()
    amount_per_trade_pct = amount_per_trade_pct_entry.get()
    leverage = leverage_entry.get()
    take_profit_pct = take_profit_pct_entry.get()
    stop_loss_pct = stop_loss_pct_entry.get()
    
    # Save user data
    save_user_data(api_key, api_secret, line_token, symbol, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct)
    
    # Get Binance USDT balance
    binance_usdt_balance = get_binance_balance(api_key, api_secret)
    
    # Send LINE notification
    if binance_usdt_balance is not None:
        message = f"User data saved successfully.\nBinance USDT Balance: {binance_usdt_balance:.2f} USDT-M"
        send_line_notification(message, line_token)
        messagebox.showinfo("Success", message)
        
        # Start trading
        start_trading(api_key, api_secret, line_token, symbol, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct)
    else:
        message = "Failed to retrieve Binance USDT balance."
        send_line_notification(message, line_token)
        messagebox.showerror("Error", message)


def send_line_notification(message, line_token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': f'Bearer {line_token}'}
    data = {'message': message}
    response = requests.post(url, headers=headers, data=data)
    print("LINE Notification Response:", response.text)




# Function to update trading signals
def trading_signal(df):
    # ตัวอย่างการใช้ FLI เพื่อสร้างสัญญาณซื้อขาย
    df['sar'] = talib.SAR(df['high'], df['low'], acceleration=0.02, maximum=0.2)
    df['ema_75'] = talib.EMA(df['close'], timeperiod=75)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    
    # ตรวจสอบสัญญาณซื้อ
    df['Buy_Signal'] = np.where(
        (df['close'] > df['ema_75']) &
        (df['close'] < df['sar']) &
        (df['rsi'] < 30),  # เงื่อนไขตัวอย่างสำหรับสัญญาณซื้อ
        1,
        0
    )

    # ตรวจสอบสัญญาณขาย
    df['Sell_Signal'] = np.where(
        (df['close'] < df['ema_75']) &
        (df['close'] > df['sar']) &
        (df['rsi'] > 70),  # เงื่อนไขตัวอย่างสำหรับสัญญาณขาย
        1,
        0
    )

    return df

def check_buy_signal(df, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct):
    if df['Buy_Signal'].iloc[-1] == 1 and df['Buy_Signal'].iloc[1] != 1:
        current_price = df['close'].iloc[-1]
        # คำนวณจำนวนสินค้าที่จะซื้อโดยใช้ FLI
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        amount_to_buy = (usdt_balance * total_usdt_pct / 100) * leverage / current_price
        print(f"Buy Signal detected. Buy amount: {amount_to_buy:.2f} {symbol.split('/')[0]}")
        return True, amount_to_buy
    else:
        return False, None

def check_sell_signal(df):
    if df['Sell_Signal'].iloc[-1] == 1 and df['Sell_Signal'].iloc[1] != 1:
        print("Sell signal detected")
        return True
    else:
        return False

def execute_real_trade_single(action, amount, symbol, exchange, line_token):
    print(f"Executing {action} trade for {amount} {symbol} on exchange {exchange.id}")
    # Execute real trade (not implemented in this example)
    # Send notification via LINE
    message = f"Executing {action} trade for {amount} {symbol} on exchange {exchange.id}"
    send_line_notification(message, line_token)

def update_price_thread(ax, current_price_label, symbol, exchange):
    global canvas, current_price
    while True:
        try:
            ticker = exchange.fetchTicker(symbol)
            current_price = ticker['last']
            print("Current Price:", current_price)
            current_price_label.set_text(f"Current Price: {current_price:.2f}")

            df.loc[df.index[-1], 'close'] = current_price
            ax.lines[0].set_ydata(df['close'])

            canvas.draw()  
            print("Price Updated.")

            # Check trading signal every 30 minutes
            if time.time() - last_signal_check_time >= 1800:  # 1800 seconds = 30 minutes
                last_signal_check_time = time.time()
                message = check_trading_signal(df)
                if message:
                    send_line_notification(message, line_token)
                    print("Trading signal notification sent:", message)

            time.sleep(30)  # Update price every 30 seconds
        except Exception as e:
            print("Error updating price:", str(e))
def save_user_data(api_key, api_secret, line_token, symbol, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct):
    # เขียนข้อมูลลงในไฟล์ user_data.txt
    with open('user_data.txt', 'w') as file:
        file.write(f"API Key: {api_key}\n")
        file.write(f"API Secret: {api_secret}\n")
        file.write(f"Line Token: {line_token}\n")
        file.write(f"Symbol: {symbol}\n")
        file.write(f"Total USDT Percentage: {total_usdt_pct}\n")
        file.write(f"Amount Per Trade Percentage: {amount_per_trade_pct}\n")
        file.write(f"Leverage: {leverage}\n")
        file.write(f"Take Profit Percentage: {take_profit_pct}\n")
        file.write(f"Stop Loss Percentage: {stop_loss_pct}\n")
    print("User data saved successfully.")

def start_trading(api_key, api_secret, line_token, symbol, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct):
    global trading_active
    trading_active = True
    print("Trading started...")
    
    # เพิ่มเงื่อนไขตรวจสอบ trading_active ที่เริ่มต้นของฟังก์ชัน
    if trading_active:
        # Initialize exchange
        global exchange
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret
        })
        exchange.load_markets()
        usdt_m_available = 'USDTM' in [asset['asset'] for asset in exchange.fetch_balance()['info']['balances']]


        if not usdt_m_available:
            print("USDT-M is not available in Futures wallet. Please deposit USDT-M to your Futures account.")
            return
        
        # Set trading symbol
        global df
        df = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(df, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        # Calculate trading signals
        df = trading_signal(df)
        # Initialize position status
        position_open = False
        position_type = None
        position_amount = None
        position_open_price = None
        # Main trading loop
        while True:
            try:
                if trading_active:
                    # Check for buy signal
                    buy_signal, amount_to_buy = check_buy_signal(df, total_usdt_pct, amount_per_trade_pct, leverage, take_profit_pct, stop_loss_pct)
                    # Check for sell signal
                    sell_signal = check_sell_signal(df)
                    # Close position if sell signal detected
                    if position_open and sell_signal:
                        execute_real_trade_single('SELL', None, symbol, exchange, line_token)
                        position_open = False
                        position_type = None
                        position_amount = None
                        position_open_price = None
                    # Open long position if buy signal detected and no position is open
                    elif buy_signal and not position_open:
                        execute_real_trade_single('BUY', amount_to_buy, symbol, exchange, line_token)
                        position_open = True
                        position_type = 'LONG'
                        position_amount = amount_to_buy
                        position_open_price = df['close'].iloc[-1]
                    # Open short position if sell signal detected and no position is open
                    elif sell_signal and not position_open:
                        execute_real_trade_single('SELL', amount_to_buy, symbol, exchange, line_token)
                        position_open = True
                        position_type = 'SHORT'
                        position_amount = amount_to_buy
                        position_open_price = df['close'].iloc[-1]
                    # Update position if it's already open
                    elif position_open:
                        # Update position if take profit or stop loss condition met
                        if position_type == 'LONG' and df['close'].iloc[-1] >= position_open_price * (1 + take_profit_pct / 100) or df['close'].iloc[-1] <= position_open_price * (1 - stop_loss_pct / 100):
                            execute_real_trade_single('SELL', None, symbol, exchange, line_token)
                            position_open = False
                            position_type = None
                            position_amount = None
                            position_open_price = None
                        elif position_type == 'SHORT' and df['close'].iloc[-1] <= position_open_price * (1 - take_profit_pct / 100) or df['close'].iloc[-1] >= position_open_price * (1 + stop_loss_pct / 100):
                            execute_real_trade_single('BUY', None, symbol, exchange, line_token)
                            position_open = False
                            position_type = None
                            position_amount = None
                            position_open_price = None
                    time.sleep(300)  # Check signals every 5 minutes
                else:
                    break
            except Exception as e:
                print("Error in main loop:", str(e))
                time.sleep(60)


trading_active = False

user_data_file = "user_data.txt"
if os.path.exists(user_data_file):
        with open(user_data_file, "r") as file:
            user_data = file.readlines()
        try:
            default_api_key = user_data[0].split(":")[1].strip() # API Key
            default_api_secret = user_data[1].split(":")[1].strip() # API Secret
            default_line_token = user_data[2].split(":")[1].strip() # line_token
            default_symbol = user_data[3].split(":")[1].strip() # Trading Pair
            default_total_usdt_pct = user_data[4].split(":")[1].strip() # Total USDT
            default_amount_per_trade_pct = user_data[5].split(":")[1].strip() # Amount per Trade
            default_leverage = user_data[6].split(":")[1].strip() # Amount per Trade
            default_take_profit_pct = user_data[7].split(":")[1].strip() # Amount per Trade
            default_stop_loss_pct = user_data[8].split(":")[1].strip() # Amount per Trade
        except IndexError:
            print("Error: Insufficient data in user_data.txt file")
            default_api_key = ""
            default_api_secret = ""
            default_line_token = ""            
            default_symbol = ""
            default_total_usdt = ""
            default_amount_per_trade = ""
            default_total_usdt_pct = ""
            default_amount_per_trade_pct = ""
            default_leverage = ""
            default_take_profit_pct = ""
            default_stop_loss_pct = ""     
else:
    default_api_key = ""
    default_api_secret = ""
    default_line_token = ""    
    default_symbol = ""
    default_total_usdt = ""
    default_amount_per_trade = ""
    default_total_usdt_pct = ""
    default_amount_per_trade_pct = ""
    default_leverage = ""
    default_take_profit_pct = ""
    default_stop_loss_pct = "" 

# Function to stop trading
def stop_trading():
    global trading_active
    print("Trading stopped.")
    trading_active = False
# Function to load user data from file
def load_user_data():
    user_data = {}
    user_data_file = "user_data.txt"
    if os.path.exists(user_data_file):
        with open(user_data_file, "r") as file:
            lines = file.readlines()
            for line in lines:
                key, value = line.strip().split(": ")
                user_data[key] = value
    return user_data

# Main function
# Create main window
root = tk.Tk()
root.title("Enter User Data")

# Load user data from file
user_data = load_user_data()

# API Key
api_key_label = tk.Label(root, text="API Key:")
api_key_label.grid(row=0, column=0)
api_key_entry = tk.Entry(root)
api_key_entry.grid(row=0, column=1)
api_key_entry.insert(0, user_data.get("API Key", ""))  # Set default value

# API Secret
api_secret_label = tk.Label(root, text="API Secret:")
api_secret_label.grid(row=1, column=0)
api_secret_entry = tk.Entry(root)
api_secret_entry.grid(row=1, column=1)
api_secret_entry.insert(0, user_data.get("API Secret", ""))  # Set default value

# Line Token
line_token_label = tk.Label(root, text="Line Token:")
line_token_label.grid(row=2, column=0)
line_token_entry = tk.Entry(root)
line_token_entry.grid(row=2, column=1)
line_token_entry.insert(0, user_data.get("Line Token", ""))  # Set default value

# Symbol
symbol_label = tk.Label(root, text="Symbol:")
symbol_label.grid(row=3, column=0)
symbol_entry = tk.Entry(root)
symbol_entry.grid(row=3, column=1)
symbol_entry.insert(0, user_data.get("Symbol", ""))  # Set default value

# Total USDT Percentage
total_usdt_pct_label = tk.Label(root, text="Total USDT (%):")
total_usdt_pct_label.grid(row=4, column=0)
total_usdt_pct_entry = tk.Entry(root)
total_usdt_pct_entry.grid(row=4, column=1)
total_usdt_pct_entry.insert(0, user_data.get("Total USDT Percentage", ""))  # Set default value

# Amount per Trade Percentage
amount_per_trade_pct_label = tk.Label(root, text="Amount per Trade (%):")
amount_per_trade_pct_label.grid(row=5, column=0)
amount_per_trade_pct_entry = tk.Entry(root)
amount_per_trade_pct_entry.grid(row=5, column=1)
amount_per_trade_pct_entry.insert(0, user_data.get("Amount Per Trade Percentage", ""))  # Set default value

# Leverage
leverage_label = tk.Label(root, text="Leverage:")
leverage_label.grid(row=6, column=0)
leverage_entry = tk.Entry(root)
leverage_entry.grid(row=6, column=1)
leverage_entry.insert(0, user_data.get("Leverage", ""))  # Set default value

# Take Profit Percentage
take_profit_pct_label = tk.Label(root, text="Take Profit (%):")
take_profit_pct_label.grid(row=7, column=0)
take_profit_pct_entry = tk.Entry(root)
take_profit_pct_entry.grid(row=7, column=1)
take_profit_pct_entry.insert(0, user_data.get("Take Profit Percentage", ""))  # Set default value

# Stop Loss Percentage
stop_loss_pct_label = tk.Label(root, text="Stop Loss (%):")
stop_loss_pct_label.grid(row=8, column=0)
stop_loss_pct_entry = tk.Entry(root)
stop_loss_pct_entry.grid(row=8, column=1)
stop_loss_pct_entry.insert(0, user_data.get("Stop Loss Percentage", ""))  # Set default value

# Submit button
submit_button = tk.Button(root, text="Submit", command=submit_form)
submit_button.grid(row=9, column=0, columnspan=2)

# Start main event loop
root.mainloop()

if __name__ == "__main__":
    create_main_window()
    submit_form()


