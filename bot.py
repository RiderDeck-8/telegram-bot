import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.foreignexchange import ForeignExchange

# Token del bot de Telegram
TOKEN = '7269472561:AAE9KUJhN0pcZNMVQqHEUfNKAsQjKJ9kW58'
# API Key de Alpha Vantage
ALPHA_VANTAGE_API_KEY = 'IW4NXF0KSCQJZCH3'

# Diccionario para almacenar portafolios de usuarios y alertas
portfolios = {}
alerts = {}

# Función para iniciar el bot
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "¡Hola! Soy tu bot financiero.\n"
        "Usa los siguientes comandos:\n"
        "/stock [TICKER] - Obtener información de una acción.\n"
        "/alert [TICKER] [PRECIO] - Recibir una alerta cuando la acción alcance el precio indicado.\n"
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
        "/alert [TICKER] [PRECIO] - Configurar una alerta para un ticker cuando alcance un precio específico.\n"
        "/buy [TICKER] [CANTIDAD] - Comprar una cantidad específica de acciones de un ticker.\n"
        "/portfolio - Ver el estado actual de tu portafolio de inversiones.\n"
        "/convert [MONEDA_ORIGEN] [MONEDA_DESTINO] [CANTIDAD] - Convertir una cantidad de una moneda a otra.\n"
        "/setnews [TICKER] - Configurar alertas de noticias para un ticker específico."
    )

# Función para obtener información de una acción
async def stock_info(update: Update, context: CallbackContext):
    ticker = ' '.join(context.args).upper()
    if not ticker:
        await update.message.reply_text("Por favor proporciona un ticker de acción. Ejemplo: /stock AAPL")
        return

    await update.message.reply_text(f"Buscando información para el ticker: {ticker}")

    try:
        ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='json')
        data, meta_data = ts.get_quote_endpoint(symbol=ticker)

        if '05. price' in data:
            price = data['05. price']
            high = data['03. high']
            low = data['04. low']
            volume = data['06. volume']
            response = (
                f"**{ticker}**\n"
                f"Precio actual: ${price}\n"
                f"Máximo del día: ${high}\n"
                f"Mínimo del día: ${low}\n"
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

        ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='json')
        data, _ = ts.get_quote_endpoint(symbol=ticker)
        price = float(data['05. price'])

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

    ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='json')
    for ticker, data in portfolios[user_id].items():
        quantity = data['quantity']
        total_investment = data['total_investment']

        current_data, _ = ts.get_quote_endpoint(symbol=ticker)
        current_price = float(current_data['05. price'])
        current_value = current_price * quantity
        total_value += current_value

        portfolio_message += (
            f"{ticker}: {quantity} acciones\n"
            f"Valor actual: ${current_value:.2f}\n"
            f"Inversión total: ${total_investment:.2f}\n\n"
        )

    portfolio_message += f"Valor total del portafolio: ${total_value:.2f}"
    await update.message.reply_text(portfolio_message)

# Función para convertir monedas
async def convert_currency(update: Update, context: CallbackContext):
    try:
        from_currency = context.args[0].upper()
        to_currency = context.args[1].upper()
        amount = float(context.args[2])

        cc = ForeignExchange(key=ALPHA_VANTAGE_API_KEY)
        data, _ = cc.get_currency_exchange_rate(from_currency, to_currency)
        exchange_rate = float(data['5. Exchange Rate'])
        converted_amount = amount * exchange_rate

        await update.message.reply_text(f'{amount} {from_currency} equivale a {converted_amount:.2f} {to_currency}')
    except (IndexError, ValueError):
        await update.message.reply_text('Uso: /convert [MONEDA_ORIGEN] [MONEDA_DESTINO] [CANTIDAD]')
    except Exception as e:
        await update.message.reply_text(f'Error al convertir monedas: {e}')

# Función para establecer alertas de precios
async def set_price_alert(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    try:
        ticker = context.args[0].upper()
        target_price = float(context.args[1])

        if user_id not in alerts:
            alerts[user_id] = []

        alerts[user_id].append({
            'ticker': ticker,
            'target_price': target_price
        })

        await update.message.reply_text(f'Alerta establecida para {ticker} cuando alcance ${target_price}.')

    except (IndexError, ValueError):
        await update.message.reply_text('Uso: /alert [TICKER] [PRECIO]')
    except Exception as e:
        await update.message.reply_text(f'Error al establecer alerta: {e}')

# Nueva función para listar las alertas configuradas
async def list_alerts(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id not in alerts or not alerts[user_id]:
        await update.message.reply_text('No tienes alertas configuradas.')
        return

    alert_message = "Tus alertas:\n"
    for alert in alerts[user_id]:
        alert_message += f"{alert['ticker']}: ${alert['target_price']}\n"

    await update.message.reply_text(alert_message)

# Función para establecer alertas de noticias
async def set_news_alert(update: Update, context: CallbackContext):
    ticker = ' '.join(context.args).upper()
    if not ticker:
        await update.message.reply_text("Por favor proporciona un ticker de acción para las noticias. Ejemplo: /setnews AAPL")
        return

    await update.message.reply_text(f"Alerta de noticias establecida para el ticker: {ticker}")

# Función para verificar las alertas de precios
async def check_price_alerts(application: Application):
    while True:
        for user_id, user_alerts in alerts.items():
            ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='json')
            for alert in user_alerts:
                ticker = alert['ticker']
                target_price = alert['target_price']
                data, _ = ts.get_quote_endpoint(symbol=ticker)
                current_price = float(data['05. price'])
                
                if current_price >= target_price:
                    await application.bot.send_message(
                        chat_id=user_id,
                        text=f'🔔 Alerta de precio: {ticker} ha alcanzado o superado ${target_price}. Precio actual: ${current_price}'
                    )
                    user_alerts.remove(alert)

        await asyncio.sleep(60)  # Esperar 1 minuto antes de verificar nuevamente

# Configuración del bot
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock_info))
    application.add_handler(CommandHandler("buy", buy_stock))
    application.add_handler(CommandHandler("portfolio", view_portfolio))
    application.add_handler(CommandHandler("convert", convert_currency))
    application.add_handler(CommandHandler("alert", set_price_alert))
    application.add_handler(CommandHandler("listalerts", list_alerts))
    application.add_handler(CommandHandler("setnews", set_news_alert))

    # Iniciar la verificación de alertas en una tarea asíncrona
    loop = asyncio.get_event_loop()
    loop.create_task(check_price_alerts(application))

    application.run_polling()

if __name__ == '__main__':
    main()
