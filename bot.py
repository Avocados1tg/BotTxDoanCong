#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_part1.py — Part 1/4
Core: config, DB, users, balance, helpers
"""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Telegram bot token, bắt buộc
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Telegram ID của admin
DB_PATH = os.getenv("DB_PATH", "casino_full.db")  # Đường dẫn DB SQLite

# ================= DEFAULT SETTINGS =================
DEFAULT_SWITCHES = {
    "taixiu": True,
    "dice": True,
    "roulette": True,
    "troll": True,
    "shop": True,
    "quest": True,
}

# Game parameters
INITIAL_BALANCE = 1000
DAILY_REWARD = 300
DAILY_COOLDOWN_HOURS = 24
MAX_BET = 100_000
MIN_BET = 10
QUEST_MIN = 100
QUEST_MAX = 500

# ================= RANDOM UTIL =================
try:
    from secrets import randbelow
    _rand = randbelow
except ImportError:
    import random
    _sysrand = random.SystemRandom()
    _rand = lambda n: _sysrand.randrange(n)

def now_iso() -> str:
    """Trả về timestamp hiện tại theo ISO format"""
    return datetime.utcnow().isoformat()

# ================= DATABASE UTIL =================
def with_db(func):
    """Decorator: mở DB, commit, close"""
    def wrapper(*args, **kwargs):
        con = sqlite3.connect(DB_PATH)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA foreign_keys=ON;")
        try:
            res = func(con, *args, **kwargs)
            con.commit()
            return res
        finally:
            con.close()
    return wrapper

@with_db
def init_db(con: sqlite3.Connection):
    """Khởi tạo các bảng cơ bản"""
    con.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        balance INTEGER NOT NULL DEFAULT 0,
        last_daily TEXT,
        loss_streak INTEGER NOT NULL DEFAULT 0,
        win_streak INTEGER NOT NULL DEFAULT 0
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game TEXT NOT NULL,
        amount INTEGER NOT NULL,
        choice TEXT NOT NULL,
        result TEXT NOT NULL,
        payout INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS switches (
        key TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS shop (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        acquired_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(item_id) REFERENCES shop(item_id)
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER NOT NULL,
        to_user INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(from_user) REFERENCES users(id),
        FOREIGN KEY(to_user) REFERENCES users(id)
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS quests (
        user_id INTEGER UNIQUE NOT NULL,
        last_claim_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    # Seed switches
    for k, v in DEFAULT_SWITCHES.items():
        con.execute("INSERT OR IGNORE INTO switches(key, value) VALUES (?, ?)", (k, 1 if v else 0))
    # Seed shop items
    seed_items = [
        ("🎩 Top Hat", 1000),
        ("👑 Crown", 5000),
        ("🔥 Fire Badge", 2000),
        ("🍀 Lucky Charm", 1500),
    ]
    for name, price in seed_items:
        exists = con.execute("SELECT 1 FROM shop WHERE name=?", (name,)).fetchone()
        if not exists:
            con.execute("INSERT INTO shop(name, price) VALUES (?, ?)", (name, price))

# ================= USER / BALANCE =================
@with_db
def get_or_create_user(con: sqlite3.Connection, tg_id: int, username: Optional[str]) -> Tuple[int, int]:
    """Tìm user theo tg_id hoặc tạo mới"""
    row = con.execute("SELECT id, balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if row:
        return row[0], row[1]
    con.execute("INSERT INTO users(tg_id, username, balance) VALUES (?,?,?)",
                (tg_id, username, INITIAL_BALANCE))
    uid = con.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()[0]
    return uid, INITIAL_BALANCE

@with_db
def get_user(con: sqlite3.Connection, tg_id: int):
    """Lấy user theo tg_id"""
    return con.execute("SELECT id, username, balance, last_daily, loss_streak, win_streak FROM users WHERE tg_id=?", (tg_id,)).fetchone()

@with_db
def update_balance(con: sqlite3.Connection, user_id: int, new_balance: int):
    """Cập nhật số dư"""
    con.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))

@with_db
def record_bet(con: sqlite3.Connection, user_id: int, game: str, amount: int, choice: str, result: str, payout: int):
    """Lưu lịch sử cược"""
    con.execute("""
    INSERT INTO bets(user_id, game, amount, choice, result, payout, created_at)
    VALUES (?,?,?,?,?,?,?)""", (user_id, game, amount, choice, result, payout, now_iso()))

@with_db
def set_last_daily(con: sqlite3.Connection, user_id: int, ts: str):
    """Cập nhật last_daily"""
    con.execute("UPDATE users SET last_daily=? WHERE id=?", (ts, user_id))

@with_db
def leaderboard(con: sqlite3.Connection, limit: int = 10):
    """Top users theo số dư"""
    return con.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)).fetchall()

# ================= SWITCHES =================
@with_db
def set_switch(con: sqlite3.Connection, key: str, value: bool):
    con.execute("INSERT INTO switches(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, 1 if value else 0))

@with_db
def get_switch(con: sqlite3.Connection, key: str) -> bool:
    row = con.execute("SELECT value FROM switches WHERE key=?", (key,)).fetchone()
    if not row:
        return DEFAULT_SWITCHES.get(key, True)
    return bool(row[0])

# ================= STREAKS =================
@with_db
def adjust_streaks(con: sqlite3.Connection, user_id: int, win: bool):
    if win:
        con.execute("UPDATE users SET win_streak=win_streak+1, loss_streak=0 WHERE id=?", (user_id,))
    else:
        con.execute("UPDATE users SET loss_streak=loss_streak+1, win_streak=0 WHERE id=?", (user_id,))

@with_db
def get_recent_losses(con: sqlite3.Connection, user_id: int, n: int = 3) -> int:
    rows = con.execute("SELECT payout FROM bets WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, n)).fetchall()
    return sum(1 for (p,) in rows if p < 0)

@with_db
def find_user_by_username_or_id(con: sqlite3.Connection, token: str):
    token = token.strip()
    if token.startswith("@"):
        row = con.execute("SELECT id, tg_id, username FROM users WHERE lower(username)=lower(?)", (token[1:],)).fetchone()
        return row
    try:
        tid = int(token)
    except ValueError:
        return None
    return con.execute("SELECT id, tg_id, username FROM users WHERE tg_id=?", (tid,)).fetchone()

# ================= HELPERS =================
def parse_bet(args: List[str]) -> Tuple[Optional[int], Optional[str]]:
    """Phân tích cú pháp cược text"""
    if len(args) < 2:
        return None, None
    try:
        amt = int(args[0])
    except ValueError:
        return None, None
    return amt, args[1].lower()

def clamp_bet(amount: int) -> Optional[str]:
    """Kiểm tra giới hạn cược"""
    if amount < MIN_BET:
        return f"Mức cược tối thiểu là {MIN_BET}."
    if amount > MAX_BET:
        return f"Mức cược tối đa là {MAX_BET}."
    return None

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Tạo menu inline cơ bản"""
    rows = [
        [InlineKeyboardButton("💰 Balance", callback_data="m:bal"),
         InlineKeyboardButton("🎁 Daily", callback),
         #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_part2.py — Part 2/4
Game logic: Tài Xỉu, Dice, Roulette, Troll
"""
from bot_part1 import get_or_create_user, update_balance, record_bet, adjust_streaks, _rand

# ================= GAME HELPERS =================
def roll_dice(sides: int = 6) -> int:
    return _rand(sides) + 1

def play_taixiu(amount: int, choice: str) -> Tuple[int, str]:
    """Tài Xỉu 3 xúc xắc"""
    dice = [roll_dice() for _ in range(3)]
    total = sum(dice)
    result = "tài" if total >= 11 else "xỉu"
    payout = amount if result == choice else -amount
    return payout, f"🎲 Dice: {dice} → {total} → {result}"

def play_dice_game(amount: int, choice: str) -> Tuple[int, str]:
    d1, d2 = roll_dice(), roll_dice()
    total = d1 + d2
    result = "even" if total % 2 == 0 else "odd"
    payout = amount if result == choice else -amount
    return payout, f"🎲 Dice: {d1}+{d2}={total} → {result}"

def play_roulette(amount: int, choice: str) -> Tuple[int, str]:
    """Roulette kiểu đơn giản: số 0-36"""
    num = _rand(37)
    if choice.isdigit():
        win = int(choice) == num
        payout = amount * 35 if win else -amount
        return payout, f"🎰 Roulette: {num} → {'Win!' if win else 'Lose'}"
    elif choice.lower() in ["red","black"]:
        color = "red" if num % 2 == 0 else "black"
        win = choice.lower() == color
        payout = amount if win else -amount
        return payout, f"🎰 Roulette: {num} ({color}) → {'Win!' if win else 'Lose'}"
    else:
        return -amount, f"🎰 Invalid choice. Lose {amount}."

def play_troll(amount: int) -> Tuple[int, str]:
    """Game troll: 50/50 mất hết hoặc x2"""
    if _rand(2) == 0:
        return -amount, f"😈 Troll: You lost {amount}!"
    else:
        return amount, f"😇 Troll: You doubled {amount}!"

# ================= GAME WRAPPERS =================
def handle_game(user_id: int, amount: int, game: str, choice: str) -> str:
    """Chạy game và ghi vào DB"""
    if game == "taixiu":
        payout, msg = play_taixiu(amount, choice)
    elif game == "dice":
        payout, msg = play_dice_game(amount, choice)
    elif game == "roulette":
        payout, msg = play_roulette(amount, choice)
    elif game == "troll":
        payout, msg = play_troll(amount)
    else:
        return "❌ Game không tồn tại."
    # Cập nhật DB
    from bot_part1 import record_bet, update_balance, adjust_streaks
    user_row = get_or_create_user(user_id, None)
    uid, balance = user_row
    new_balance = balance + payout
    update_balance(uid, new_balance)
    adjust_streaks(uid, payout > 0)
    record_bet(uid, game, amount, choice, "win" if payout>0 else "lose", payout)
    return f"{msg}\n💰 Balance: {new_balance}"#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_part4.py — Part 4/4
Command handlers chi tiết và main loop hoàn chỉnh
"""
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from bot_part1 import init_db, get_or_create_user, leaderboard as lb_func
from bot_part2 import handle_game
from bot_part3 import list_shop, buy_item, show_inventory, claim_daily_quest, transfer_money

# ================= GAME COMMAND WRAPPER =================
async def handle_game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, game: str):
    tg_id = update.effective_user.id
    if len(context.args) < 1:
        await update.message.reply_text("❌ Cú pháp: /{game} <số tiền> [<lựa chọn>]")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return
    choice = context.args[1] if len(context.args) > 1 else ""
    result_msg = handle_game(tg_id, amount, game, choice)
    await update.message.reply_text(result_msg)

# ================= SHOP/INVENTORY COMMANDS =================
async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = list_shop()
    await update.message.reply_text("🏬 Shop:\n" + msg)

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if len(context.args) < 1:
        await update.message.reply_text("❌ Cú pháp: /buy <item_id>")
        return
    try:
        item_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Item ID không hợp lệ.")
        return
    msg = buy_item(tg_id, item_id)
    await update.message.reply_text(msg)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    msg = show_inventory(tg_id)
    await update.message.reply_text(msg)

# ================= QUEST =================
async def quest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    reward, msg = claim_daily_quest(tg_id)
    await update.message.reply_text(msg)

# ================= TRANSFER =================
async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("❌ Cú pháp: /transfer <@user hoặc id> <số tiền>")
        return
    target = context.args[0].replace("@","")
    try:
        to_user_id = int(target)
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ ID hoặc số tiền không hợp lệ.")
        return
    msg = transfer_money(tg_id, to_user_id, amount)
    await update.message.reply_text(msg)

# ================= LEADERBOARD =================
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb = lb_func()
    msg = "🏆 Leaderboard:\n" + "\n".join([f"{i+1}. {name} — {bal}" for i,(name,bal) in enumerate(lb)])
    await update.message.reply_text(msg)

# ================= BALANCE =================
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    uid, bal = get_or_create_user(tg_id, update.effective_user.username)
    await update.message.reply_text(f"💰 Balance: {bal}")

# ================= MAIN =================
def main():
    init_db()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    app = Application.builder().token(BOT_TOKEN).build()

    # COMMON COMMANDS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance))

    # GAME COMMANDS
    app.add_handler(CommandHandler("taixiu", lambda u,c: handle_game_cmd(u,c,"taixiu")))
    app.add_handler(CommandHandler("dice", lambda u,c: handle_game_cmd(u,c,"dice")))
    app.add_handler(CommandHandler("roulette", lambda u,c: handle_game_cmd(u,c,"roulette")))
    app.add_handler(CommandHandler("troll", lambda u,c: handle_game_cmd(u,c,"troll")))

    # SHOP/INVENTORY
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))

    # QUEST
    app.add_handler(CommandHandler("quest", quest_cmd))

    # TRANSFER
    app.add_handler(CommandHandler("transfer", transfer_cmd))

    # LEADERBOARD
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))

    # RUN BOT
    print("Bot is running...")
    app.run_polling()

# START/HELP
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    username = update.effective_user.username
    uid, bal = get_or_create_user(tg_id, username)
    await update.message.reply_text(f"👋 Chào {username}, Balance: {bal}\nDùng /help để xem lệnh.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
🎮 Các lệnh:
/start - Bắt đầu
/balance - Xem số dư
/taixiu <số> <tài/xỉu> - Chơi Tài Xỉu
/dice <số> <even/odd> - Chơi Dice
/roulette <số> <số/red/black> - Roulette
/troll <số> - Game troll
/shop - Xem shop
/buy <id> - Mua item
/inventory - Xem item
/quest - Nhận quest hằng ngày
/transfer <@user hoặc id> <số> - Chuyển tiền
/leaderboard - Top user
"""
    await update.message.reply_text(msg)

if __name__ == "__main__":
    main()


