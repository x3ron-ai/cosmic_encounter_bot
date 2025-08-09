import telebot, os, logging, math
from telebot.types import InputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from cc_data import ALIENS, ESSENCE_ALIENS, FLARES, TECHNOLOGIES, HAZARDS, STATIONS, LOCALIZATION_EN, ACHIEVEMENTS, ARTIFACTS
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
pending_games = {}
pending_game_players = {}
waitlist = {}
selected_winners = {}
pending_comments = {}

def send_paginated_keyboard(chat_id, message_id, items: list, page: int, item_prefix: str, page_prefix: str, item_label: str, items_per_page: int = 8, row_width: int = 2, callback_func=None, page_callback_func=None):
	total_pages = math.ceil(len(items) / items_per_page)
	page = max(0, min(page, total_pages - 1))

	start = page * items_per_page
	end = start + items_per_page
	current_items = sorted(items)[start:end]

	keyboard = InlineKeyboardMarkup(row_width=row_width)

	buttons = [
		InlineKeyboardButton(
			text=item.capitalize(),
			callback_data=callback_func(item, start + i, page) if callback_func else f"{item_prefix}:{start + i}:{page}"
		) for i, item in enumerate(current_items)
	]

	for i in range(0, len(buttons), row_width):
		keyboard.add(*buttons[i:i + row_width])

	nav_buttons = []
	if page > 0:
		nav_cb = page_callback_func(page - 1) if page_callback_func else f"{page_prefix}_page:{page - 1}"
		nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=nav_cb))
	if page < total_pages - 1:
		nav_cb = page_callback_func(page + 1) if page_callback_func else f"{page_prefix}_page:{page + 1}"
		nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=nav_cb))

	if nav_buttons:
		keyboard.add(*nav_buttons)

	text = f"Выбери {item_label} (стр. {page + 1} из {total_pages})"

	if message_id:
		bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
	else:
		bot.send_message(chat_id, text, reply_markup=keyboard)

def send_achievements_page(chat_id, message_id, page):
	send_paginated_keyboard(
		chat_id, message_id, list(ACHIEVEMENTS.keys()), page,
		item_prefix="achieve", page_prefix="achieve",
		item_label="достижение", items_per_page=8, row_width=2
	)

def send_artifacts_page(chat_id, message_id, page):
	send_paginated_keyboard(
		chat_id, message_id, sorted(list(ARTIFACTS.keys())), page,
		item_prefix="art", page_prefix="art",
		item_label="артефакт", items_per_page=8, row_width=2
	)

def send_stations_page(chat_id, message_id, page):
	send_paginated_keyboard(
		chat_id, message_id, list(STATIONS.keys()), page,
		item_prefix="station", page_prefix="station",
		item_label="станцию", items_per_page=10, row_width=2
	)

def send_technologies_page(chat_id, message_id, page):
	send_paginated_keyboard(
		chat_id, message_id, list(TECHNOLOGIES.keys()), page,
		item_prefix="tech", page_prefix="tech",
		item_label="технологию", items_per_page=10, row_width=2
	)

def send_hazards_page(chat_id, message_id, page):
	send_paginated_keyboard(
		chat_id, message_id, list(HAZARDS.keys()), page,
		item_prefix="hazard", page_prefix="hazard",
		item_label="угрозу", items_per_page=10, row_width=2
	)


def send_alien_page(chat_id, message_id, page, game_id=None, player_id=None):
	def alien_callback(name, index, page):
		if game_id and player_id:
			return f"select_alien:{name}:{page}:{game_id}:{player_id}"
		return f"alien:{name}:{page}"

	def page_callback(new_page):
		if game_id and player_id:
			return f"page:{new_page}:{game_id}:{player_id}"
		return f"page:{new_page}"

	send_paginated_keyboard(
		chat_id=chat_id,
		message_id=message_id,
		items=list(ALIENS.keys()),
		page=page,
		item_prefix="alien",
		page_prefix="page",
		item_label="пришельца",
		items_per_page=10,
		row_width=2,
		callback_func=alien_callback,
		page_callback_func=page_callback
	)

def send_history_page(chat_id, player_games, page, message_id=None):
	if not player_games or page >= len(player_games):
		bot.send_message(chat_id, "Игра не найдена.")
		return

	game = player_games[page]
	player_id = game['player_id']
	creator_id = game['creator_id']

	estimations = []

	response = (
		f'📜 История игр (игра {page + 1} из {len(player_games)}):\n\n'
		f'🎮 Игра #{game["game_id"]} {"🏆 Победа!" if game["am_i_winner"] else "❌ Поражение"}\n'
		f'👽 Ты играл за: {game["my_alien"].capitalize() if game["my_alien"] else "Nonono"}\n'
		f'⭐ Твоя оценка: {game["my_estimation"]}/5\n'
		f'💬 Название игры: {game["comment"] or "—"}\n'
		f'🗓️ Дата: {game["date"].strftime("%d.%m.%Y %H:%M")}\n\n'
		'👥 Игроки:\n'
	)

	estimations.append(game["my_estimation"])
	comments_text = ''
	for opp in game['opponents']:
		tg = bot.get_chat(opp['player_id'])
		tg_name = f'@{tg.username} ({tg.first_name})' if tg.username else f"{tg.first_name}"
		status = "🏆" if opp["is_winner"] else "❌"
		estimation = f'{opp["estimation"]}/5⭐' if opp["estimation"] is not None else "—"
		estimations.append(opp["estimation"])
		response += f'• 👽 {opp["alien"].capitalize()} {status} ({tg_name}) — {estimation}\n'
		if opp["comment"]:
			comments_text += f'{tg_name} -  {opp["comment"]}\n'

	try: response += f'\n🌟 Оценка партии: {format_integer(round(sum([e for e in estimations if e is not None]) / len([e for e in estimations if e is not None]), 2))}\n'
	except: pass
	response += f'\n🧩 Дополнения: {game["dlc"] or "—"}\n'
	if comments_text:
		response += '📝 Комментарии:\n'+comments_text
	keyboard = InlineKeyboardMarkup(row_width=3)
	keyboard.add(InlineKeyboardButton(
		"✏️ Изменить оценку",
		callback_data=f"change_rating:{game['game_id']}:{int(game['am_i_winner'] or 0)}"
	))

	nav_buttons = []
	if page > 0:
		nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"history:{page - 1}"))
	if page < len(player_games) - 1:
		nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"history:{page + 1}"))

	if nav_buttons:
		keyboard.add(*nav_buttons)

	if player_id == creator_id and len(get_game_players(game['game_id'])) <= 2:
		keyboard.add(InlineKeyboardButton("Удалить игру", callback_data=f"deletegame:{game['game_id']}"))

	keyboard.add(InlineKeyboardButton("📝 Оставить комментарий", callback_data=f"comment_game:{game['game_id']}"))
	if message_id:
		bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=response, reply_markup=keyboard)
	else:
		bot.send_message(chat_id, response, reply_markup=keyboard)


def send_other_photos(chat_id, object_name, is_private=True):
	media = []

	all_photos = {**HAZARDS, **TECHNOLOGIES, **STATIONS, **ARTIFACTS}
	image_path = all_photos[object_name]
	if type(image_path) != list:
		image_path = [image_path]

	for photo in image_path:
		if os.path.exists(photo):
			card_name = photo.split('/')[-1].replace('_', ' ').replace('.jpg', '')
			media.append(InputMediaPhoto(media=open(photo, 'rb'), caption=f"Карта: {card_name.capitalize()}"))
		else:
			logging.warning(f"Файл не найден: {image_path}")
	bot.send_media_group(chat_id, media)

def send_alien_photos(chat_id, alien_name, is_private=True):
	media = []
	loc_rev = {k.lower(): i for i, k in LOCALIZATION_EN.items()}
	if alien_name in loc_rev:
		alien_name = loc_rev[alien_name]

	if alien_name in ALIENS:
		image_path = ALIENS[alien_name]
		if os.path.exists(image_path):
			if alien_name in LOCALIZATION_EN:
				caption=f"Пришелец: {alien_name.capitalize()} ({LOCALIZATION_EN[alien_name]})"
			else:
				caption=f"Пришелец: {alien_name.capitalize()}"
			media.append(InputMediaPhoto(media=open(image_path, 'rb'), caption=caption))
		else:
			logging.warning(f"Файл не найден: {image_path}")

	if alien_name in FLARES:
		flare_path = FLARES[alien_name]
		if os.path.exists(flare_path):
			media.append(InputMediaPhoto(media=open(flare_path, 'rb'), caption="Вспышка"))
		else:
			logging.warning(f"Файл не найден: {flare_path}")

	if alien_name in ESSENCE_ALIENS:
		essence_path = ESSENCE_ALIENS[alien_name]
		if os.path.exists(essence_path):
			media.append(InputMediaPhoto(media=open(essence_path, 'rb'), caption=f"Карты: {alien_name.capitalize()}"))
		else:
			logging.warning(f"Файл не найден: {essence_path}")

	if media:
		try:
			bot.send_media_group(chat_id, media)
			alien_stats = get_alien_stats(alien_name)
			games_count = len(alien_stats)
			if alien_stats == []: return

			winrate = len([i for i in alien_stats if i['is_winner']]) / games_count * 100
			avg_est = sum([i['estimation'] for i in alien_stats])

			games_ids = [i['game_id'] for i in alien_stats]
			other_estimations = []
			for game in alien_stats:
				game_players = get_game_players(game['game_id'])
				alien_player = [i['player_id'] for i in game_players if i['alien'] == alien_name][0]
				[other_estimations.append((i['estimation'], i['is_winner'])) for i in game_players if i['player_id'] != alien_player]

			winrate_vs_alien = format_integer(round(len([i for i in other_estimations if i[1]]) / len(other_estimations)*100, 2))
			avg_est_vs_alien = format_integer(sum([i[0] for i in other_estimations]) / len(other_estimations))

			bot.send_message(chat_id,
				f'👽 *Статистика пришельца:*\n\n'
				f'🎮 Кол-во игр: *{games_count}*\n'
				f'🏆 Процент побед: *{format_integer(round(winrate, 2))}%*\n'
				f'⚔️ Винрейт остальных с персонажем: *{format_integer(round(winrate_vs_alien, 2))}%*\n'
				f'🌟 Средняя оценка игр: *{format_integer(round(avg_est, 2))}*\n'
				f'⭐ Оценка игры против персонажа: *{format_integer(round(avg_est_vs_alien, 2))}*',
				parse_mode='Markdown'
			)

		except Exception as e:
			logging.error(f"Ошибка при отправке альбома: {e}")
			bot.send_message(chat_id, "Ошибка при отправке изображений")
	else:
		if is_private: bot.send_message(chat_id, f"{alien_name}.\nА где а нет")

def create_game_message(game_id, creator_id, comment, dlc_list, game_players):
	creator = bot.get_chat(creator_id).username or f"User{creator_id}"
	dlc_str = ", ".join(dlc_list) if dlc_list else "Без дополнений"
	text = f"Новая игра #{game_id}\nСоздатель: @{creator}\nКомментарий: {comment}\nДополнения: {dlc_str}\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

	if game_players.get(game_id):
		text += "\nИгроки: "
		for i in game_players[game_id]:
			text += '\n'+ (i.username if i.username else i.first_name)

	keyboard = InlineKeyboardMarkup()
	keyboard.add(InlineKeyboardButton("Присоединиться/Выйти", callback_data=f"join_game:{game_id}"))
	keyboard.add(InlineKeyboardButton("Проверка", callback_data=f"check_game:{game_id}"))
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

def send_rating_request(chat_id, game_id, player_id, is_winner):
	keyboard = InlineKeyboardMarkup(row_width=5)
	for i in range(1, 6):
		keyboard.add(InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate:{game_id}:{player_id}:{is_winner}:{i}"))
	bot.send_message(chat_id, "Оцените игру (1-5 звезд):", reply_markup=keyboard)

def send_achieve_info(chat_id, player_id, achievement_id, message_id=None):
	achievement = sorted(list(ACHIEVEMENTS.keys()))[achievement_id]
	achievement_info = ACHIEVEMENTS[achievement]
	keyboard = InlineKeyboardMarkup()

	player_achievements = [i['achievement'] for i in get_player_achievements(player_id)]

	if achievement not in player_achievements:
		keyboard.add(InlineKeyboardButton("✅ Получить достижение", callback_data=f"add_achieve:{achievement_id}:{player_id}"))
	else:
		keyboard.add(InlineKeyboardButton("❌ Убрать достижение", callback_data=f"del_achieve:{achievement_id}:{player_id}"))

	text = f"Достижение: {achievement}\n{achievement_info}"
	if not message_id:
		bot.send_message(chat_id, text, reply_markup=keyboard)
	else:
		bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)

@bot.message_handler(commands=['ceval'])
def eval_message(message):
	if message.from_user.id == 818175547:
		bot.send_message(message.chat.id, str(eval(message.text.replace('/ceval ', ''))))

@bot.message_handler(commands=['analysis'])
def analysis_handler(message):
	with open('data/analysis.txt') as f:
		analysis = f.read().split('///')

	for i in analysis:
		bot.reply_to(message, i)

@bot.message_handler(commands=['site'])
def site_message(message):
	keyboard = InlineKeyboardMarkup()
	keyboard.add(InlineKeyboardButton(text="Сайт", url="https://3g.stariybog.ru/cc/"))
	keyboard.add(InlineKeyboardButton(text="Эмоджи", url="https://t.me/addemoji/CosmicEncounter"))

	bot.reply_to(message, 'Омагад!!!\nСайт со статистикой - https://3g.stariybog.ru/cc/\nЭмоджи Космик Енкаунтер - https://t.me/addemoji/CosmicEncounter', reply_markup=keyboard)

@bot.message_handler(commands=['start'])
def send_welcome(message):
	try:
		add_player(bot.get_chat(message.from_user.id))
		bot.reply_to(message, "Напиши нужного пришельца или выбери его в /aliens")
	except Exception as e:
		logging.error(f"Ошибка в send_welcome: {e}")

@bot.message_handler(commands=['achievements'])
def achievements_handler(message):
	send_achievements_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['stations'])
def stations_handler(message):
	send_stations_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['technologies', 'tech'])
def stations_handler(message):
	send_technologies_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['artifacts'])
def artifacts_handler(message):
	send_artifacts_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['hazards'])
def stations_handler(message):
	send_hazards_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['aliens'])
def aliens_handler(message):
	send_alien_page(chat_id=message.chat.id, message_id=None, page=0)

def format_integer(okak):
	return okak if okak != int(okak) else int(okak)

def winrate_calculator(player_games):
	try: wr = len([i for i in player_games if i['am_i_winner']]) / len(player_games) * 100
	except: wr = 0
	wr = format_integer(wr)
	wr = round(wr, 2)
	return wr

def average_estimation_calculator(player_games):
	try: avg_est = sum([i['my_estimation'] for i in player_games]) / len(player_games)
	except: avg_est = 0
	avg_est = format_integer(avg_est)
	avg_est = round(avg_est, 2)
	return avg_est

@bot.message_handler(commands=['history'])
def player_history(message):
	player_games = get_player_stats(message.from_user.id)

	if not player_games:
		bot.reply_to(message, "У тебя пока нет сыгранных игр.")
		return

	send_history_page(message.chat.id, player_games, page=0)

@bot.message_handler(commands=['profile'])
def user_profile(message):
	player_games = get_player_stats(message.from_user.id)

	wl = ' '.join(['W' if i['am_i_winner'] else 'L' for i in player_games][:5])

	player_achievements = get_player_achievements(message.from_user.id)

	winrate = winrate_calculator(player_games)
	avg_est = average_estimation_calculator(player_games)
	aliens_stats = {i: [] for i in ALIENS}
	for game in player_games:
		aliens_stats[game['my_alien']].append(game)

	alien_stat_message = ""
	for alien in sorted(aliens_stats, key=lambda x: len(aliens_stats[x])):
		alien_games = aliens_stats[alien]
		if alien_games == []: continue
		alien_winrate = winrate_calculator(alien_games)
		alien_avg_est = average_estimation_calculator(alien_games)
		alien_stat_message+=f"\n  • {alien.capitalize()} - {len(alien_games)} игр, {alien_winrate}% побед, {alien_avg_est}⭐️"

	achievements_message = "\n🥇 Достижения игрока" #за достижения вписать
	for achievement in player_achievements:
		achievements_message += f"\n  • {achievement['achievement']} - {achievement['date'].strftime('%d.%m.%Y %H:%M')}"

	resp_mes = f"👤 Игрок: {bot.get_chat(message.from_user.id).username}\n🏆 {wl}\n🏅 Победы: {winrate}% | ⭐️ Средняя оценка: {avg_est}\n\n🧬 Пришельцы: {alien_stat_message}\n{achievements_message}"
	bot.reply_to(message, resp_mes)

@bot.message_handler(commands=['party'])
def party_menu(message):
	try:
		msg = bot.reply_to(message, "Введите комментарий к игре:")
		bot.register_next_step_handler(msg, handle_game_comment, message.from_user.id)
	except Exception as e:
		logging.error(f"Ошибка в party_menu: {e}")

def generate_dlc_keyboard(creator_id):
	dlcs = pending_games.get(creator_id, {'dlcs': set()})['dlcs']
	keyboard = InlineKeyboardMarkup(row_width=2)
	for dlc in DLC_LIST:
		text = f"✅ {dlc.capitalize()}" if dlc in dlcs else dlc.capitalize()
		keyboard.add(InlineKeyboardButton(text, callback_data=f"dlc:{creator_id}:{dlc}"))
	keyboard.add(InlineKeyboardButton("Создать игру", callback_data=f"create_game:{creator_id}"))
	return keyboard

def handle_game_comment(message, creator_id):
	comment = message.text.strip()
	pending_games[creator_id] = {'comment': comment, 'dlcs': set()}
	bot.send_message(message.chat.id, "Выберите дополнения (можно несколько):", reply_markup=generate_dlc_keyboard(creator_id))

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

		elif action == "station":
			_, station_index, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_other_photos(call.message.chat.id, list(STATIONS)[int(station_index)])
			send_stations_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id)

		elif action == "tech":
			_, technology_index, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_other_photos(call.message.chat.id, list(TECHNOLOGIES)[int(technology_index)])
			send_technologies_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id, 'FFFFFFFFFFFFFFFF'+str(technology_index))

		elif action == "hazard":
			_, hazard_index, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_other_photos(call.message.chat.id, list(HAZARDS)[int(hazard_index)])
			send_hazards_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id)

		elif action == "art":
			_, art_index, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_other_photos(call.message.chat.id, sorted(list(ARTIFACTS))[int(art_index)])
			send_artifacts_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id)

		elif action == "change_rating":
			game_id, is_winner = map(int, data[1:3])
			player_id = call.from_user.id
			send_rating_request(call.message.chat.id, game_id, player_id, is_winner)
			bot.answer_callback_query(call.id, "Выберите новую оценку")

		elif action == "deletegame":
			_, game_id = data
			game_id = int(game_id)
			game = get_game(game_id)
			if len(get_game_players(game_id)) > 2:
				bot.answer_callback_query(call.id, "Игру нельзя удалить - она не пустая")
				return
			if game['creator_id'] == call.from_user.id:
				delete_game(game_id)
				bot.answer_callback_query(call.id, "Игра удалена и восстановлению не подлежит")
				player_games = get_player_stats(call.from_user.id)
				send_history_page(call.message.chat.id, player_games, 0, call.message.message_id)
			else:
				bot.answer_callback_query(call.id, "Нэт, ты не создатель")

		elif action == "history":
			_, page_str = data
			page = int(page_str)
			player_games = get_player_stats(call.from_user.id)

			if not player_games:
				bot.answer_callback_query(call.id, "История не найдена.")
				return

			send_history_page(call.message.chat.id, player_games, page, call.message.message_id)
			bot.answer_callback_query(call.id)

		elif action == "comment_game":
			_, game_id = data
			game_id = int(game_id)
			pending_comments[call.from_user.id] = game_id
			bot.send_message(call.message.chat.id, f"Напиши комментарий к игре #{game_id}:")

		elif action == "add_achieve":
			_, achieve_index, player_id = data
			if int(player_id) != call.from_user.id:
				bot.answer_callback_query(call.id, "Ты не ты чето я не я")
				return
			achievement_name = sorted(list(ACHIEVEMENTS.keys()))[int(achieve_index)]
			add_player_achievement(int(player_id), achievement_name)
			send_achieve_info(call.message.chat.id, call.from_user.id, message_id=call.message.id, achievement_id=int(achieve_index))
			bot.answer_callback_query(call.id)

		elif action == "del_achieve":
			_, achieve_index, player_id = data
			if int(player_id) != call.from_user.id:
				bot.answer_callback_query(call.id, "Ты не ты чето я не я")
				return
			achievement_name = sorted(list(ACHIEVEMENTS.keys()))[int(achieve_index)]
			delete_player_achievement(int(player_id), achievement_name)
			send_achieve_info(call.message.chat.id, call.from_user.id, message_id=call.message.id, achievement_id=int(achieve_index))
			bot.answer_callback_query(call.id)

		elif action == "achieve":
			_, achieve_index, page_str = data
			page = int(page_str)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			send_achieve_info(call.message.chat.id, call.from_user.id, message_id=None, achievement_id=int(achieve_index))
			send_achievements_page(call.message.chat.id, message_id=None, page=page)
			bot.answer_callback_query(call.id)

		elif action == "page":
			page = int(data[1])
			game_id = int(data[2]) if len(data) > 2 else None
			player_id = int(data[3]) if len(data) > 3 else None

			if player_id is not None and player_id != call.from_user.id:
				bot.answer_callback_query(call.id, "Ты не ты чето я не я")
				return

			send_alien_page(call.message.chat.id, call.message.message_id, page, game_id, player_id)
			bot.answer_callback_query(call.id)

		elif action == "achieve_page":
			page = int(data[1])
			send_achievements_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

		elif action == "tech_page":
			page = int(data[1])
			send_technologies_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

		elif action == "art_page":
			page = int(data[1])
			send_artifacts_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

		elif action == "hazard_page":
			page = int(data[1])
			send_hazards_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

		elif action == "station_page":
			page = int(data[1])
			send_stations_page(call.message.chat.id, call.message.message_id, page)
			bot.answer_callback_query(call.id)

		elif action == "dlc":
			creator_id, dlc = data[1], data[2]
			creator_id = int(creator_id)
			if creator_id != call.from_user.id:
				bot.answer_callback_query(call.id, "Только создатель может выбирать дополнения!")
				return
			dlcs = pending_games.setdefault(creator_id, {'comment': '', 'dlcs': set()})['dlcs']
			if dlc in dlcs:
				dlcs.remove(dlc)
				bot.answer_callback_query(call.id, f"Убрано: {dlc}")
			else:
				dlcs.add(dlc)
				bot.answer_callback_query(call.id, f"Добавлено: {dlc}")
			bot.edit_message_reply_markup(
				chat_id=call.message.chat.id,
				message_id=call.message.message_id,
				reply_markup=generate_dlc_keyboard(creator_id)
			)

		elif action == "create_game":
			creator_id = int(data[1])
			if not check_player(creator_id):
				bot.answer_callback_query(call.id, "Напишите /start боту в личку")
				return
			if creator_id not in pending_games:
				bot.answer_callback_query(call.id, "Ошибка: комментарий не найден")
				return
			comment = pending_games[creator_id]['comment']
			dlc_list = list(pending_games[creator_id]['dlcs'])
			game_id = create_game(comment, dlc_list, creator_id)

			text, keyboard = create_game_message(game_id, creator_id, comment, dlc_list, pending_game_players)
			pending_game_players[game_id] = []
			bot.send_message(call.message.chat.id, text, reply_markup=keyboard)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			del pending_games[creator_id]
			bot.answer_callback_query(call.id)

		elif action == "check_game":
			game_id = int(data[1])
			r_message = ''
			players = get_game_players(game_id)
			for i in players:
				if not i['alien']:
					r_message += f"Типуля @{bot.get_chat(i['player_id']).username} не выбрал пришельца!\n"
				else:
					r_message += f"@{bot.get_chat(i['player_id']).username} выбрал персонажа \"{i['alien'].capitalize()}\"\n"
			bot.send_message(call.message.chat.id, r_message or "Никто не пришел играть в кк...")
			bot.answer_callback_query(call.id)

		elif action == "join_game":
			game_id = int(data[1])
			player_id = call.from_user.id
			if not check_player(player_id):
				bot.answer_callback_query(call.id, "Напишите /start боту в личку")
				return
			if is_player_in_game(game_id, player_id):
				leave_from_game(game_id, player_id)
				bot.answer_callback_query(call.id, "Вы вышли из игры!")
				n = 0
				for i in pending_game_players[game_id]:
					if i.id == player_id:
						pending_game_players[game_id].pop(n)
					n+=1

			else:
				join_game(game_id, player_id)
				bot.send_message(player_id, f"Введите имя пришельца")
				waitlist[player_id] = {'action':'select_alien', 'game_id':game_id}
				bot.answer_callback_query(call.id, "Выберите пришельца")
				pending_game_players[game_id].append(call.from_user)

			game_data = get_game(game_id)
			creator_id = game_data['creator_id']
			dlc_list = game_data['dlc'].split(', ')
			comment = game_data['comment']
			text, keyboard = create_game_message(game_id, creator_id, comment, dlc_list, pending_game_players)
			bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=text, reply_markup=keyboard)

		elif action == "select_alien":
			_, alien_name, page_str, game_id, player_id = data
			game_id, player_id = int(game_id), int(player_id)
			if get_game(game_id)['is_over']:
				bot.delete_message(call.message.chat.id, call.message.message_id)
				bot.answer_callback_query(call.id, "Игра уже завершена!")
				return
			try:
				join_game(game_id, player_id, alien_name)
				bot.delete_message(call.message.chat.id, call.message.message_id)
				bot.send_message(player_id, f"Вы выбрали пришельца: {alien_name.capitalize()}")
				bot.answer_callback_query(call.id, "Пришелец выбран!")
			except ValueError:
				bot.answer_callback_query(call.id, "Неверный пришелец, выберите снова")
				send_alien_page(player_id, None, 0, game_id, player_id)

		elif action == "end_game":
			game_id, creator_id = map(int, data[1:3])
			if call.from_user.id != creator_id:
				bot.answer_callback_query(call.id, "Только создатель может завершить игру!")
				return
			players = get_game_players(game_id)
			for i in players:
				if not i['alien']:
					bot.answer_callback_query(call.id, f"Типуля @{bot.get_chat(i['player_id']).username} не выбрал пришельца!")
					return
			mark_game_as_over(game_id)
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
				logging.debug(is_winner)
				set_player_result(game_id, player['player_id'], is_winner, None)
				send_rating_request(player['player_id'], game_id, player['player_id'], int(is_winner))

			bot.delete_message(call.message.chat.id, call.message.message_id)
			selected_winners.pop(game_id, None)
			bot.answer_callback_query(call.id, "Игра завершена")

		elif action == "rate":
			game_id, player_id, is_winner, rating = map(int, data[1:5])
			set_player_result(game_id, player_id, bool(is_winner), rating)
			bot.delete_message(call.message.chat.id, call.message.message_id)
			bot.answer_callback_query(call.id, "Оценка сохранена")

	except Exception as e:
		logging.error(f"Ошибка в callback_handler: {e}")
		bot.answer_callback_query(call.id, "Произошла ошибка")
		raise

@bot.message_handler(commands=['e'])
def catch_custom_emoji(message):
	if message.entities:
		for ent in message.entities:
			if ent.type == 'custom_emoji':
				custom_emoji_id = ent.custom_emoji_id
				bot.send_message(message.chat.id, f'Эмоджи: `\"{message.text.split(":")[-1]}\": {custom_emoji_id},`', parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.from_user.id in pending_comments)
def save_comment_handler(message):
	game_id = pending_comments.pop(message.from_user.id)
	comment = message.text.strip()

	set_player_comment(game_id, message.from_user.id, comment)

	bot.send_message(message.chat.id, f"Комментарий к игре #{game_id} сохранён ✅")

@bot.message_handler(func=lambda message: message.chat.id == message.from_user.id)
def send_alien_image(message):
	player_id = message.from_user.id
	if player_id in waitlist:
		pending_data = waitlist[player_id]
		if pending_data['action'] == 'select_alien':
			game_id = pending_data['game_id']
			loc_rev = {k.lower(): i for i, k in LOCALIZATION_EN.items()}

			alien = message.text.lower().strip()
			if alien in loc_rev:
				alien = loc_rev[alien]
			if alien not in ALIENS:
				bot.reply_to(message, "Такого пришельца нет, попробуй еще")
				return

			if get_game(game_id)['is_over']:
				bot.reply_to(message, "Игра уже завершена")
				del(waitlist[player_id])
				return
			try:
				join_game(game_id, player_id, alien)
				bot.reply_to(message, f"Вы выбрали пришельца: {alien.capitalize()}")
				del(waitlist[player_id])
			except ValueError:
				bot.reply_to(message, "Неверный пришелец, выберите снова")
	try:
		alien_name = message.text.replace('ё', 'е').lower().strip()
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
