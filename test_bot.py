from telegram.ext import Application, CommandHandler
import os

async def start(update, context):
    await update.message.reply_text("Hello from PTB 20.7 🚀")

def main():
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
