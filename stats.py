import psycopg2
from psycopg2.extras import RealDictCursor
from aliens import aliens
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
	logging.info(f"Connecting to database with params: {DB_PARAMS}")
	try:
		conn = psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)
		logging.info("Successfully connected to database")
		return conn
	except Exception as e:
		logging.error(f"Failed to connect to database: {e}")
		raise

def add_player(telegram_id):
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("INSERT INTO players (id) VALUES (%s) ON CONFLICT DO NOTHING", (telegram_id,))

def create_game(comment, dlc_list, creator_id):
	dlc_str = ", ".join(dlc_list) if dlc_list else ""
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute("INSERT INTO games (comment, dlc, creator_id) VALUES (%s, %s, %s) RETURNING id", (comment, dlc_str, creator_id))
			return cur.fetchone()['id']

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

def join_game(game_id, player_id, alien_name):
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
					gp.is_winner AS am_i_winner
				FROM games g
				JOIN game_players gp ON g.id = gp.game_id
				WHERE gp.player_id = %s
				ORDER BY g.date DESC
			""", (player_id,))
			games = cur.fetchall()

			# Для каждого найденного game_id — достаём остальных игроков
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

			return games
