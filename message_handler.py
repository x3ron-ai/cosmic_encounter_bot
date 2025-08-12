import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from cc_data import ALIENS, LOCALIZATION_EN
from stats import *
from utils import *
from bot_instance import bot
from callback_handler import setup_callback_handler
import random

setup_callback_handler(bot)

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
def technologies_handler(message):
	send_technologies_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['artifacts'])
def artifacts_handler(message):
	send_artifacts_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['hazards'])
def hazards_handler(message):
	send_hazards_page(chat_id=message.chat.id, message_id=None, page=0)

@bot.message_handler(commands=['aliens'])
def aliens_handler(message):
	send_alien_page(chat_id=message.chat.id, message_id=None, page=0)

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

	from collections import defaultdict
	aliens_stats = defaultdict(list)
	for game in player_games:
		aliens_stats[game['my_alien']].append(game)

	alien_stat_message = ""
	for alien in sorted(aliens_stats, key=lambda x: len(aliens_stats[x])):
		alien_games = aliens_stats[alien]
		if not alien_games: continue
		alien_winrate = winrate_calculator(alien_games)
		alien_avg_est = average_estimation_calculator(alien_games)
		alien_stat_message += f"\n  • {alien.capitalize()} - {len(alien_games)} игр, {alien_winrate}% побед, {alien_avg_est}⭐️"

	achievements_message = "\n🥇 Достижения игрока"
	for achievement in player_achievements:
		achievements_message += f"\n  • {achievement['achievement']} - {achievement['date'].strftime('%d.%m.%Y %H:%M')}"

	resp_mes = f"👤 Игрок: {bot.get_chat(message.from_user.id).username}\n🏆 {wl}\n🏅 Победы: {winrate}% | ⭐️ Средняя оценка: {avg_est}\n\n🧬 Пришельцы: {alien_stat_message}\n{achievements_message}"
	bot.reply_to(message, resp_mes)

@bot.message_handler(commands=['party'])
def party_menu(message):
	try:
		msg = bot.reply_to(message, "Введите название к игре:")
		bot.register_next_step_handler(msg, handle_game_comment, message.from_user.id)
	except Exception as e:
		logging.error(f"Ошибка в party_menu: {e}")

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
			alien = message.text.lower().strip().replace('ё', 'е')
			if alien in loc_rev:
				alien = loc_rev[alien]
			if alien not in ALIENS:
				bot.reply_to(message, "Такого пришельца нет, попробуй еще")
				return
			if get_game(game_id)['is_over']:
				bot.reply_to(message, "Игра уже завершена")
				del waitlist[player_id]
				return
			try:
				join_game(game_id, player_id, alien)
				bot.reply_to(message, f"Вы выбрали пришельца: {alien.capitalize()}")
				del waitlist[player_id]
			except ValueError:
				bot.reply_to(message, "Неверный пришелец, выберите снова")
	try:
		alien_name = message.text.replace('ё', 'е').lower().strip()
		send_alien_photos(message.chat.id, alien_name, message.chat.id == message.from_user.id)
	except Exception as e:
		logging.error(f"Ошибка в send_alien_image: {e}")

