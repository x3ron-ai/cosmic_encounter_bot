import telebot, os, logging, math
from telebot.types import InputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from aliens import *
from stats import *
from datetime import datetime

load_dotenv()

logging.basicConfig(level=logging.INFO)

try:
	bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
except Exception as e:
	logging.error(f"Ошибка инициализации бота: {e}")
	exit()

ITEMS_PER_PAGE = 10
BUTTONS_PER_ROW = 2
DLC_LIST = ['технологии', 'награды', 'маркеры кораблей', 'диски союзов', 'космические станции', 'карточки угроз']
pending_games = {}  # Временное хранение комментариев и дополнений для игр
selected_winners = {}  # game_id -> set(player_ids)

def send_alien_page(chat_id, message_id, page, game_id=None, player_id=None):
	alien_names = sorted(list(aliens.keys()))
	total_pages = math.ceil(len(alien_names) / ITEMS_PER_PAGE)
	page = max(0, min(page, total_pages - 1))

	start = page * ITEMS_PER_PAGE
	end = start + ITEMS_PER_PAGE
	current_items = alien_names[start:end]

	keyboard = InlineKeyboardMarkup(row_width=BUTTONS_PER_ROW)

	if game_id and player_id:
		buttons = [InlineKeyboardButton(text=name.capitalize(), callback_data=f"select_alien:{name}:{page}:{game_id}:{player_id}") for name in current_items]
	else:
		buttons = [InlineKeyboardButton(text=name.capitalize(), callback_data=f"alien:{name}:{page}") for name in current_items]

	for i in range(0, len(buttons), BUTTONS_PER_ROW):
		keyboard.add(*buttons[i:i + BUTTONS_PER_ROW])

	nav_buttons = []
	if page > 0:
		nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{page - 1}:{game_id}:{player_id}" if game_id else f"page:{page - 1}"))
	if page < total_pages - 1:
		nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{page + 1}:{game_id}:{player_id}" if game_id else f"page:{page + 1}"))
	if nav_buttons:
		keyboard.add(*nav_buttons)

	text = f"Выбери пришельца (стр. {page + 1} из {total_pages})"

	if message_id:
		bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
	else:
		bot.send_message(chat_id, text, reply_markup=keyboard)

def send_alien_photos(chat_id, alien_name, is_private=True):
	media = []

	if alien_name in aliens:
		image_path = aliens[alien_name]
		if os.path.exists(image_path):
			media.append(InputMediaPhoto(media=open(image_path, 'rb'), caption=f"Пришелец: {alien_name.capitalize()}"))
		else:
			logging.warning(f"Файл не найден: {image_path}")

	if alien_name in flares:
		flare_path = flares[alien_name]
		if os.path.exists(flare_path):
			media.append(InputMediaPhoto(media=open(flare_path, 'rb'), caption="Вспышка"))
		else:
			logging.warning(f"Файл не найден: {flare_path}")

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
			bot.send_message(chat_id, "Ошибка при отправке изображений")
	else:
		if is_private: bot.send_message(chat_id, "А где а нет")

def create_game_message(game_id, creator_id, comment, dlc_list):
	creator = bot.get_chat(creator_id).username or f"User{creator_id}"
	dlc_str = ", ".join(dlc_list) if dlc_list else "Без дополнений"
	text = f"Новая игра #{game_id}\nСоздатель: @{creator}\nКомментарий: {comment}\nДополнения: {dlc_str}\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

	keyboard = InlineKeyboardMarkup()
	keyboard.add(InlineKeyboardButton("Присоединиться", callback_data=f"join_game:{game_id}"))
	keyboard.add(InlineKeyboardButton("Завершить игру", callback_data=f"end_game:{game_id}:{creator_id}"))

	return text, keyboard

def send_winner_selection(chat_id, game_id):
	keyboard = generate_updated_winner_keyboard(game_id, chat_id)
	bot.send_message(chat_id, "Выберите победителей (по одному или несколько):", reply_markup=keyboard)

def generate_updated_winner_keyboard(game_id, chat_id):
	players = get_game_players(game_id)
	keyboard = InlineKeyboardMarkup(row_width=2)
	winners = selected_winners.get(game_id, set())

	for player in players:
		player_id = player['player_id']
		username = bot.get_chat(player_id).username or f"User{player_id}"
		is_selected = player_id in winners
		text = f"{'✅ ' if is_selected else ''}@{username}"
		keyboard.add(InlineKeyboardButton(text, callback_data=f"winner_toggle:{game_id}:{player_id}"))

	keyboard.add(InlineKeyboardButton("✅ Завершить игру", callback_data=f"finalize_game:{game_id}"))
	return keyboard

def send_rating_request(chat_id, game_id, player_id):
	keyboard = InlineKeyboardMarkup(row_width=5)
	for i in range(1, 6):
		keyboard.add(InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate:{game_id}:{player_id}:{i}"))
	bot.send_message(chat_id, "Оцените игру (1-5 звезд):", reply_markup=keyboard)

@bot.message_handler(commands=['site'])
def site_message(message):
	bot.reply_to(message, 'Омагад!!! https://t.me/addemoji/CosmicEncounter')

@bot.message_handler(commands=['start'])
def send_welcome(message):
	try:
		add_player(message.from_user.id)
		bot.reply_to(message, "Напиши нужного пришельца или выбери его в /menu")
	except Exception as e:
		logging.error(f"Ошибка в send_welcome: {e}")

@bot.message_handler(commands=['menu'])
def menu_handler(message):
	send_alien_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['profile'])
def user_profile(message):
	user_stats = get_player_stats

@bot.message_handler(commands=['party'])
def party_menu(message):
	try:
		msg = bot.reply_to(message, "Введите комментарий к игре:")
		bot.register_next_step_handler(msg, handle_game_comment, message.from_user.id)
	except Exception as e:
		logging.error(f"Ошибка в party_menu: {e}")

def handle_game_comment(message, creator_id):
	comment = message.text.strip()
	pending_games[creator_id] = {'comment': comment, 'dlcs': set()}
	keyboard = InlineKeyboardMarkup(row_width=2)
	for dlc in DLC_LIST:
		keyboard.add(InlineKeyboardButton(dlc.capitalize(), callback_data=f"dlc:{creator_id}:{dlc}"))
	keyboard.add(InlineKeyboardButton("Создать игру", callback_data=f"create_game:{creator_id}"))

	bot.send_message(message.chat.id, "Выберите дополнения (можно несколько):", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: CallbackQuery):
	try:
		data = call.data.split(":")
		action = data[0]

		if action == "alien":
			_, alien_name, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_alien_photos(call.message.chat.id, alien_name)
			send_alien_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id)

		elif action == "page":
			page = int(data[1])
			game_id = int(data[2]) if len(data) > 2 else None
			player_id = int(data[3]) if len(data) > 3 else None
			send_alien_page(call.message.chat.id, call.message.message_id, page, game_id, player_id)
			bot.answer_callback_query(call.id)

		elif action == "dlc":
			creator_id, dlc = data[1], data[2]
			pending_games.setdefault(int(creator_id), {'comment': '', 'dlcs': set()})['dlcs'].add(dlc)
			bot.answer_callback_query(call.id, f"Добавлено: {dlc}")

		elif action == "create_game":
			creator_id = int(data[1])
			if creator_id not in pending_games:
				bot.answer_callback_query(call.id, "Ошибка: комментарий не найден")
				return
			comment = pending_games[creator_id]['comment']
			dlc_list = list(pending_games[creator_id]['dlcs'])
			game_id = create_game(comment, dlc_list, creator_id)
			add_player(creator_id)
			text, keyboard = create_game_message(game_id, creator_id, comment, dlc_list)
			bot.send_message(call.message.chat.id, text, reply_markup=keyboard)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			del pending_games[creator_id]
			bot.answer_callback_query(call.id)

		elif action == "join_game":
			game_id = int(data[1])
			player_id = call.from_user.id
			if is_player_in_game(game_id, player_id):
				bot.answer_callback_query(call.id, "Вы уже в игре!")
				return
			add_player(player_id)
			send_alien_page(player_id, None, 0, game_id, player_id)
			bot.answer_callback_query(call.id, "Выберите персонажа")

		elif action == "select_alien":
			_, alien_name, page_str, game_id, player_id = data
			game_id, player_id = int(game_id), int(player_id)
			try:
				join_game(game_id, player_id, alien_name)
				bot.delete_message(call.message.chat.id, call.message.message_id)
				bot.send_message(player_id, f"Вы выбрали персонажа: {alien_name.capitalize()}")
				bot.answer_callback_query(call.id, "Персонаж выбран!")
			except ValueError:
				bot.answer_callback_query(call.id, "Неверный персонаж, выберите снова")
				send_alien_page(player_id, None, 0, game_id, player_id)

		elif action == "end_game":
			game_id, creator_id = map(int, data[1:3])
			if call.from_user.id != creator_id:
				bot.answer_callback_query(call.id, "Только создатель может завершить игру!")
				return
			send_winner_selection(call.message.chat.id, game_id)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			bot.answer_callback_query(call.id)

		elif action == "winner_toggle":
			game_id, player_id = int(data[1]), int(data[2])
			winners = selected_winners.setdefault(game_id, set())
			if player_id in winners:
				winners.remove(player_id)
				bot.answer_callback_query(call.id, "Победитель убран")
			else:
				winners.add(player_id)
				bot.answer_callback_query(call.id, "Победитель добавлен")

			bot.edit_message_reply_markup(
				chat_id=call.message.chat.id,
				message_id=call.message.message_id,
				reply_markup=generate_updated_winner_keyboard(game_id, call.message.chat.id)
			)

		elif action == "finalize_game":
			game_id = int(data[1])
			winners = selected_winners.get(game_id, set())

			for player in get_game_players(game_id):
				is_winner = player['player_id'] in winners
				set_player_result(game_id, player['player_id'], is_winner, None)
				send_rating_request(player['player_id'], game_id, player['player_id'])

			bot.delete_message(call.message.chat.id, call.message.message_id)
			selected_winners.pop(game_id, None)
			bot.answer_callback_query(call.id, "Игра завершена")

		elif action == "rate":
			game_id, player_id, rating = map(int, data[1:4])
			set_player_result(game_id, player_id, is_player_in_game(game_id, player_id), rating)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			bot.answer_callback_query(call.id, "Оценка сохранена")

	except Exception as e:
		logging.error(f"Ошибка в callback_handler: {e}")
		bot.answer_callback_query(call.id, "Произошла ошибка")

@bot.message_handler(func=lambda message: True)
def send_alien_image(message):
	try:
		alien_name = message.text.lower().strip()
		send_alien_photos(message.chat.id, alien_name, message.chat.id == message.from_user.id)
	except Exception as e:
		logging.error(f"Ошибка в send_alien_image: {e}")
		bot.reply_to(message, "Произошла ошибка при обработке запроса.")

if __name__ == '__main__':
	try:
		logging.info("Бот запущен")
		bot.infinity_polling()
	except Exception as e:
		logging.error(f"Ошибка в основном цикле: {e}")

