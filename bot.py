import logging
from dotenv import load_dotenv
from bot_instance import bot
import message_handler

load_dotenv()
logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    try:
        logging.info("Бот запущен")
        bot.infinity_polling()
    except Exception as e:
        logging.error(f"Ошибка в основном цикле: {e}")
