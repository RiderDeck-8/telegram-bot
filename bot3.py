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

# Aplicar nest_asyncio para permitir el uso de asyncio en un entorno con un loop de eventos ya existente
nest_asyncio.apply()

# Token del bot de Telegram
TOKEN = '7542207567:AAHdO7BcPyHxSDSICPHOopzwprzaqtpD8HM'

# Diccionario para almacenar portafolios de usuarios y alertas
portfolios = {}
alerts = {}

# Ruta del archivo JSON
ALERTS_FILE = 'alerts.json'

def load_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_alerts():
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f, indent=4)

# Cargar alertas al iniciar el bot
alerts = load_alerts()

# Función para iniciar el bot
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "¡Hola! Soy tu bot financiero.\n"
        "Usa los siguientes comandos:\n"
        "/stock [TICKER] - Obtener información de una acción.\n"
        "/alert [TICKER] [comprar/vender] [PRECIO] - Configurar una alerta para un ticker cuando alcance un precio específico.\n"
        "/buy [TICKER] [CANTIDAD] - Comprar acciones.\n"
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
        "/buy [TICKER] [CANTIDAD] - Comprar una cantidad específica de acciones de un ticker.\n"
        "/portfolio - Ver el estado actual de tu portafolio de inversiones.\n"
        "/grafica - Creacion de graficas ['1d', '1mo', '3mo', '6mo', '1y', '5y'].\n"
        "/listalerts - Listar tus alertas.\n"
    )

# Función para obtener información de una acción
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
            price = data['Close'].iloc[-1]
            high = data['High'].max()
            low = data['Low'].min()
            volume = data['Volume'].sum()
            response = (
                f"**{ticker}**\n"
                f"Precio actual: ${price:.2f}\n"
                f"Máximo del día: ${high:.2f}\n"
                f"Mínimo del día: ${low:.2f}\n"
                f"Volumen: {volume}\n"
            )
        else:
            response = f"No se pudo obtener información para el ticker: {ticker}"

    except Exception as e:
        response = f"Error al obtener información del ticker {ticker}: {e}"

    await update.message.reply_text(response, parse_mode='Markdown')

# Función para comprar acciones
async def buy_stock(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    try:
        ticker = context.args[0].upper()
        amount = int(context.args[1])

        stock = yf.Ticker(ticker)
        info = stock.info
        price = float(info['regularMarketPrice'])

        if user_id not in portfolios:
            portfolios[user_id] = {}

        if ticker in portfolios[user_id]:
            portfolios[user_id][ticker]['quantity'] += amount
            portfolios[user_id][ticker]['total_investment'] += price * amount
        else:
            portfolios[user_id][ticker] = {
                'quantity': amount,
                'total_investment': price * amount,
            }

        await update.message.reply_text(f"Compraste {amount} acciones de {ticker} a ${price} cada una.")

    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /buy [TICKER] [CANTIDAD]")
    except Exception as e:
        await update.message.reply_text(f"Error al comprar acciones: {e}")

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
        current_price = float(info['regularMarketPrice'])
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
        save_alerts()

        await update.message.reply_text(f'Alerta {alert_type} establecida para {ticker} a ${target_price}.')

    except (IndexError, ValueError):
        await update.message.reply_text('Uso: /alert [TICKER] [comprar/vender] [PRECIO]')
    except Exception as e:
        await update.message.reply_text(f'Error al establecer alerta: {e}')

# Función para generar gráficos de acciones
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
        data = stock.history(period=period)  # Datos para el período especificado

        if data.empty:
            await update.message.reply_text(f"No se pudo obtener datos para el ticker: {ticker}")
            return

        # Crear gráfico
        plt.figure(figsize=(10, 6))
        plt.plot(data.index, data['Close'], label='Precio de Cierre', color='blue')
        plt.title(f'Precio de Cierre de {ticker} ({period})')
        plt.xlabel('Fecha')
        plt.ylabel('Precio de Cierre')
        plt.legend()
        plt.grid(True)

        # Obtener los precios de las puntas
        start_price = data['Close'].iloc[0]
        end_price = data['Close'].iloc[-1]
        start_date = data.index[0]
        end_date = data.index[-1]

        # Etiquetas para las puntas
        plt.annotate(f'${start_price:.2f}', xy=(start_date, start_price), xytext=(start_date, start_price + 10),
                     arrowprops=dict(facecolor='black', arrowstyle='->'), fontsize=10, color='red')
        plt.annotate(f'${end_price:.2f}', xy=(end_date, end_price), xytext=(end_date, end_price + 10),
                     arrowprops=dict(facecolor='black', arrowstyle='->'), fontsize=10, color='red')

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
#async def list_alerts(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if user_id not in alerts or not alerts[user_id]:
        await update.message.reply_text('No tienes alertas configuradas.')
        return

    alert_message = "Tus alertas:\n"
    for alert in alerts[user_id]:
        alert_message += f"{alert['ticker']}: ${alert['target_price']} ---> {alert['type']}\n"

    await update.message.reply_text(alert_message)

async def list_alerts(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    alerts = load_alerts()  # Cargar alertas desde el archivo JSON
    
    user_alerts = alerts.get(user_id, [])
    if not user_alerts:
        message = "No tienes alertas activas."
    else:
        message = "Tus alertas activas:\n"
        for alert in user_alerts:
            ticker = alert['ticker']
            alert_type = alert['type']
            target_price = alert['target_price']
            message += f"{ticker} - {alert_type.capitalize()} a ${target_price}---> {alert['type']}\n"
            
    await context.bot.send_message(chat_id=user_id, text=message)

# Función para verificar las alertas de precios
async def check_price_alerts(context: CallbackContext):
    application = context.application
    for user_id, user_alerts in alerts.items():
        for alert in user_alerts.copy():
            ticker = alert['ticker']
            alert_type = alert['type']
            target_price = alert['target_price']

            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period="1d")

                if data.empty:
                    message = f"No se pudo obtener el precio actual para {ticker}."
                    logging.error(f"Error: {message}")
                    await application.bot.send_message(chat_id=user_id, text=message)
                    continue

                price = data['Close'].iloc[-1]
                logging.info(f"{ticker} - Precio actual: ${price}")

                if (alert_type == 'comprar' and price <= target_price) or (alert_type == 'vender' and price >= target_price):
                    message = f"🔔🔔🔔Alerta de {alert_type} para {ticker} a ${target_price} ha sido alcanzada (Precio actual: ${price})."
                    await application.bot.send_message(chat_id=user_id, text=message)
                    user_alerts.remove(alert)

            except Exception as e:
                message = f"Error al obtener datos para {ticker}: {e}"
                logging.exception(f"Excepción al procesar {ticker}: {e}")
                await application.bot.send_message(chat_id=user_id, text=message)

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
    application.add_handler(CommandHandler("portfolio", view_portfolio))
    application.add_handler(CommandHandler("alert", set_price_alert))
    application.add_handler(CommandHandler("listalerts", list_alerts))
    application.add_handler(CommandHandler("grafica", plot_stock))  # Agregar manejador para gráficos

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