import os
import time
from sched import scheduler

from dotenv import load_dotenv
from gate_api import Configuration, ApiClient, FuturesApi
from gate_api.models.futures_candlestick import FuturesCandlestick
from gate_api.models.futures_ticker import FuturesTicker

from service.discord_client import DiscordClient
from service.order_handler import OrderHandler
from service.renko_calculator import RenkoCalculator

# Load environment variables from .env file
load_dotenv()

GATE_URL_HOST_LIVE = os.getenv("GATE_URL_HOST_LIVE")
GATE_URL_HOST_TEST = os.getenv("GATE_URL_HOST_TEST")

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

SYMBOL_LIST = os.getenv("SYMBOL_LIST").split(",")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_COUNT = int(os.getenv("OHLCV_COUNT"))

LEVERAGE = int(os.getenv("LEVERAGE"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Dependencies initialization
gate_configuration = Configuration(
    host=GATE_URL_HOST_TEST,
    key=API_KEY,
    secret=SECRET_KEY,
)
gate_client = ApiClient(configuration=gate_configuration)
gate_futures_api = FuturesApi(api_client=gate_client)
discord_client = DiscordClient(url=DISCORD_WEBHOOK_URL)
order_handler = OrderHandler(
    gate_futures_api=gate_futures_api,
    discord_client=discord_client,
    symbol_list=SYMBOL_LIST,
    leverage=LEVERAGE,
)
renko_calculator = RenkoCalculator(
    symbol_list=SYMBOL_LIST,
    ohlcv_timeframe=OHLCV_TIMEFRAME,
    atr_period=ATR_PERIOD,
    ohlcv_count=OHLCV_COUNT,
    discord_client=discord_client,
    order_handler=order_handler,
)
data_stream_scheduler = scheduler(time.time, time.sleep)


def initialize_historical_data():
    discord_client.push_log_buffer("[Main] Renko trader started")
    for symbol in SYMBOL_LIST:
        candlestick_list: list[FuturesCandlestick] = (
            gate_futures_api.list_futures_candlesticks(
                settle="usdt",
                contract=symbol,
                limit=OHLCV_COUNT,
                interval=OHLCV_TIMEFRAME,
            )
        )
        renko_calculator.set_ohlcv_list_into_symbol_data_list(
            symbol=symbol, candlestick_list=candlestick_list
        )
    renko_calculator.set_brick_size_into_symbol_data_list()
    renko_calculator.set_renko_list_into_symbol_data_list()
    discord_client.push_log_buffer(
        f"[Main] Historial data loaded on {len(SYMBOL_LIST)} symbols: {str(SYMBOL_LIST)}"
    )
    discord_client.flush_log_buffer()
    for symbol in SYMBOL_LIST:
        renko_calculator.send_renko_plot_to_discord(symbol=symbol)


def main():
    initialize_historical_data()

    def fetch_then_process_ticker_data_scheduled():
        ticker_data_list: FuturesTicker = gate_futures_api.list_futures_tickers(
            settle="usdt"
        )
        renko_calculator.handle_new_ticker_data(ticker_data_list)
        data_stream_scheduler.enter(1, 1, fetch_then_process_ticker_data_scheduled)

    data_stream_scheduler.enter(1, 1, fetch_then_process_ticker_data_scheduled)
    data_stream_scheduler.run()


def test():
    pass


if __name__ == "__main__":
    main()
    # test()
