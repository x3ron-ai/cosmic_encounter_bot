import psycopg2
from psycopg2.extras import RealDictCursor
from cc_data import ALIENS as aliens
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

DB_PARAMS = {
	'dbname': os.getenv('DB_NAME'),
	'user': os.getenv('DB_LOGIN'),
	'password': os.getenv('DB_PASS'),
	'host': os.getenv('DB_HOST'),
	'port': os.getenv('DB_PORT')
}

def get_connection():
	try:
		conn = psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)
		return conn
	except Exception as e:
		raise

def check_player(telegram_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT * FROM players WHERE id=%s", (telegram_id,))
			return bool(cur.fetchone())

def add_player(tg_user):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("INSERT INTO players (id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (tg_user.id, tg_user.username or '', tg_user.firstname or ''))

def get_alien_stats(alien):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT * FROM game_players WHERE alien=%s", (alien,))
			return cur.fetchall()

def create_game(comment, dlc_list, creator_id):
	dlc_str = ", ".join(dlc_list) if dlc_list else ""
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("INSERT INTO games (comment, dlc, creator_id) VALUES (%s, %s, %s) RETURNING id", (comment, dlc_str, creator_id))
			return cur.fetchone()['id']

def delete_game(game_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("DELETE FROM game_players WHERE game_id = %s", (game_id,))
			cur.execute("DELETE FROM games WHERE id=%s", (game_id,))
			conn.commit()
			return ":("

def get_game(game_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT * FROM games WHERE id=%s", (game_id,))
			return cur.fetchone()

def list_games():
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT * FROM games ORDER BY date DESC")
			return cur.fetchall()

def join_game(game_id, player_id, alien_name=None):
	if alien_name:
		alien_name = alien_name.lower()
		if alien_name not in aliens:
			raise ValueError("Unknown alien name")

	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				INSERT INTO game_players (game_id, player_id, alien, estimation, is_winner)
				VALUES (%s, %s, %s, NULL, NULL)
				ON CONFLICT DO NOTHING
			""", (game_id, player_id, alien_name))

def leave_from_game(game_id, player_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("DELETE FROM game_players WHERE player_id=%s AND game_id=%s", (player_id,game_id))

def set_player_result(game_id, player_id, is_winner, estimation):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				UPDATE game_players
				SET is_winner = %s,
					estimation = %s
				WHERE game_id = %s AND player_id = %s
			""", (is_winner, estimation, game_id, player_id))

def get_game_players(game_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				SELECT * FROM game_players
				WHERE game_id = %s
			""", (game_id,))
			return cur.fetchall()

def mark_game_as_over(game_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("UPDATE games SET is_over = TRUE WHERE id=%s", (game_id,))
			return 'emae'

def get_game_winners(game_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				SELECT player_id FROM game_players
				WHERE game_id = %s AND is_winner = TRUE
			""", (game_id,))
			return [row['player_id'] for row in cur.fetchall()]

def is_player_in_game(game_id, player_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				SELECT 1 FROM game_players
				WHERE game_id = %s AND player_id = %s
			""", (game_id, player_id))
			return cur.fetchone() is not None

def add_player_achievement(player_id, achievement):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				INSERT INTO player_achievements(player_id, achievement) VALUES (%s, %s)
			""", (player_id, achievement))

def delete_player_achievement(player_id, achievement):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				DELETE FROM player_achievements WHERE player_id = %s AND achievement = %s
			""", (player_id, achievement))

def get_player_achievements(player_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute(
				"SELECT achievement, date FROM player_achievements WHERE player_id = %s ORDER BY date ASC",
				(player_id,)
			)
			return cur.fetchall()

def get_player_stats(player_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("""
				SELECT
					g.id AS game_id,
					g.comment,
					g.dlc,
					g.creator_id,
					g.date,
					gp.alien AS my_alien,
					gp.estimation AS my_estimation,
					gp.is_winner AS am_i_winner,
					gp.player_id
				FROM games g
				LEFT JOIN game_players gp ON g.id = gp.game_id AND gp.player_id = %s
				WHERE g.creator_id = %s OR gp.player_id = %s
				ORDER BY g.date DESC
			""", (player_id, player_id, player_id))
			games = cur.fetchall()

			for game in games:
				game_id = game['game_id']
				cur.execute("""
					SELECT
						player_id,
						alien,
						estimation,
						is_winner
					FROM game_players
					WHERE game_id = %s AND player_id != %s
				""", (game_id, player_id))
				game['opponents'] = cur.fetchall()

				if game['player_id'] is None:
					game['player_id'] = player_id
					game['my_alien'] = "НЕ_ИГРОК"
					game['my_estimation'] = 0
					game['am_i_winner'] = False

			return games

