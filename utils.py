import telebot, os, logging, math
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from cc_data import ALIENS, ESSENCE_ALIENS, FLARES, TECHNOLOGIES, HAZARDS, STATIONS, LOCALIZATION_EN, ACHIEVEMENTS, ARTIFACTS
from stats import *
from datetime import datetime
from bot_instance import bot
import random

ITEMS_PER_PAGE = 10
BUTTONS_PER_ROW = 2
DLC_LIST = ['технологии', 'награды', 'маркеры кораблей', 'диски союзов', 'космические станции', 'карточки угроз']
pending_games = {}
pending_game_players = {}
waitlist = {}
selected_winners = {}
pending_comments = {}

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
			avg_est = sum([i['estimation'] or 0 for i in alien_stats])

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
	else:
		if is_private: bot.send_message(chat_id, f"{alien_name}.\nА где а нет")

def show_random_alien():
	keyboard = InlineKeyboardMarkup()
	keyboard.add(InlineKeyboardButton("🎲 Перебросить", callback_data=f"random"))
	random_alien = random.choice(list(ALIENS.keys())).capitalize()
	return f"🎲 Рандомный пришелец:\n{random_alien}", keyboard

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
