import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import yfinance as yf
from telegram.error import NetworkError, TelegramError
import matplotlib.pyplot as plt
import io
import logging

# Token del bot de Telegram
TOKEN = '7269472561:AAE9KUJhN0pcZNMVQqHEUfNKAsQjKJ9kW58'

# Diccionario para almacenar portafolios de usuarios y alertas
portfolios = {}
alerts = {}

# Función para iniciar el bot
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "¡Hola! Soy tu bot financiero.\n"
        "Usa los siguientes comandos:\n"
        "/stock [TICKER] - Obtener información de una acción.\n"
        "/alert [TICKER] [comprar/vender] [PRECIO] - Configurar una alerta para un ticker cuando alcance un precio específico.\n"
        "/buy [TICKER] [CANTIDAD] - Comprar acciones.\n"
        "/portfolio - Ver tu portafolio.\n"
        "/convert [MONEDA_ORIGEN] [MONEDA_DESTINO] [CANTIDAD] - Convertir monedas.\n"
        "/setnews [TICKER] - Establecer alertas de noticias para un ticker.\n"
        "/listalerts - Listar tus alertas"
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
        "/convert [MONEDA_ORIGEN] [MONEDA_DESTINO] [CANTIDAD] - Convertir una cantidad de una moneda a otra.\n"
        "/setnews [TICKER] - Configurar alertas de noticias para un ticker específico.\n"
        "/listalerts - Listar tus alertas"
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
    user_id = update.message.chat_id
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
    user_id = update.message.chat_id
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
    user_id = update.message.chat_id
    try:
        ticker = context.args[0].upper()
        alert_type = context.args[1].lower()  # 'buy' o 'sell'
        target_price = float(context.args[2])

        if alert_type not in ['comprar', 'vender']:
            await update.message.reply_text('El tipo de alerta debe ser "comprar" o "vender". Uso: /alert [TICKER] [comprar/vender] [PRECIO]')
            return

        if user_id not in alerts:
            alerts[user_id] = []

        alerts[user_id].append({
            'ticker': ticker,
            'type': alert_type,
            'target_price': target_price
        })

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
                     arrowprops=dict(facecolor='black', arrowstyle='->'), fontsize=10, color='green')

        # Guardar gráfico en un objeto BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Enviar gráfico al usuario
        await update.message.reply_photo(photo=buf)

    except Exception as e:
        await update.message.reply_text(f"Error al generar gráfico: {e}")

# Función principal
async def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    application = Application.builder().token(TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock_info))
    application.add_handler(CommandHandler("buy", buy_stock))
    application.add_handler(CommandHandler("portfolio", view_portfolio))
    application.add_handler(CommandHandler("alert", set_price_alert))
    application.add_handler(CommandHandler("plot", plot_stock))

    # Ejecutar el bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
