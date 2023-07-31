"""The main app"""
import re
import sys
import time
import traceback

from binance.enums import *
from telethon import TelegramClient, events
from logger import logger
from binance_bot import place_spot_trade, place_future_order, get_symbol, client as bc
from message_patterns import spot_pattern
from utils import extract_match, emit_collect_success, match_signal, verify_symbol
from intro import introduction
import configs
# Telegram API keys
api_id = configs.TELEGRAM_APP_ID
api_hash = configs.TELEGRAM_APP_HASH
phone_number = configs.PHONE_NUMBER
channel_name = configs.CHANNEL_NAME
risk_percent = configs.RISK_PERCENTAGE
buy_percentage =  configs.BUY_PERCENTAGE
use_stop_loss =  configs.USE_STOP_LOSS

# Connect to the Telegram channel
client = TelegramClient(phone_number, api_id, api_hash)
client.start()
# ========================
#  INTRODUCTION
introduction()
# ========================


@client.on(events.NewMessage(chats=[int(channel_name)]))
async def handle_spot_message(event):
    message = event.message.message

    if "Exchange:   BINANCE" in message:
        logger.info("===== Handling Spot Signal Messages =====")
        # Parse the signal from the message

        symbol = str(str(message).split("$")[1].split()[0]).upper()
        print(symbol)
        targets = re.findall(r"%(\d+).*?([\d.]+)", message)
        if targets:
            # Place a Binance buy order
            balance = bc.get_asset_balance(asset="USDT")
            print(balance)
            logger.info(f"Current Asset balance: {balance}")
            # run
            if balance is not None:
                quantity = round(
                    float(balance["free"]), 0
                )  # Buy 10% of available balance
                place_spot_trade(
                    pair=symbol,
                    side="BUY",
                    quantity=quantity,
                )
    elif "1️⃣" in str(message):
        logger.info("===== Handling Spot Signal Messages =====")
        # Parse the signal from the message

        symbol = str(message).split("$")[1].split()[0].replace("/", "").upper()
        print(symbol)
        balance = bc.get_asset_balance(asset="USDT")
        print(balance)
        logger.info(f"Current Asset balance: {balance}")
        # run
        if balance is not None:
            quantity = round(
                float(balance["free"]), 0
            )  # Buy 10% of available balance
            place_spot_trade(
                pair=symbol,
                side="BUY",
                quantity=quantity,
            )

@client.on(events.NewMessage(chats=[int(channel_name)]))
async def handle_signal_message(event):
# Define the regex pattern to extract the symbol, leverage, entries, targets, and stop loss
    # Define the possible keywords for a signal
    keywords = ["SHORT", "LONG", "🛑", "✳️"]

    # Check if the message contains any of the keywords
    if any(keyword in event.raw_text for keyword in keywords):
        logger.info("===== Handling Futures Signal Messages =====")

        # Extract the symbol, leverage, side, entry price, and stop loss price from the signal
        symbol = None
        leverage = None
        side = None
        entry = None
        signal_stop_loss = None
        signal_message = event.raw_text.split("\n") 
        for line in signal_message:
            if any(keyword in line for keyword in keywords):
                symbol = line.split()[0].replace("/", "").upper()
                try:
                    entry = float(signal_message[2].split(" ")[1])
                except ValueError:
                    entry = float(re.findall(r'\d+\.\d+',signal_message[2])[0])
                try:
                    leverage = float(signal_message[1].split(" ")[1].replace("x", ""))
                except ValueError:
                    leverage = float(re.findall(r'\d+\.\d+',signal_message[1])[0])
                if "SHORT" in line:
                    side = "SELL"
                if "LONG" in line:
                    side = "BUY"
                if "SL" or "Sl" in line:
                    if use_stop_loss:
                        signal_stop_loss = float(signal_message[-1].split(" ")[1])

        emit_collect_success(symbol, side, entry, leverage, type="Complex Version")
    else:
        keywords = ["short", "long"]
        logger.info("===== Handling Futures Signal Messages =====")
        symbol = None
        leverage = None
        side = None
        entry = None
        signal_stop_loss = None
        signal_take_profit = None
        signal_message = event.raw_text.split(" ")
        for line in signal_message:
            if any(keyword in line for keyword in keywords):
                try:
                    symbol: str = signal_message[0] + "USDT"
                    get_symbol(symbol)
                except:
                    symbol: str = signal_message[1] + "USDT"

                entry = float(signal_message[2])
                leverage = float(20)
                if "short" in line:
                    side = "SELL"
                elif "long" in line:
                    side = "BUY"
        emit_collect_success(symbol, side, entry, leverage, type="Minimal Version")

        # Place the limit order with the extracted information
    order = None
    if not verify_symbol(bc, symbol):
        return
    print(f"Passed Colection, creating order now  for {symbol}...")
    try:
        place_future_order(
            symbol=symbol,
            side=side,
            entry=entry,
            leverage=leverage)
    except Exception as e:
        print(e)
        print(traceback.format_exc())


    # if order is not None:
    #     logger.info(f"Placed limit {side.lower()} futures order")

    #     # Set up the loop to check the order status and update the take profit and stop loss orders
    #     while True:
    #         print("Getting the current order status")
    #         # Get the current order status
    #         if order is not None:
    #             # If the order has been filled or canceled, break the loop
    #             if order_status["status"] == "FILLED" or order_status["status"] == "CANCELED":
    #                 break
    #             # Define the take profit and stop loss prices
    #             take_profit_price = market_price * (1 + risk_percent) if side == "BUY" else market_price * (1 - risk_percent)
    #             stop_loss_price = signal_stop_loss if signal_stop_loss is not None else market_price * (1 - risk_percent) if side == "BUY" else market_price * (1 - risk_percent)

    #             # # Update the take profit and stop loss orders if necessary
    #             if order_status["status"] == "NEW":
    #                 print(f"Updating order for {symbol}, setting stop loss at {stop_loss_price} and take profit at {take_profit_price}")
    #                 # Get the current timestamp
    #                 timestamp = bc.futures_time()["serverTime"]
    #                 stop_loss_order = bc.futures_create_order(
    #                 symbol=symbol,
    #                 side=side,
    #                 positionSide="SHORT",
    #                 price=market_price,
    #                 type=FUTURE_ORDER_TYPE_STOP,
    #                 timeInForce=TIME_IN_FORCE_GTC,
    #                 stopPrice=stop_loss_price,
    #                 quantity=quantity,
    #                 # reduceOnly=True,
    #                 workingType="MARK_PRICE",
    #                 priceProtect=True,
    #                 newOrderRespType=ORDER_RESP_TYPE_RESULT,
    #                 timestamp=timestamp
    #                 )
    #                 take_profit_order = bc.futures_create_order(
    #                 symbol=symbol,
    #                 side=side,
    #                 price=market_price,
    #                 type=FUTURE_ORDER_TYPE_TAKE_PROFIT,
    #                 positionSide="LONG",
    #                 timeInForce=TIME_IN_FORCE_GTC,
    #                 stopPrice=take_profit_price,
    #                 quantity=quantity,
    #                 # reduceOnly=True,
    #                 workingType="MARK_PRICE",
    #                 priceProtect=True,
    #                 newOrderRespType=ORDER_RESP_TYPE_RESULT,
    #                 timestamp=timestamp
    #                 )
    #                 if stop_loss_order and take_profit_order is not None:
    #                     logger.info(f"Placed limit futures {side.lower()} order with {stop_loss_price} stop loss and {take_profit_price} take profit for {symbol}")

    #         logger.info("No available futures order(s)")
            # break
# Start the event loop
with client:
    client.run_until_disconnected()

