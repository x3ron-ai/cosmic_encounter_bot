import logging
from telebot.types import CallbackQuery
from cc_data import ALIENS, ESSENCE_ALIENS, FLARES, TECHNOLOGIES, HAZARDS, STATIONS, LOCALIZATION_EN, ACHIEVEMENTS, ARTIFACTS
from stats import *
from utils import *

_actions_registry = {}

def register_action(action):
	def decorator(func):
		_actions_registry[action] = func
		return func
	return decorator

class CallbackHandler:
	def __init__(self, bot):
		self.bot = bot

	def handle(self, call: CallbackQuery):
		try:
			data = call.data.split(":")
			action = data[0]
			
			if action in _actions_registry:
				_actions_registry[action](self, call, data[1:])
			else:
				logging.error(f"Неизвестное действие: {action}")
				self.bot.answer_callback_query(call.id, "Неизвестное действие")
		
		except Exception as e:
			logging.error(f"Ошибка в обработчике callback: {e}")
			self.bot.answer_callback_query(call.id, f"Произошла ошибка: {str(e)}")

	def _handle_page_with_photo(self, call: CallbackQuery, data, data_source, send_photo_func, send_page_func, extra_text=""):
		try:
			index, page_str = data
			page = int(page_str)
			self.bot.delete_message(call.message.chat.id, call.message.message_id)
			send_photo_func(call.message.chat.id, list(data_source)[int(index)])
			send_page_func(call.message.chat.id, message_id=None, page=page)
			self.bot.answer_callback_query(call.id, extra_text)
		except (IndexError, ValueError) as e:
			logging.error(f"Ошибка в _handle_page_with_photo: {e}")
			self.bot.answer_callback_query(call.id, "Неверные данные для навигации")

	@register_action("alien")
	def handle_alien(self, call: CallbackQuery, data):
		alien_name, page_str = data
		page = int(page_str)
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		send_alien_photos(call.message.chat.id, alien_name)
		send_alien_page(call.message.chat.id, message_id=None, page=page)
		self.bot.answer_callback_query(call.id)
		
	@register_action("station")
	def handle_station(self, call: CallbackQuery, data):
		self._handle_page_with_photo(call, data, STATIONS, send_other_photos, send_stations_page)

	@register_action("tech")
	def handle_tech(self, call: CallbackQuery, data):
		self._handle_page_with_photo(call, data, TECHNOLOGIES, send_other_photos, send_technologies_page)

	@register_action("hazard")
	def handle_hazard(self, call: CallbackQuery, data):
		self._handle_page_with_photo(call, data, HAZARDS, send_other_photos, send_hazards_page)

	@register_action("art")
	def handle_art(self, call: CallbackQuery, data):
		self._handle_page_with_photo(call, data, sorted(list(ARTIFACTS)), send_other_photos, send_artifacts_page)

	@register_action("change_rating")
	def handle_change_rating(self, call: CallbackQuery, data):
		game_id, is_winner = map(int, data)
		player_id = call.from_user.id
		send_rating_request(call.message.chat.id, game_id, player_id, is_winner)
		self.bot.answer_callback_query(call.id, "Выберите новую оценку")

	@register_action("deletegame")
	def handle_delete_game(self, call: CallbackQuery, data):
		game_id = int(data[0])
		game = get_game(game_id)
		if len(get_game_players(game_id)) > 2:
			self.bot.answer_callback_query(call.id, "Игру нельзя удалить - она не пустая")
			return
		if game['creator_id'] == call.from_user.id:
			delete_game(game_id)
			self.bot.answer_callback_query(call.id, "Игра удалена и восстановлению не подлежит")
			player_games = get_player_stats(call.from_user.id)
			send_history_page(call.message.chat.id, player_games, 0, call.message.message_id)
		else:
			self.bot.answer_callback_query(call.id, "Нэт, ты не создатель")

	@register_action("history")
	def handle_history(self, call: CallbackQuery, data):
		page = int(data[0])
		player_games = get_player_stats(call.from_user.id)
		if not player_games:
			self.bot.answer_callback_query(call.id, "История не найдена.")
			return
		send_history_page(call.message.chat.id, player_games, page, call.message.message_id)
		self.bot.answer_callback_query(call.id)

	@register_action("comment_game")
	def handle_comment_game(self, call: CallbackQuery, data):
		game_id = int(data[0])
		pending_comments[call.from_user.id] = game_id
		self.bot.send_message(call.message.chat.id, f"Напиши комментарий к игре #{game_id}:")

	@register_action("add_achieve")
	def handle_add_achieve(self, call: CallbackQuery, data):
		achieve_index, player_id = data
		if int(player_id) != call.from_user.id:
			self.bot.answer_callback_query(call.id, "Ты не ты чето я не я")
			return
		achievement_name = sorted(list(ACHIEVEMENTS.keys()))[int(achieve_index)]
		add_player_achievement(int(player_id), achievement_name)
		send_achieve_info(call.message.chat.id, call.from_user.id, message_id=call.message.id, achievement_id=int(achieve_index))
		self.bot.answer_callback_query(call.id)

	@register_action("del_achieve")
	def handle_del_achieve(self, call: CallbackQuery, data):
		achieve_index, player_id = data
		if int(player_id) != call.from_user.id:
			self.bot.answer_callback_query(call.id, "Ты не ты чето я не я")
			return
		achievement_name = sorted(list(ACHIEVEMENTS.keys()))[int(achieve_index)]
		delete_player_achievement(int(player_id), achievement_name)
		send_achieve_info(call.message.chat.id, call.from_user.id, message_id=call.message.id, achievement_id=int(achieve_index))
		self.bot.answer_callback_query(call.id)

	@register_action("achieve")
	def handle_achieve(self, call: CallbackQuery, data):
		achieve_index, page_str = data
		page = int(page_str)
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		send_achieve_info(call.message.chat.id, call.from_user.id, message_id=None, achievement_id=int(achieve_index))
		send_achievements_page(call.message.chat.id, message_id=None, page=page)
		self.bot.answer_callback_query(call.id)

	@register_action("page")
	def handle_page(self, call: CallbackQuery, data):
		page = int(data[0])
		game_id = int(data[1]) if len(data) > 1 else None
		player_id = int(data[2]) if len(data) > 2 else None
		if player_id is not None and player_id != call.from_user.id:
			self.bot.answer_callback_query(call.id, "Ты не ты чето я не я")
			return
		send_alien_page(call.message.chat.id, call.message.message_id, page, game_id, player_id)
		self.bot.answer_callback_query(call.id)

	@register_action("achieve_page")
	def handle_achieve_page(self, call: CallbackQuery, data):
		page = int(data[0])
		send_achievements_page(call.message.chat.id, call.message.message_id, page)
		self.bot.answer_callback_query(call.id)

	@register_action("tech_page")
	def handle_tech_page(self, call: CallbackQuery, data):
		page = int(data[0])
		send_technologies_page(call.message.chat.id, call.message.message_id, page)
		self.bot.answer_callback_query(call.id)

	@register_action("art_page")
	def handle_art_page(self, call: CallbackQuery, data):
		page = int(data[0])
		send_artifacts_page(call.message.chat.id, call.message.message_id, page)
		self.bot.answer_callback_query(call.id)

	@register_action("hazard_page")
	def handle_hazard_page(self, call: CallbackQuery, data):
		page = int(data[0])
		send_hazards_page(call.message.chat.id, call.message.message_id, page)
		self.bot.answer_callback_query(call.id)

	@register_action("station_page")
	def handle_station_page(self, call: CallbackQuery, data):
		page = int(data[0])
		send_stations_page(call.message.chat.id, call.message.message_id, page)
		self.bot.answer_callback_query(call.id)

	@register_action("dlc")
	def handle_dlc(self, call: CallbackQuery, data):
		creator_id, dlc = data
		creator_id = int(creator_id)
		if creator_id != call.from_user.id:
			self.bot.answer_callback_query(call.id, "Только создатель может выбирать дополнения!")
			return
		dlcs = pending_games.setdefault(creator_id, {'comment': '', 'dlcs': set()})['dlcs']
		if dlc in dlcs:
			dlcs.remove(dlc)
			self.bot.answer_callback_query(call.id, f"Убрано: {dlc}")
		else:
			dlcs.add(dlc)
			self.bot.answer_callback_query(call.id, f"Добавлено: {dlc}")
		self.bot.edit_message_reply_markup(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			reply_markup=generate_dlc_keyboard(creator_id)
		)

	@register_action("create_game")
	def handle_create_game(self, call: CallbackQuery, data):
		creator_id = int(data[0])
		if not check_player(creator_id):
			self.bot.answer_callback_query(call.id, "Напишите /start боту в личку")
			return
		if creator_id not in pending_games:
			self.bot.answer_callback_query(call.id, "Ошибка: комментарий не найден")
			return
		comment = pending_games[creator_id]['comment']
		dlc_list = list(pending_games[creator_id]['dlcs'])
		game_id = create_game(comment, dlc_list, creator_id)
		text, keyboard = create_game_message(game_id, creator_id, comment, dlc_list, pending_game_players)
		pending_game_players[game_id] = []
		self.bot.send_message(call.message.chat.id, text, reply_markup=keyboard)
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		del pending_games[creator_id]
		self.bot.answer_callback_query(call.id)

	@register_action("check_game")
	def handle_check_game(self, call: CallbackQuery, data):
		game_id = int(data[0])
		r_message = ''
		players = get_game_players(game_id)
		for i in players:
			if not i['alien']:
				r_message += f"Типуля @{self.bot.get_chat(i['player_id']).username} не выбрал пришельца!\n"
			else:
				r_message += f"@{self.bot.get_chat(i['player_id']).username} выбрал персонажа \"{i['alien'].capitalize()}\"\n"
		self.bot.send_message(call.message.chat.id, r_message or "Никто не пришел играть в кк...")
		self.bot.answer_callback_query(call.id)

	@register_action("join_game")
	def handle_join_game(self, call: CallbackQuery, data):
		game_id = int(data[0])
		player_id = call.from_user.id
		if not check_player(player_id):
			self.bot.answer_callback_query(call.id, "Напишите /start боту в личку")
			return
		if is_player_in_game(game_id, player_id):
			leave_from_game(game_id, player_id)
			self.bot.answer_callback_query(call.id, "Вы вышли из игры!")
			for i, player in enumerate(pending_game_players[game_id]):
				if player.id == player_id:
					pending_game_players[game_id].pop(i)
					break
		else:
			join_game(game_id, player_id)
			self.bot.send_message(player_id, f"Введите имя пришельца")
			waitlist[player_id] = {'action': 'select_alien', 'game_id': game_id}
			self.bot.answer_callback_query(call.id, "Выберите пришельца")
			pending_game_players[game_id].append(call.from_user)
		game_data = get_game(game_id)
		creator_id = game_data['creator_id']
		dlc_list = game_data['dlc'].split(', ')
		comment = game_data['comment']
		text, keyboard = create_game_message(game_id, creator_id, comment, dlc_list, pending_game_players)
		self.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=text, reply_markup=keyboard)

	@register_action("select_alien")
	def handle_select_alien(self, call: CallbackQuery, data):
		alien_name, page_str, game_id, player_id = data
		game_id, player_id = int(game_id), int(player_id)
		if get_game(game_id)['is_over']:
			self.bot.delete_message(call.message.chat.id, call.message.message_id)
			self.bot.answer_callback_query(call.id, "Игра уже завершена!")
			return
		try:
			join_game(game_id, player_id, alien_name)
			self.bot.delete_message(call.message.chat.id, call.message.message_id)
			self.bot.send_message(player_id, f"Вы выбрали пришельца: {alien_name.capitalize()}")
			self.bot.answer_callback_query(call.id, "Пришелец выбран!")
		except ValueError:
			self.bot.answer_callback_query(call.id, "Неверный пришелец, выберите снова")
			send_alien_page(player_id, None, 0, game_id, player_id)

	@register_action("end_game")
	def handle_end_game(self, call: CallbackQuery, data):
		game_id, creator_id = map(int, data)
		if call.from_user.id != creator_id:
			self.bot.answer_callback_query(call.id, "Только создатель может завершить игру!")
			return
		players = get_game_players(game_id)
		for i in players:
			if not i['alien']:
				self.bot.answer_callback_query(call.id, f"Типуля @{self.bot.get_chat(i['player_id']).username} не выбрал пришельца!")
				return
		mark_game_as_over(game_id)
		send_winner_selection(call.message.chat.id, game_id)
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		self.bot.answer_callback_query(call.id)

	@register_action("winner_toggle")
	def handle_winner_toggle(self, call: CallbackQuery, data):
		game_id, player_id = int(data[0]), int(data[1])
		winners = selected_winners.setdefault(game_id, set())
		if player_id in winners:
			winners.remove(player_id)
			self.bot.answer_callback_query(call.id, "Победитель убран")
		else:
			winners.add(player_id)
			self.bot.answer_callback_query(call.id, "Победитель добавлен")
		self.bot.edit_message_reply_markup(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			reply_markup=generate_updated_winner_keyboard(game_id, call.message.chat.id)
		)

	@register_action("finalize_game")
	def handle_finalize_game(self, call: CallbackQuery, data):
		game_id = int(data[0])
		winners = selected_winners.get(game_id, set())
		players = get_game_players(game_id)
		for player in players:
			is_winner = player['player_id'] in winners
			set_player_result(game_id, player['player_id'], is_winner, None)
			send_rating_request(player['player_id'], game_id, player['player_id'], int(is_winner))
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		game_members = ""
		for i in players:
			is_winner = i['player_id'] in winners
			game_members += f"{'🏆' if is_winner else '❌'} @{self.bot.get_chat(i['player_id']).username} - {i['alien']}\n"
		self.bot.send_message(call.message.chat.id, f"Игра #{game_id} завершена!\nПоставьте оценку игре в личных сообщениях\nУчастники игры:\n{game_members}")
		selected_winners.pop(game_id, None)
		self.bot.answer_callback_query(call.id, "Игра завершена")

	@register_action("rate")
	def handle_rate(self, call: CallbackQuery, data):
		game_id, player_id, is_winner, rating = map(int, data)
		set_player_result(game_id, player_id, bool(is_winner), rating)
		self.bot.delete_message(call.message.chat.id, call.message.message_id)
		self.bot.answer_callback_query(call.id, "Оценка сохранена")

	@register_action("random")
	def handle_random(self, call: CallbackQuery, data):
		text, keyboard = show_random_alien()
		self.bot.answer_callback_query(call.id, "random...")
		self.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=text, reply_markup=keyboard)

def setup_callback_handler(bot):
	handler = CallbackHandler(bot)
	@bot.callback_query_handler(func=lambda call: True)
	def callback_query(call: CallbackQuery):
		handler.handle(call)
