import math
import re
import time
from typing import Union, Optional, Dict
import configs
from binance.um_futures import UMFutures
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from logger import logger
from decimal import Decimal
import requests


def get_binance_trading_pair_info(symbol):
    base_url = "https://api.binance.com/api/v3/exchangeInfo"
    response = requests.get(base_url)
    data = response.json()
    symbol_info = next((s for s in data['symbols'] if s['symbol'] == symbol), None)
    return symbol_info


def get_symbol(symbol):
    return client.futures_symbol_ticker(str(symbol))


def get_contract_precision(symbol):
    exchange_info = client.futures_exchange_info()
    for symbol_info in exchange_info['symbols']:
        if symbol_info['symbol'] == symbol:
            precision = int(symbol_info['quantityPrecision'])
            return precision
    return None


def round_to_precision(number, precision):
    return math.floor(number * 10 ** precision) / 10 ** precision


# regex pattern to extract futures-order information
futures_pattern = r"(\w+)\/(\w+)\s*(LONG|SHORT)\s*🛑\s*Leverage\s*(\d+x)\s*Entries\s*(\d+\.\d+)\s*Target\s*1\s*(" \
                  r"\d+\.\d+)\s*Target\s*2\s*(\d+\.\d+)\s*Target\s*3\s*(\d+\.\d+)\s*Target\s*4\s*(" \
                  r"\d+\.\d+)\s*Target\s*5\s*(\d+\.\d+)\s*SL\s*(\d+\.\d+)"

# regex pattern to extract spot-order information
spot_pattern = r"\$(\w+)\/(\w+)[\s\S]+?Buy Price\s+:\s+([\d.]+)"

scientific_pattern = r'^[-+]?[0-9]*\.?[0-9]+[eE][-+]?[0-9]+$'

# Binance API keys
api_key = configs.BINANCE_API_KEY
api_secret = configs.BINANCE_API_SECRET
risk_percent = float(configs.RISK_PERCENTAGE)
buy_percentage = configs.BUY_PERCENTAGE
client = Client(api_key=api_key, api_secret=api_secret)
client2 = UMFutures(key=api_key, secret=api_secret)

def cancel_order(symbol):
    client.futures_cancel_all_open_orders(symbol=symbol)


def price(symbol):
    return client.futures_symbol_ticker(symbol=symbol)["price"]


def round_step_size(quantity: Union[float, Decimal], step_size: Union[float, Decimal]) -> float:
    """Rounds a given quantity to a specific step size

    :param quantity: required
    :param step_size: required

    :return: decimal
    """
    quantity = Decimal(str(quantity))
    return float(quantity - quantity % Decimal(str(step_size)))


def get_tick_size(symbol: str) -> float:
    info = client.futures_exchange_info()

    for symbol_info in info['symbols']:
        if symbol_info['symbol'] == symbol:
            for symbol_filter in symbol_info['filters']:
                if symbol_filter['filterType'] == 'PRICE_FILTER':
                    return float(symbol_filter['tickSize'])


def get_rounded_price(symbol: str, price: float):
    return round_step_size(price, get_tick_size(symbol))


def open_orders(symbol):
    return client.get_open_orders(symbol=symbol)


def open_orders_futures(symbol):
    return client.futures_get_open_orders(symbol=symbol)


# Function to place a Spot trade
def place_spot_trade(pair, side, quantity):
    logs = open("file.txt", "a+")
    market_price = float(client.get_symbol_ticker(symbol=pair)["price"])
    ext = [i["quantityPrecision"] for i in client.futures_exchange_info()["symbols"] if
           i["pair"] == pair][0]
    quan = round((quantity * buy_percentage) / market_price, ext)
    print(quan, quantity / market_price, quantity)
    try:
        order = client.create_order(
            symbol=pair,
            side=side,
            type="MARKET",
            quantity=quan
        )
        logger.info(f"Placed {side} order for {pair} at price {market_price}")
        print(order)
        logs.write(str(order) + "\n")
    except Exception as e:
        logger.info(f"Error placing {side} order for {pair}: {str(e)}")
    take_profit_price = market_price * (1 + risk_percent) if side == "BUY" else market_price * (
            1 - risk_percent)
    stop_loss_price = market_price * (1 - risk_percent) if side == "BUY" else market_price * (
            1 + risk_percent)
    print(take_profit_price, "take profit")
    print(stop_loss_price, "stop loss")
    logs.write(str(take_profit_price) + "\n")
    logs.write(str(stop_loss_price) + "\n")
    while True:
        time.sleep(0.5)
        try:
            if side == "BUY":
                nowprice = float(client.get_symbol_ticker(symbol=pair)["price"])
                print(nowprice)
                if (take_profit_price <= nowprice) or (stop_loss_price >= nowprice):
                    sell = client.create_order(
                        symbol=pair,
                        side="SELL",
                        type="MARKET",
                        quantity=quan
                    )
                    print(sell)
                    logs.write(str(sell) + "\n")
                    print("Order close")
                    break
            else:
                nowprice = float(client.futures_symbol_ticker(symbol=pair)['price'])
                print(nowprice)

                if (take_profit_price >= nowprice) or (stop_loss_price <= nowprice):
                    sell = client.create_order(
                        symbol=pair,
                        side="SELL",
                        type="MARKET",
                        quantity=quan
                    )
                    print(sell)
                    logs.write(str(sell) + "\n")
                    print("Order close")
                    break
        except Exception as e:
            print(e)
            pass
    logs.close()
    return order


# function to place a futures trade
def place_future_order(symbol, side, entry, leverage):
    # Calculate the quantity to trade based on the account balance and the percentage risk
    logs = open("file.txt", "a+")
    print(client2.balance())

    balance = float(list(i["balance"] for i in client2.balance() if i["asset"] == "USDT")[0])
    ticker = client.futures_symbol_ticker(symbol=symbol)
    market_price = float(ticker['price'])
    print("Your Balance is ", balance)
    print(buy_percentage)
    unsafe_quantity = (balance * buy_percentage) * leverage
    quantity = float(math.floor(unsafe_quantity))
    ext = [i["quantityPrecision"] for i in client.futures_exchange_info()["symbols"] if
           i["pair"] == symbol][0]
    quan = round((quantity * buy_percentage) / market_price, ext)

    print(quantity, unsafe_quantity, quan)
    try:
        client.futures_change_margin_type(marginType="ISOLATED", symbol=symbol)
    except:
        pass
    positionSide = "BOTH"
    # positionSide = "SHORT" if side == "SELL" else "LONG"
    print(side)
    order = client.futures_create_order(
        side=side,
        type=FUTURE_ORDER_TYPE_MARKET,
        # timeInForce=TIME_IN_FORCE_GTC,
        quantity=quan,
        leverage=leverage,
        # price=market_price,
        symbol=symbol
        # stopPrice=stop_loss_price
    )
    take_profit_price = market_price * (1 + risk_percent * 1.1 / leverage) if side == "BUY" else market_price * (
            1 - (risk_percent) * 1.1 / leverage)
    stop_loss_price = market_price * (1 - risk_percent / leverage) if side == "BUY" else market_price * (
            1 + risk_percent / leverage)
    print(take_profit_price)
    print(stop_loss_price)
    print(f"Order placed successfully: {order}")
    print("Take Profit", take_profit_price)
    print("Stop Loss", stop_loss_price)
    logs.write(str(order) + "\n")
    logs.write(str(take_profit_price) + "\n")
    logs.write(str(stop_loss_price) + "\n")
    orderId = order["orderId"]
    order_status = client.futures_get_order(symbol=symbol, orderId=orderId)

    while True:
        time.sleep(0.5)
        try:
            if side == "BUY":
                nowprice = float(client.futures_symbol_ticker(symbol=symbol)['price'])
                print(nowprice)
                logs.write(str(nowprice) + "\n")
                if (take_profit_price <= nowprice) or (stop_loss_price >= nowprice):
                    while True:
                        try:
                            sell = client.futures_create_order(
                                side="SELL",
                                type=FUTURE_ORDER_TYPE_MARKET,
                                # timeInForce=TIME_IN_FORCE_GTC,
                                quantity=quan,
                                leverage=leverage,
                                # price=market_price,
                                symbol=symbol,
                                # stopPrice=stop_loss_price
                            )
                            break
                        except Exception as e:
                            print(e)
                            pass

                    print("Order close")
                    print(sell)
                    logs.write(str(sell) + "\n")
                    logs.write(str(take_profit_price) + "\n")
                    logs.write(str(stop_loss_price) + "\n")
                    break
            else:
                nowprice = float(client.futures_symbol_ticker(symbol=symbol)['price'])
                print(nowprice)
                logs.write(str(nowprice) + "\n")

                if (take_profit_price >= nowprice) or (stop_loss_price <= nowprice):
                    while True:
                        try:
                            sell = client.futures_create_order(
                                side="BUY",
                                type=FUTURE_ORDER_TYPE_MARKET,
                                # timeInForce=TIME_IN_FORCE_GTC,
                                quantity=quan,
                                leverage=leverage,
                                # price=market_price,
                                symbol=symbol,
                                # stopPrice=stop_loss_price
                            )
                            break
                        except Exception as e:
                            print(e)
                            pass
                    logs.write(str(sell) + "\n")
                    logs.write(str(take_profit_price) + "\n")
                    logs.write(str(stop_loss_price) + "\n")
                    print("Order close")
                    print(sell)
                    break
        except:
            pass
    logs.close()
    # print(f"Take profit order placed successfully: {take_profit_order}")

    return print(f"Placed {side} order for {symbol} at {market_price}.")
