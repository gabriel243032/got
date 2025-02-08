import time
import requests
import telegram
import pandas as pd
from binance.client import Client
import threading  # Importa threading

# Configura tu bot de Telegram
TELEGRAM_TOKEN = "8193748398:AAFsrOowltkg2qKdR_ldv0yp85uNfMjfnDk"
CHAT_ID = "6421416066"
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Configura tu API de Binance
BINANCE_API_KEY = "PT0lwmB6XdsTAKItYfe7ICsefvnzWU2qF4JbxlKpenLaMcbv6GRgzR4FyT4bcRsn"
BINANCE_API_SECRET = "YTaChgFlxULdEo42TiG4fjEdl5uFlhJSQbME5eBR4F6fjIZuku8XyVNICk7Jiin9"
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# 🔹 Umbrales de estrategia
PERCENT_CHANGE_THRESHOLD = 1.0  # Cambio del 1% en 5 minutos
EMA_SHORT = 9
EMA_LONG = 21
RSI_PERIOD = 14
VOLUME_THRESHOLD = 1.5  # Volumen debe aumentar 1.5x en comparación con el promedio

def send_telegram_message(message):
    """Envía un mensaje de alerta a Telegram"""
    bot.send_message(chat_id=CHAT_ID, text=message)

def get_futures_symbols():
    """Obtiene todos los pares de trading de futuros en Binance"""
    exchange_info = client.futures_exchange_info()
    return [s['symbol'] for s in exchange_info['symbols']]

def calculate_indicators(df):
    """Calcula EMA, RSI y volumen"""
    df["ema9"] = df["close"].ewm(span=EMA_SHORT, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=EMA_LONG, adjust=False).mean()
    
    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # Volumen promedio
    df["avg_volume"] = df["volume"].rolling(RSI_PERIOD).mean()
    
    return df

def get_klines(symbol):
    """Obtiene datos de velas de 5 minutos"""
    klines = client.futures_klines(symbol=symbol, interval="5m", limit=50)
    df = pd.DataFrame(klines, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "trades", "taker_base_vol", "taker_quote_vol", "ignore"
    ])
    df = df.astype(float)
    return df

def analyze_market(symbol):
    """Analiza el mercado y busca señales de entrada"""
    df = get_klines(symbol)
    df = calculate_indicators(df)

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    percent_change = ((last_row["close"] - prev_row["close"]) / prev_row["close"]) * 100
    volume_increase = last_row["volume"] > last_row["avg_volume"] * VOLUME_THRESHOLD

    # Señal de compra
    if (
        last_row["ema9"] > last_row["ema21"] and 
        prev_row["ema9"] <= prev_row["ema21"] and  # Cruce alcista
        last_row["rsi"] < 70 and  # Evita sobrecompra
        percent_change >= PERCENT_CHANGE_THRESHOLD and 
        volume_increase  # Confirmación de volumen
    ):
        message = f"🟢 **Señal de COMPRA en {symbol}**\n📈 Cambio: {percent_change:.2f}%\n📊 RSI: {last_row['rsi']:.2f}\n📉 EMA9 > EMA21\n🔥 Volumen alto"
        send_telegram_message(message)

    # Señal de venta
    if (
        last_row["ema9"] < last_row["ema21"] and 
        prev_row["ema9"] >= prev_row["ema21"] and  # Cruce bajista
        last_row["rsi"] > 30 and  # Evita sobreventa
        percent_change <= -PERCENT_CHANGE_THRESHOLD and 
        volume_increase  # Confirmación de volumen
    ):
        message = f"🔴 **Señal de VENTA en {symbol}**\n📉 Cambio: {percent_change:.2f}%\n📊 RSI: {last_row['rsi']:.2f}\n📈 EMA9 < EMA21\n🔥 Volumen alto"
        send_telegram_message(message)

def monitor_market(symbol):
    """Monitorea cada par en un hilo"""
    while True:
        try:
            analyze_market(symbol)
            time.sleep(300)  # 5 minutos
        except Exception as e:
            print(f"Error en {symbol}: {e}")
            time.sleep(10)

if __name__ == "__main__":
    symbols = get_futures_symbols()
    print(f"🔍 Monitoreando {len(symbols)} pares de futuros...")

    # Crear hilos para cada símbolo (máximo 20 para evitar sobrecarga)
    max_threads = 20
    for i, symbol in enumerate(symbols):
        if i >= max_threads:
            break  # Evitar sobrecarga
        t = threading.Thread(target=monitor_market, args=(symbol,))
        t.start()