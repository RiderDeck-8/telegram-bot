import asyncio
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext
import yfinance as yf
import matplotlib.pyplot as plt
import io

# Token del bot de Telegram
TOKEN = '7269472561:AAE9KUJhN0pcZNMVQqHEUfNKAsQjKJ9kW58'

# Diccionario para almacenar portafolios de usuarios, alertas y noticias
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
        "/listalerts - Listar tus alertas\n"
        "/chart [TICKER] - Ver gráfico de precios para un ticker."
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
        "/chart [TICKER] - Ver gráfico de precios para un ticker."
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
        data = stock.history(period="1d")
        price = data['Close'].iloc[-1]

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

        await update.message.reply_text(f"Compraste {amount} acciones de {ticker} a ${price:.2f} cada una.")

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
        current_data = stock.history(period="1d")
        current_price = current_data['Close'].iloc[-1]
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
        alert_type = context.args[1].lower()  # 'comprar' o 'vender'
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

# Función para listar las alertas configuradas
async def list_alerts(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id not in alerts or not alerts[user_id]:
        await update.message.reply_text('No tienes alertas configuradas.')
        return

    alert_message = "Tus alertas:\n"
    for alert in alerts[user_id]:
        alert_message += f"{alert['ticker']}: {alert['type']} a ${alert['target_price']}\n"

    await update.message.reply_text(alert_message)

# Función para establecer alertas de noticias
async def set_news_alert(update: Update, context: CallbackContext):
    ticker = ' '.join(context.args).upper()
    if not ticker:
        await update.message.reply_text("Por favor proporciona un ticker. Ejemplo: /setnews AAPL")
        return

    # Aquí deberías implementar la lógica para manejar las alertas de noticias
    await update.message.reply_text(f"Alertas de noticias configuradas para el ticker: {ticker}")

# Función para mostrar el gráfico de precios de un ticker
async def show_chart(update: Update, context: CallbackContext):
    ticker = ' '.join(context.args).upper()
    if not ticker:
        await update.message.reply_text("Por favor proporciona un ticker. Ejemplo: /chart AAPL")
        return

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1y")

        if data.empty:
            await update.message.reply_text(f"No se pudo obtener información para el ticker: {ticker}")
            return

        plt.figure(figsize=(10, 6))
        plt.plot(data.index, data['Close'], label='Precio de Cierre')
        plt.title(f'Gráfico de Precios de {ticker}')
        plt.xlabel('Fecha')
        plt.ylabel('Precio')
        plt.legend()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        await update.message.reply_photo(photo=InputFile(buf, filename='chart.png'))

    except Exception as e:
        await update.message.reply_text(f"Error al obtener el gráfico: {e}")

# Función para verificar y notificar alertas de precios
async def check_price_alerts():
    while True:
        for user_id, user_alerts in alerts.items():
            for alert in user_alerts:
                ticker = alert['ticker']
                alert_type = alert['type']
                target_price = alert['target_price']

                try:
                    stock = yf.Ticker(ticker)
                    data = stock.history(period="1d")
                    current_price = data['Close'].iloc[-1]

                    if alert_type == 'comprar' and current_price <= target_price:
                        message = f"¡Alerta de compra! El precio de {ticker} ha bajado a ${current_price:.2f}, que es igual o menor que tu precio objetivo de ${target_price}."
                        await bot.send_message(chat_id=user_id, text=message)
                    elif alert_type == 'vender' and current_price >= target_price:
                        message = f"¡Alerta de venta! El precio de {ticker} ha subido a ${current_price:.2f}, que es igual o mayor que tu precio objetivo de ${target_price}."
                        await bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    print(f"Error al verificar alerta de precio: {e}")

        await asyncio.sleep(60 * 5)  # Espera 5 minutos antes de la siguiente verificación

# Configuración del bot
def main():
    global bot
    bot = Application.builder().token(TOKEN).build()

    # Comandos del bot
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("help", help_command))
    bot.add_handler(CommandHandler("stock", stock_info))
    bot.add_handler(CommandHandler("buy", buy_stock))
    bot.add_handler(CommandHandler("portfolio", view_portfolio))
    bot.add_handler(CommandHandler("alert", set_price_alert))
    bot.add_handler(CommandHandler("listalerts", list_alerts))
    bot.add_handler(CommandHandler("setnews", set_news_alert))
    bot.add_handler(CommandHandler("chart", show_chart))

    # Inicia el bot
    asyncio.create_task(check_price_alerts())
    bot.run_polling()

if __name__ == '__main__':
    main()
