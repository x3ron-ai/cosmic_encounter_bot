import telebot, os, logging, math
from telebot.types import InputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from aliens import *

load_dotenv()

logging.basicConfig(level=logging.INFO)

try:
	bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
except Exception as e:
	logging.error(f"Ошибка инициализации бота: {e}")
	exit()


ITEMS_PER_PAGE = 10
BUTTONS_PER_ROW = 2

def send_alien_page(chat_id, message_id, page):
	alien_names = list(aliens.keys())
	total_pages = math.ceil(len(alien_names) / ITEMS_PER_PAGE)
	page = max(0, min(page, total_pages - 1))

	start = page * ITEMS_PER_PAGE
	end = start + ITEMS_PER_PAGE
	current_items = alien_names[start:end]

	keyboard = InlineKeyboardMarkup(row_width=BUTTONS_PER_ROW)

	# Добавляем кнопки с именами пришельцев
	buttons = [InlineKeyboardButton(text=name.capitalize(), callback_data=f"alien:{name}") for name in current_items]
	for i in range(0, len(buttons), BUTTONS_PER_ROW):
		keyboard.add(*buttons[i:i + BUTTONS_PER_ROW])

	# Кнопки навигации
	nav_buttons = []
	if page > 0:
		nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{page - 1}"))
	if page < total_pages - 1:
		nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{page + 1}"))
	if nav_buttons:
		keyboard.add(*nav_buttons)

	text = f"Выбери пришельца (стр. {page + 1} из {total_pages})"

	if message_id:
		bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
	else:
		bot.send_message(chat_id, text, reply_markup=keyboard)



def send_alien_photos(chat_id, alien_name):
	media = []

	# Основное изображение
	if alien_name in aliens:
		image_path = aliens[alien_name]
		if os.path.exists(image_path):
			media.append(InputMediaPhoto(media=open(image_path, 'rb'), caption=f"Пришелец: {alien_name.capitalize()}"))
		else:
			logging.warning(f"Файл не найден: {image_path}")

	# Вспышка
	if alien_name in flares:
		flare_path = flares[alien_name]
		if os.path.exists(flare_path):
			media.append(InputMediaPhoto(media=open(flare_path, 'rb'), caption="Вспышка"))
		else:
			logging.warning(f"Файл не найден: {flare_path}")

	# Пиколи!!
	if alien_name in essence_aliens:
		essence_path = essence_aliens[alien_name]
		if os.path.exists(essence_path):
			media.append(InputMediaPhoto(media=open(essence_path, 'rb'), caption=f"Карты: {alien_name.capitalize()}"))
		else:
			logging.warning(f"Файл не найден: {essence_path}")

	if media:
		try:
			bot.send_media_group(chat_id, media)
		except Exception as e:
			logging.error(f"Ошибка при отправке альбома: {e}")
			bot.send_message(chat_id, "Окак")
	else:
		bot.send_message(chat_id, "А где а нет")


def send_photo_with_retry(chat_id, image_path, caption=None):
	"""Универсальная функция для отправки фото с обработкой ошибок"""
	try:
		if not os.path.exists(image_path):
			logging.error(f"Файл не найден: {image_path}")
			return False

		with open(image_path, 'rb') as photo:
			bot.send_photo(chat_id, InputFile(photo), caption=caption)
		return True
	except Exception as e:
		logging.error(f"Ошибка при отправке фото: {e}")
		return False


@bot.message_handler(commands=['start'])
def send_welcome(message):
	try:
		bot.reply_to(message, "Напиши нужного пришельца.")
	except Exception as e:
		logging.error(f"Ошибка в send_welcome: {e}")

@bot.message_handler(commands=['menu'])
def menu_handler(message):
	send_alien_page(chat_id=message.chat.id, message_id=None, page=0)




@bot.message_handler(commands=['party'])
def party_menu(message):
	print('party creation')



@bot.message_handler(func=lambda message: True)
def send_alien_image(message):
		try:
				alien_name = message.text.lower().strip()
				send_alien_photos(message.chat.id, alien_name)
		except Exception as e:
				logging.error(f"Ошибка в send_alien_image: {e}")
				bot.reply_to(message, "Произошла ошибка при обработке запроса.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("alien:") or call.data.startswith("page:"))
def callback_handler(call: CallbackQuery):
	try:
		if call.data.startswith("alien:"):
			alien_name = call.data.split(":")[1]
			send_alien_photos(call.message.chat.id, alien_name)
			bot.answer_callback_query(call.id)

		elif call.data.startswith("page:"):
			page = int(call.data.split(":")[1])
			send_alien_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

	except Exception as e:
		logging.error(f"Ошибка в callback_handler: {e}")
		bot.answer_callback_query(call.id, "Произошла ошибка")

if __name__ == '__main__':
	try:
		logging.info("Бот запущен")
		bot.infinity_polling()
	except Exception as e:
		logging.error(f"Ошибка в основном цикле: {e}")
