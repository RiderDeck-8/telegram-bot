import nest_asyncio
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, JobQueue
import yfinance as yf
from telegram.error import NetworkError, TelegramError
import matplotlib.pyplot as plt
import io
import logging
import json
import os
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error



# Aplicar nest_asyncio para permitir el uso de asyncio en un entorno con un loop de eventos ya existente
nest_asyncio.apply()

# Token del bot de Telegram
TOKEN = '7542207567:AAHdO7BcPyHxSDSICPHOopzwprzaqtpD8HM'

# Diccionario para almacenar portafolios de usuarios y alertas
portfolios = {}
alerts = {}
profits = {}

# Ruta del archivo JSON
ALERTS_FILE = 'alerts.json'
PORTFOLIOS_FILE = 'portfolios.json'
PROFITS_FILE = 'profits.json'

def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_json_file(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# Cargar datos al iniciar el bot
alerts = load_json_file(ALERTS_FILE)
portfolios = load_json_file(PORTFOLIOS_FILE)
profits = load_json_file(PROFITS_FILE)

# Función para iniciar el bot
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "¡Hola! Soy tu bot financiero.\n"
        "Usa los siguientes comandos:\n"
        "/stock [TICKER] - Obtener información de una acción.\n"
        "/alert [TICKER] [comprar/vender] [PRECIO] - Configurar una alerta para un ticker cuando alcance un precio específico.\n"
        "/editalert [TICKER] [comprar/vender] [NUEVO PRECIO] - Editar Alertas.\n"
        "/deletealert [TICKER] - Eliminar Alertas.\n"
        "/buy [TICKER] [CANTIDAD] - Comprar acciones.\n"
        "/sell [TICKER] [CANTIDAD] - Vender acciones.\n"
        "/profits - Ver tu ganancias o perdidas.\n"
        "/portfolio - Ver tu portafolio.\n"
        "/listalerts - Listar tus alertas.\n"
        "/grafica - Creacion de graficas ['1d', '1mo', '3mo', '6mo', '1y', '5y']."
        
    )

# Función para manejar el comando /help
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Aquí tienes una lista de los comandos disponibles:\n\n"
        "/start - Iniciar la interacción con el bot.\n"
        "/stock [TICKER] - Obtener información actual sobre una acción específica.\n"
        "/alert [TICKER] [comprar/vender] [PRECIO] - Configurar una alerta para un ticker cuando alcance un precio específico.\n"
        "/editalert [TICKER] [comprar/vender] [NUEVO PRECIO] - Editar Alertas.\n"
        "/deletealert [TICKER] - Eliminar Alertas.\n"
        "/buy [TICKER] [CANTIDAD] - Comprar una cantidad específica de acciones de un ticker.\n"
        "/sell [TICKER] [CANTIDAD] - Vender una cantidad específica de acciones de un ticker.\n"
        "/profits - Ver tu ganancias o perdidas.\n"
        "/portfolio - Ver el estado actual de tu portafolio de inversiones.\n"
        "/grafica - Creacion de graficas ['1d', '1mo', '3mo', '6mo', '1y', '5y'].\n"
        "/listalerts - Listar tus alertas.\n"
    )

# Función para obtener la tasa de cambio USD/MXN
def get_usd_to_mxn_rate():
    exchange_rate = yf.Ticker('USDMXN=X')
    rate = exchange_rate.history(period='1d')['Close'].iloc[-1]
    print(rate)
    return rate

# Modificación en la función stock_info para mostrar precios en MXN
async def stock_info(update: Update, context: CallbackContext):
    ticker = ' '.join(context.args).upper()
    if not ticker:
        await update.message.reply_text("Por favor proporciona un ticker de acción. Ejemplo: /stock AAPL")
        return

    await update.message.reply_text(f"Buscando información para el ticker: {ticker}")

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")

        if not data.empty:
            price_usd = data['Close'].iloc[-1]
            high_usd = data['High'].max()
            low_usd = data['Low'].min()
            volume = data['Volume'].sum()

            # Convertir los precios a MXN
            usd_to_mxn = get_usd_to_mxn_rate()
            price_mxn = price_usd * usd_to_mxn
            high_mxn = high_usd * usd_to_mxn
            low_mxn = low_usd * usd_to_mxn

            response = (
                f"**{ticker}**\n"
                f"Precio actual: ${price_mxn:.2f} MXN\n"
                f"Máximo del día: ${high_mxn:.2f} MXN\n"
                f"Mínimo del día: ${low_mxn:.2f} MXN\n"
                f"Volumen: {volume}\n"
            )
        else:
            response = f"No se pudo obtener información para el ticker: {ticker}"

    except Exception as e:
        response = f"Error al obtener información del ticker {ticker}: {e}"

    await update.message.reply_text(response, parse_mode='Markdown')

async def predict_future_prices(ticker, days=30):
    # Descargar datos históricos
    stock = yf.Ticker(ticker)
    data = stock.history(period='1y')

    # Asegurarse de que hay datos suficientes
    if data.empty or len(data) < 30:
        return None

    # Preparar datos para el modelo
    data['Date'] = data.index
    data['Day'] = (data.index - data.index[0]).days
    X = data[['Day']]
    y = data['Close']

    # Dividir en datos de entrenamiento y prueba
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # Crear y entrenar el modelo
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Predecir precios futuros
    future_days = np.arange(len(data), len(data) + days).reshape(-1, 1)
    future_prices = model.predict(future_days)

    # Evaluar el modelo
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    
    # Mostrar hiperparámetros del modelo
    coef = model.coef_[0]
    intercept = model.intercept_

    return future_prices, mse, coef, intercept

async def predict(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /predict [TICKER] [DÍAS]. Ejemplo: /predict AAPL 30")
        return

    ticker = context.args[0].upper()
    try:
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Número de días inválido. Debe ser un número entero.")
        return

    # Predecir precios futuros
    future_prices, mse, coef, intercept = await predict_future_prices(ticker, days)

    if future_prices is None:
        await update.message.reply_text(f"No se pudo obtener datos para el ticker: {ticker} o no hay suficientes datos.")
        return

    # Preparar el mensaje con los resultados
    response = f"Predicción de precios para {ticker} para los próximos {days} días:\n"
    for i, price in enumerate(future_prices[-days:]):
        response += f"Día {i + 1}: ${price:.2f}\n"

    response += (
        f"\nPrecisión del modelo: Error cuadrático medio (MSE): {mse:.2f}\n"
        f"Hiperparámetros del modelo:\n"
        f"Coeficiente (pendiente): {coef:.4f}\n"
        f"Intercepto: {intercept:.4f}"
    )
    
    await update.message.reply_text(response)

# Modificación en la función buy_stock para realizar compras en MXN
async def buy_stock(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /buy [TICKER] [CANTIDAD]")
            return

        ticker = context.args[0].upper()
        amount = int(context.args[1])

        stock = yf.Ticker(ticker)
        info = stock.history(period="1d")

        if 'Close' in info and info['Close'] is not None:
            price_usd = float(info['Close'].iloc[-1])
        else:
            await update.message.reply_text(f"No se pudo obtener el precio de mercado para {ticker}.")
            return

        # Convertir el precio a MXN
        usd_to_mxn = get_usd_to_mxn_rate()
        price_mxn = price_usd * usd_to_mxn

        if user_id not in portfolios:
            portfolios[user_id] = {}

        if ticker in portfolios[user_id]:
            portfolios[user_id][ticker]['quantity'] += amount
            portfolios[user_id][ticker]['total_investment'] += price_mxn * amount
            portfolios[user_id][ticker]['buy_prices'].append(price_mxn)
        else:
            portfolios[user_id][ticker] = {
                'quantity': amount,
                'total_investment': price_mxn * amount,
                'buy_prices': [price_mxn],
            }
        
        save_json_file(PORTFOLIOS_FILE, portfolios)

        await update.message.reply_text(f"Compraste {amount} acciones de {ticker} a ${price_mxn:.2f} MXN cada una.")

    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /buy [TICKER] [CANTIDAD]")
    except Exception as e:
        await update.message.reply_text(f"Error al comprar acciones: {e}")
        
async def view_profits(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if user_id not in portfolios or not portfolios[user_id]:
        await update.message.reply_text("Tu portafolio está vacío.")
        return

    profits_message = "Ganancias y pérdidas actuales:\n"
    total_profit_loss = 0.0

    for ticker, data in portfolios[user_id].items():
        quantity = data['quantity']
        buy_prices = data['buy_prices']
        if not buy_prices:
            continue
        avg_buy_price = sum(buy_prices) / len(buy_prices)
        stock = yf.Ticker(ticker)
        info = stock.history(period="1d")
        current_price = float(info['Close'].iloc[-1])
        total_value = current_price * quantity
        total_cost = avg_buy_price * quantity
        profit_loss = total_value - total_cost
        total_profit_loss += profit_loss

        profits_message += (
            f"{ticker}: {quantity} acciones\n"
            f"Precio promedio de compra: ${avg_buy_price:.2f}\n"
            f"Precio actual: ${current_price:.2f}\n"
            f"Ganancia/Pérdida: ${profit_loss:.2f}\n\n"
        )

    profits_message += f"Ganancia/Pérdida total: ${total_profit_loss:.2f}"
    await update.message.reply_text(profits_message)

# Función para ver el portafolio del usuario
async def view_portfolio(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if user_id not in portfolios or not portfolios[user_id]:
        await update.message.reply_text("Tu portafolio está vacío.")
        return

    portfolio_message = "Tu portafolio:\n"
    total_value = 0.0

    for ticker, data in portfolios[user_id].items():
        quantity = data['quantity']
        total_investment = data['total_investment']

        stock = yf.Ticker(ticker)
        info = stock.info
        info = stock.history(period="1d")
        current_price = float(info['Close'].iloc[0])
        current_value = current_price * quantity
        total_value += current_value

        portfolio_message += (
            f"{ticker}: {quantity} acciones\n"
            f"Valor actual: ${current_value:.2f}\n"
            f"Inversión total: ${total_investment:.2f}\n\n"
        )

    portfolio_message += f"Valor total del portafolio: ${total_value:.2f}"
    await update.message.reply_text(portfolio_message)

# Función para establecer alertas de precios (compra o venta)
async def set_price_alert(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    try:
        ticker = context.args[0].upper()
        alert_type = context.args[1].lower()  # 'buy' o 'sell'
        target_price = float(context.args[2])

        if alert_type not in ['comprar', 'vender']:
            await update.message.reply_text('El tipo de alerta debe ser "comprar" o "vender". Uso: /alert [TICKER] [comprar/vender] [PRECIO]')
            return

        if user_id not in alerts:
            alerts[user_id] = []
            
        # Verificar si ya existe una alerta similar para evitar duplicados
        if any(alert['ticker'] == ticker and alert['type'] == alert_type for alert in alerts[user_id]):
            await update.message.reply_text(f"Ya existe una alerta {alert_type} para {ticker}.")
            return
            

        alerts[user_id].append({
            'ticker': ticker,
            'type': alert_type,
            'target_price': target_price
        })
        
        # Guardar las alertas en el archivo JSON
        save_json_file(ALERTS_FILE, alerts)

        await update.message.reply_text(f'Alerta {alert_type} establecida para {ticker} a ${target_price}.')

    except (IndexError, ValueError):
        await update.message.reply_text('Uso: /alert [TICKER] [comprar/vender] [PRECIO]')
    except Exception as e:
        await update.message.reply_text(f'Error al establecer alerta: {e}')

# Función para editar una alerta existente
async def edit_alert(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)

    if len(context.args) < 3:
        await update.message.reply_text("Uso: /editalert [TICKER] [comprar/vender] [NUEVO PRECIO]")
        return

    ticker = context.args[0].upper()
    action = context.args[1].lower()
    try:
        new_price = float(context.args[2])
    except ValueError:
        await update.message.reply_text("Por favor, introduce un precio válido.")
        return

    if user_id not in alerts:
        await update.message.reply_text("No tienes alertas configuradas.")
        return

    if ticker not in alerts[user_id]:
        await update.message.reply_text("No tienes una alerta para este ticker.")
        return

    # Debugging: Log información antes de modificar
    print(f"Editando alerta: Usuario: {user_id}, Ticker: {ticker}, Acción: {action}, Nuevo Precio: {new_price}")

    alerts[user_id][ticker] = {'action': action, 'price': new_price}
    save_json_file(ALERTS_FILE, alerts)
    await update.message.reply_text(f"Alerta para {ticker} actualizada a {action} cuando el precio sea {new_price}.")

# Función para eliminar una alerta existente
async def delete_alert(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)

    if len(context.args) < 1:
        await update.message.reply_text("Uso: /deletealert [TICKER]")
        return

    ticker = context.args[0].upper()

    if user_id not in alerts:
        await update.message.reply_text("No tienes alertas configuradas.")
        return

    if ticker not in alerts[user_id]:
        await update.message.reply_text("No tienes una alerta para este ticker.")
        return

    # Debugging: Log información antes de eliminar
    print(f"Eliminando alerta: Usuario: {user_id}, Ticker: {ticker}")

    del alerts[user_id][ticker]
    save_json_file(ALERTS_FILE, alerts)
    await update.message.reply_text(f"Alerta para {ticker} eliminada.")

# Función para calcular el MACD
def calculate_macd(data, short_period=12, long_period=26, signal_period=9):
    ema_short = data['Close'].ewm(span=short_period, adjust=False).mean()
    ema_long = data['Close'].ewm(span=long_period, adjust=False).mean()
    macd_line = ema_short - ema_long
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    macd_histogram = macd_line - signal_line
    return macd_line, signal_line, macd_histogram

def calculate_ema(data, period):
    return data['Close'].ewm(span=period, adjust=False).mean()

# Función para calcular las Bandas de Bollinger
def calculate_bollinger_bands(data, period=20):
    sma = data['Close'].rolling(window=period).mean()
    std = data['Close'].rolling(window=period).std()
    upper_band = sma + (2 * std)
    lower_band = sma - (2 * std)
    return sma, upper_band, lower_band

# Función para calcular el RSI
def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_stochastic(data, period=14):
    low_min = data['Low'].rolling(window=period).min()
    high_max = data['High'].rolling(window=period).max()
    stoch = 100 * (data['Close'] - low_min) / (high_max - low_min)
    return stoch

async def plot_stock(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /plot [TICKER] [PERÍODO]. Ejemplo: /plot AAPL 1mo")
        return

    ticker = args[0].upper()
    period = args[1]

    valid_periods = ['1d', '1mo', '3mo', '6mo', '1y', '5y']
    if period not in valid_periods:
        await update.message.reply_text(f"Período inválido. Los períodos válidos son: {', '.join(valid_periods)}.")
        return

    await update.message.reply_text(f"Generando gráfico para el ticker: {ticker} con período: {period}")

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)

        if data.empty:
            await update.message.reply_text(f"No se pudo obtener datos para el ticker: {ticker}")
            return

        # Cálculo del MACD
        macd_line, signal_line, macd_histogram = calculate_macd(data)
        
        # Cálculo del RSI
        rsi = calculate_rsi(data)

        # Cálculo de las Bandas de Bollinger
        sma, upper_band, lower_band = calculate_bollinger_bands(data)

        # Crear gráfico
        plt.figure(figsize=(14, 12))

        # Gráfico de Precio de Cierre y Bandas de Bollinger
        plt.subplot(3, 1, 1)
        plt.plot(data.index, data['Close'], label='Precio de Cierre', color='blue')
        plt.plot(data.index, sma, label='SMA', color='orange', linestyle='--')
        plt.plot(data.index, upper_band, label='Banda Superior', color='red', linestyle='--')
        plt.plot(data.index, lower_band, label='Banda Inferior', color='green', linestyle='--')
        plt.title(f'Precio de Cierre, Bandas de Bollinger, MACD y RSI de {ticker} ({period})')
        plt.xlabel('Fecha')
        plt.ylabel('Precio de Cierre')
        plt.legend()
        plt.grid(True)

        # Gráfico de MACD
        plt.subplot(3, 1, 2)
        plt.plot(data.index, macd_line, label='MACD', color='red')
        plt.plot(data.index, signal_line, label='Signal Line', color='green')
        plt.bar(data.index, macd_histogram, label='MACD Histogram', color='grey', alpha=0.5)
        plt.xlabel('Fecha')
        plt.ylabel('MACD')
        plt.legend()
        plt.grid(True)

        # Gráfico de RSI
        plt.subplot(3, 1, 3)
        plt.plot(data.index, rsi, label='RSI', color='purple')
        plt.axhline(y=70, color='r', linestyle='--', label='Sobrecompra')
        plt.axhline(y=30, color='g', linestyle='--', label='Sobreventa')
        plt.xlabel('Fecha')
        plt.ylabel('RSI')
        plt.legend()
        plt.grid(True)

        # Ajustar diseño
        plt.tight_layout()

        # Guardar gráfico en un buffer de bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Enviar gráfico al usuario
        await update.message.reply_photo(photo=buf)
        buf.close()

    except Exception as e:
        await update.message.reply_text(f"Error al generar gráfico para el ticker {ticker}: {e}")

#Machine learning
async def plot_stock_with_moving_averages(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Uso: /plotma [TICKER] [PERÍODO] [SMA_PERIOD]. Ejemplo: /plotma AAPL 1mo 30")
        return

    ticker = args[0].upper()
    period = args[1]
    sma_period = int(args[2])

    valid_periods = ['1d', '1mo', '3mo', '6mo', '1y', '5y']
    if period not in valid_periods:
        await update.message.reply_text(f"Período inválido. Los períodos válidos son: {', '.join(valid_periods)}.")
        return

    await update.message.reply_text(f"Generando gráfico para el ticker: {ticker} con período: {period} y SMA de {sma_period} días.")

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)  # Datos para el período especificado

        if data.empty:
            await update.message.reply_text(f"No se pudo obtener datos para el ticker: {ticker}")
            return

        # Calcular SMA
        data['SMA'] = data['Close'].rolling(window=sma_period).mean()

        # Crear gráfico
        plt.figure(figsize=(12, 8))
        plt.plot(data.index, data['Close'], label='Precio de Cierre', color='blue')
        plt.plot(data.index, data['SMA'], label=f'SMA {sma_period} días', color='red', linestyle='--')
        plt.title(f'Precio de Cierre y SMA de {ticker} ({period})')
        plt.xlabel('Fecha')
        plt.ylabel('Precio')
        plt.legend()
        plt.grid(True)

        # Obtener los precios de las puntas
        start_price = data['Close'].iloc[0]
        end_price = data['Close'].iloc[-1]
        start_date = data.index[0]
        end_date = data.index[-1]

        # Etiquetas para las puntas
        plt.annotate(f'${start_price:.2f}', xy=(start_date, start_price), xytext=(start_date, start_price + 10),
                     arrowprops=dict(facecolor='black', arrowstyle='->'), fontsize=5, color='red')
        plt.annotate(f'${end_price:.2f}', xy=(end_date, end_price), xytext=(end_date, end_price + 10),
                     arrowprops=dict(facecolor='black', arrowstyle='->'), fontsize=5, color='red')

        # Guardar gráfico en un buffer de bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Enviar gráfico al usuario
        await update.message.reply_photo(photo=buf)
        buf.close()

    except Exception as e:
        await update.message.reply_text(f"Error al generar gráfico para el ticker {ticker}: {e}")

# Nueva función para listar las alertas configuradas
async def list_alerts(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    alerts = load_json_file(ALERTS_FILE)  # Cargar alertas desde el archivo JSON
    
    user_alerts = alerts.get(user_id, [])
    if not user_alerts:
        message = "No tienes alertas activas."
    else:
        message = "Tus alertas activas:\n"
        for alert in user_alerts:
            ticker = alert['ticker']
            alert_type = alert['type']
            # Manejar tanto las alertas antiguas como las nuevas
            target_price_mxn = alert.get('target_price_mxn', alert.get('target_price', 'Precio no disponible'))
            message += f"{ticker} - {alert_type.capitalize()} a ${target_price_mxn} MXN\n"
            
    await update.message.reply_text(message)
  
# Función para verificar las alertas de precios
async def check_price_alerts(context: CallbackContext):
    application = context.application
    for user_id, user_alerts in alerts.items():
        alerts_to_remove = []
        for alert in user_alerts:
            ticker = alert['ticker']
            alert_type = alert['type']
            target_price_mxn = alert.get('target_price_mxn', alert['target_price'])

            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period="1d")

                if data.empty:
                    message = f"No se pudo obtener el precio actual para {ticker}."
                    logging.error(f"Error: {message}")
                    await application.bot.send_message(chat_id=user_id, text=message)
                    continue

                price_usd = data['Close'].iloc[-1]
                logging.info(f"{ticker} - Precio actual en USD: ${price_usd}")

                # Convertir el precio a MXN si es necesario
                price_mxn = price_usd * get_usd_to_mxn_rate()

                logging.info(f"{ticker} - Precio actual en MXN: ${price_mxn}")

                if (alert_type == 'comprar' and price_mxn <= target_price_mxn) or (alert_type == 'vender' and price_mxn >= target_price_mxn):
                    message = f"🔔🔔🔔 Alerta de {alert_type} para {ticker} a ${target_price_mxn} MXN ha sido alcanzada (Precio actual: ${price_mxn} MXN)."
                    await application.bot.send_message(chat_id=user_id, text=message)
                    alerts_to_remove.append(alert)

            except Exception as e:
                message = f"Error al obtener datos para {ticker}: {e}"
                logging.exception(f"Excepción al procesar {ticker}: {e}")
                await application.bot.send_message(chat_id=user_id, text=message)

        # Eliminar alertas después de verificar
        for alert in alerts_to_remove:
            user_alerts.remove(alert)

        # Guardar los cambios en el archivo JSON
        save_json_file(ALERTS_FILE, alerts)

# Función principal para configurar el bot de Telegram
async def main():
    # Crear la aplicación de Telegram
    application = Application.builder().token(TOKEN).build()

    # Crear el JobQueue
    job_queue = application.job_queue

    # Agregar manejadores de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock_info))
    application.add_handler(CommandHandler("buy", buy_stock))
    #application.add_handler(CommandHandler("sell", sell_stock))
    application.add_handler(CommandHandler("profits", view_profits))
    application.add_handler(CommandHandler("portfolio", view_portfolio))
    application.add_handler(CommandHandler("alert", set_price_alert))
    application.add_handler(CommandHandler("editalert", edit_alert))  # Nuevo comando
    application.add_handler(CommandHandler("deletealert", delete_alert))  # Nuevo comando
    application.add_handler(CommandHandler("listalerts", list_alerts))
    application.add_handler(CommandHandler("grafica", plot_stock))  # Agregar manejador para gráficos
    application.add_handler(CommandHandler("profits", view_profits))
    application.add_handler(CommandHandler("plotma", plot_stock_with_moving_averages))
    application.add_handler(CommandHandler("predict", predict))  # Añadir este comando

    # Iniciar el loop para verificar las alertas de precios en segundo plano
    job_queue.run_repeating(check_price_alerts, interval=5, first=0)

    # Iniciar la aplicación de Telegram
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Mantener la aplicación en ejecución
    while True:
        await asyncio.sleep(1)  # Dormir por 1 hora
        
async def error_handler(update: Update, context: CallbackContext):
    # Registra el error
    print(f"Ocurrió un error: {context.error}")
    # Envía una respuesta al usuario
    await update.message.reply_text('Ocurrió un error, por favor intenta nuevamente.')

    Application.add_error_handler(error_handler)

async def ping(update: Update, context: CallbackContext):
    await update.message.reply_text('pong')

    Application.add_handler(CommandHandler("ping", ping))

if __name__ == "__main__":
    # Ejecutar la función principal usando asyncio
    asyncio.run(main())