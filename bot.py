#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot.py — FULL (4 parts)
Part 1/4 — core, db, helpers, core commands
Paste Part 2, Part 3, Part 4 immediately after this.
"""
from __future__ import annotations
import os
import re
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
)

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")  # must set in env
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "casino_full.db")

DEFAULT_SWITCHES = {
    "taixiu": True,
    "dice": True,
    "roulette": True,
    "troll": True,
    "shop": True,
    "quest": True,
}

INITIAL_BALANCE = 1_000
DAILY_REWARD = 300
DAILY_COOLDOWN_HOURS = 24
MAX_BET = 100_000
MIN_BET = 10
QUEST_MIN = 100
QUEST_MAX = 500

# ========== RNG ==========
try:
    from secrets import randbelow
    _rand = randbelow
except Exception:
    import random
    _sysrand = random.SystemRandom()
    _rand = lambda n: _sysrand.randrange(n)

def now_iso() -> str:
    return datetime.utcnow().isoformat()

# ========== DB UTIL ==========
def with_db(func):
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
    # seed switches
    for k, v in DEFAULT_SWITCHES.items():
        con.execute("INSERT OR IGNORE INTO switches(key, value) VALUES (?, ?)", (k, 1 if v else 0))
    # seed shop
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

@with_db
def get_or_create_user(con: sqlite3.Connection, tg_id: int, username: Optional[str]) -> Tuple[int, int]:
    row = con.execute("SELECT id, balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if row:
        return row[0], row[1]
    con.execute("INSERT INTO users(tg_id, username, balance) VALUES (?,?,?)", (tg_id, username, INITIAL_BALANCE))
    uid = con.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()[0]
    return uid, INITIAL_BALANCE

@with_db
def get_user(con: sqlite3.Connection, tg_id: int):
    return con.execute("SELECT id, username, balance, last_daily, loss_streak, win_streak FROM users WHERE tg_id=?", (tg_id,)).fetchone()

@with_db
def update_balance(con: sqlite3.Connection, user_id: int, new_balance: int):
    con.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))

@with_db
def record_bet(con: sqlite3.Connection, user_id: int, game: str, amount: int, choice: str, result: str, payout: int):
    con.execute("INSERT INTO bets(user_id, game, amount, choice, result, payout, created_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, game, amount, choice, result, payout, now_iso()))

@with_db
def set_last_daily(con: sqlite3.Connection, user_id: int, ts: str):
    con.execute("UPDATE users SET last_daily=? WHERE id=?", (ts, user_id))

@with_db
def leaderboard(con: sqlite3.Connection, limit: int = 10):
    return con.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)).fetchall()

@with_db
def set_switch(con: sqlite3.Connection, key: str, value: bool):
    con.execute("INSERT INTO switches(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, 1 if value else 0))

@with_db
def get_switch(con: sqlite3.Connection, key: str) -> bool:
    row = con.execute("SELECT value FROM switches WHERE key=?", (key,)).fetchone()
    if not row:
        return DEFAULT_SWITCHES.get(key, True)
    return bool(row[0])

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

# ========== HELPERS ==========
def parse_bet(args: List[str]) -> Tuple[Optional[int], Optional[str]]:
    if len(args) < 2:
        return None, None
    try:
        amt = int(args[0])
    except ValueError:
        return None, None
    return amt, args[1].lower()

def clamp_bet(amount: int) -> Optional[str]:
    if amount < MIN_BET:
        return f"Mức cược tối thiểu là {MIN_BET}."
    if amount > MAX_BET:
        return f"Mức cược tối đa là {MAX_BET}."
    return None

def main_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💰 Balance", callback_data="m:bal"), InlineKeyboardButton("🎁 Daily", callback_data="m:daily")],
        [InlineKeyboardButton("🎲 Tài/Xỉu", callback_data="m:tx"), InlineKeyboardButton("🎯 Dice", callback_data="m:dice"), InlineKeyboardButton("🎡 Roulette", callback_data="m:roul")],
        [InlineKeyboardButton("🛒 Shop", callback_data="m:shop"), InlineKeyboardButton("📦 Túi đồ", callback_data="m:inv")],
        [InlineKeyboardButton("🏆 Top", callback_data="m:top"), InlineKeyboardButton("🧭 Quest", callback_data="m:quest")],
    ]
    return InlineKeyboardMarkup(rows)

# ========== CORE COMMANDS ==========
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    uid, bal = get_or_create_user(user.id, user.username or (user.full_name or "user"))
    await update.message.reply_text(
        f"Chào {user.first_name}! Ví coin ảo của bạn: {bal}💰\nGõ /help để xem lệnh. Chơi vui, KHÔNG tiền thật.",
        reply_markup=main_menu_keyboard()
    )

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu nhanh:", reply_markup=main_menu_keyboard())

async def on_menu_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()
    data = q.data
    if data == "m:bal":
        return await cmd_balance(update, context)
    if data == "m:daily":
        return await cmd_daily(update, context)
    if data == "m:tx":
        # start taixiu via callback flow
        return await start_taixiu_inline(q, context)
    if data == "m:dice":
        await q.message.reply_text("Cú pháp: /bet_dice <tiền> <1-6>")
        return
    if data == "m:roul":
        await q.message.reply_text("Cú pháp: /bet_roulette <tiền> <red|black|even|odd|0-36>")
        return
    if data == "m:shop":
        # show shop inline
        return await shop_show_inline(q, context)
    if data == "m:inv":
        return await cmd_inventory(update, context)
    if data == "m:top":
        return await cmd_leaderboard(update, context)
    if data == "m:quest":
        return await cmd_quest(update, context)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📜 Lệnh cơ bản:\n"
        "/start – khởi tạo ví\n"
        "/menu – menu nút\n"
        "/whoami – xem user_id\n"
        "/balance (/bal) – xem số dư\n"
        f"/daily – nhận {DAILY_REWARD} coin mỗi {DAILY_COOLDOWN_HOURS}h\n"
        "/leaderboard – top coin\n"
        "/weekly – top tuần (tham khảo)\n\n"
        "🎲 Cược game:\n"
        "/bet_taixiu <tiền> <tai|xiu> (text)\n"
        "/taixiu - nút chọn cửa + tiền (inline)\n"
        "/bet_dice <tiền> <1-6>\n"
        "/bet_roulette <tiền> <red|black|even|odd|0-36>\n\n"
        "🛒 Shop:\n"
        "/shop – xem hàng\n"
        "/buy <id> – mua\n"
        "/inventory – túi đồ\n\n"
        "🎁 Xã hội:\n"
        "/gift @user <tiền>\n"
        "/transfer @user <tiền>\n\n"
        "🧭 Quest:\n"
        "/quest – mô tả nhiệm vụ ngày\n"
        "/quest_claim – nhận thưởng ngày ngẫu nhiên\n\n"
        "⚙️ Admin: /give @user <tiền>, /setbal @user <tiền>, /toggle <game> on|off\n"
        "🔒 Coin ảo – không đổi ra tiền thật."
    )
    await update.message.reply_text(msg)

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Random minh bạch.\n❌ Không dùng tiền thật.\n🧠 Vui là chính — chơi có kiểm soát.")

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(f"user_id của bạn: {u.id}")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    _, username, balance, *_ = u
    await update.message.reply_text(f"{username or 'Bạn'}: {balance} coin 💰")

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, last_daily, *_ = u
    now = datetime.utcnow()
    if last_daily:
        last = datetime.fromisoformat(last_daily)
        if now - last < timedelta(hours=DAILY_COOLDOWN_HOURS):
            remain = timedelta(hours=DAILY_COOLDOWN_HOURS) - (now - last)
            hrs = int(remain.total_seconds() // 3600)
            mins = int((remain.total_seconds() % 3600) // 60)
            await update.message.reply_text(f"Chưa đủ cooldown. Thử lại sau {hrs}h{mins:02d}.")
            return
    new_bal = balance + DAILY_REWARD
    update_balance(uid, new_bal)
    set_last_daily(uid, now.isoformat())
    await update.message.reply_text(f"Nhận +{DAILY_REWARD} coin! Số dư: {new_bal} 💰")

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = leaderboard(10)
    if not top:
        await update.message.reply_text("Chưa có ai trong bảng xếp hạng.")
        return
    text = ["🏆 TOP 10 GIÀU NHẤT:"]
    for i, (username, bal) in enumerate(top, start=1):
        text.append(f"{i}. {username or 'Người chơi'} – {bal}💰")
    await update.message.reply_text("\n".join(text))
# ========== Part 2/4 (paste after Part 1) ==========
# ---------- continuing game functions ----------
def roll_3dice() -> tuple[int, tuple[int, int, int]]:
    d1 = _rand(6) + 1
    d2 = _rand(6) + 1
    d3 = _rand(6) + 1
    s = d1 + d2 + d3
    return s, (d1, d2, d3)

def spin_roulette() -> int:
    return _rand(37)  # 0..36

_ROULETTE_REDS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
_ROULETTE_BLACKS = set(range(1,37)) - _ROULETTE_REDS

async def _troll_feedback(update: Update, uid: int, win: bool, bet_amt: int = 0, payout: int = 0):
    if not get_switch("troll"):
        return
    losses = get_recent_losses(uid, 3)
    if losses >= 3:
        await update.message.reply_text("🤡 Thua 3 kèo rồi đó nha… đổi gió coi!")
    if win and payout >= bet_amt * 2 and bet_amt > 0:
        await update.message.reply_text("🤑 Ăn đậm luôn! Cho xin bí kíp?")

async def _apply_bet(update: Update, game: str, amt: int, choice: str, win: bool, result_str: str, uid: int, cur_balance: int):
    payout = amt if win else -amt
    new_bal = cur_balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, game, amt, choice, result_str, payout)
    adjust_streaks(uid, win)
    await _troll_feedback(update, uid, win, amt, payout)
    return payout, new_bal

# ---- Text commands for bets (legacy)
async def cmd_bet_taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # text-mode: /bet_taixiu <amt> <tai|xiu>
    if not get_switch("taixiu"):
        await update.message.reply_text("Game Tài Xỉu đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, *_ = u
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /bet_taixiu <tiền> <tai|xiu>")
        return
    try:
        amt = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Tiền cược phải là số.")
        return
    choice = context.args[1].lower()
    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return
    if choice not in {"tai", "xiu"}:
        await update.message.reply_text("Chọn 'tai' hoặc 'xiu'.")
        return
    total, dice = roll_3dice()
    outcome = "tai" if total >= 11 else "xiu"
    win = (choice == outcome)
    payout, new_bal = await _apply_bet(update, "taixiu", amt, choice, win, f"{dice}={total}", uid, balance)
    await update.message.reply_text(f"🎲 {dice} = {total} → {outcome.upper()}\nBạn {'THẮNG' if win else 'THUA'} {payout if win else -amt} coin.\nSố dư: {new_bal}💰")

# ---- Dice & Roulette (text) ----
async def cmd_bet_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("dice"):
        await update.message.reply_text("Game Dice đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, *_ = u
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /bet_dice <tiền> <1-6>")
        return
    try:
        amt = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Tiền cược phải là số.")
        return
    face = context.args[1]
    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return
    if face not in {"1","2","3","4","5","6"}:
        await update.message.reply_text("Bạn phải chọn số từ 1 đến 6.")
        return
    roll = _rand(6) + 1
    win = (int(face) == roll)
    payout = (amt * 5) if win else -amt
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "dice", amt, face, str(roll), payout)
    adjust_streaks(uid, win)
    await _troll_feedback(update, uid, win, amt, payout)
    await update.message.reply_text(f"🎯 Xúc xắc ra: {roll}\nBạn {'THẮNG' if win else 'THUA'} {payout if win else -amt} coin.\nSố dư: {new_bal}💰")

async def cmd_bet_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("roulette"):
        await update.message.reply_text("Roulette đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. Gõ /start để tạo.")
        return
    uid, _, balance, *_ = u
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /bet_roulette <tiền> <red|black|even|odd|0-36>")
        return
    try:
        amt = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Tiền cược phải là số nguyên.")
        return
    choice = context.args[1].lower()
    msg = clamp_bet(amt)
    if msg:
        await update.message.reply_text(msg)
        return
    if amt > balance:
        await update.message.reply_text("Không đủ coin.")
        return
    result = spin_roulette()
    win = False
    multiplier = 0
    if choice in {"red", "đen", "black"}:
        is_red = result in _ROULETTE_REDS
        is_black = result in _ROULETTE_BLACKS
        if choice == "red":
            win = is_red; multiplier = 1
        elif choice in {"black","đen"}:
            win = is_black; multiplier = 1
    elif choice in {"even","odd"}:
        if result != 0:
            if choice == "even" and result % 2 == 0:
                win, multiplier = True, 1
            if choice == "odd" and result % 2 == 1:
                win, multiplier = True, 1
    else:
        try:
            pick = int(choice)
            if 0 <= pick <= 36 and pick == result:
                win, multiplier = True, 35
        except ValueError:
            pass
    if multiplier == 0:
        multiplier = 1
    payout = amt * multiplier if win else -amt
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "roulette", amt, choice, str(result), payout)
    adjust_streaks(uid, win)
    await _troll_feedback(update, uid, win, amt, payout)
    color = "🔴" if result in _ROULETTE_REDS else ("⚫" if result in _ROULETTE_BLACKS else "🟢")
    await update.message.reply_text(f"🎡 Roulette: {color} {result}\nBạn {'THẮNG' if win else 'THUA'} {payout if win else -amt} coin.\nSố dư: {new_bal}💰")
# ========== Part 3/4 (paste after Part 2) ==========
# ========== SHOP & SOCIAL ==========
@with_db
def shop_list(con: sqlite3.Connection):
    return con.execute("SELECT item_id, name, price FROM shop ORDER BY item_id").fetchall()

async def shop_show_inline(query_obj, context: ContextTypes.DEFAULT_TYPE):
    # query_obj may be CallbackQuery or Update.message
    # We accept either; if CallbackQuery passed, send/edit; if message, send new
    is_callback = hasattr(query_obj, "answer")
    if is_callback:
        q = query_obj
        await q.answer()
        chat_id = q.message.chat_id
    else:
        # update.message
        chat_id = query_obj.effective_chat.id
        q = None

    items = shop_list()
    if not items:
        if q:
            await q.message.reply_text("🛒 Shop trống.")
        else:
            await context.bot.send_message(chat_id, "🛒 Shop trống.")
        return

    # build inline keyboard: one button per item (buy_item_<id>)
    kb = []
    for iid, name, price in items:
        kb.append([InlineKeyboardButton(f"{name} — {price}💰", callback_data=f"shop_buy_{iid}")])
    kb.append([InlineKeyboardButton("Đóng", callback_data="shop_close")])

    if q:
        await q.message.edit_text("🛒 Shop (chọn để mua):", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_message(chat_id, "🛒 Shop (chọn để mua):", reply_markup=InlineKeyboardMarkup(kb))

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user
    if data == "shop_close":
        await q.message.edit_text("Đã đóng shop.")
        return
    if data.startswith("shop_buy_"):
        try:
            item_id = int(data.split("_")[-1])
        except Exception:
            await q.message.reply_text("ID item không hợp lệ.")
            return
        u = get_user(user.id)
        if not u:
            await q.message.reply_text("Bạn chưa có ví. /start để tạo.")
            return
        uid, _, balance, *_ = u
        @with_db
        def _get(con, iid):
            return con.execute("SELECT name, price FROM shop WHERE item_id=?", (iid,)).fetchone()
        row = _get(item_id)
        if not row:
            await q.message.reply_text("Item không tồn tại.")
            return
        name, price = row
        if balance < price:
            await q.message.reply_text("Không đủ coin.")
            return
        new_bal = balance - price
        update_balance(uid, new_bal)
        @with_db
        def _save(con):
            con.execute("INSERT INTO inventory(user_id, item_id, acquired_at) VALUES (?,?,?)", (uid, item_id, now_iso()))
        _save()
        await q.message.edit_text(f"✅ Mua {name} thành công! Số dư còn: {new_bal}💰")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # show shop as a normal message (non-editable)
    items = shop_list()
    if not items:
        await update.message.reply_text("🛒 Shop trống.")
        return
    lines = []
    for iid, name, price in items:
        lines.append(f"{iid}. {name} — {price}💰")
    lines.append("\nDùng /buy <id> hoặc bấm vào nút Shop (menu).")
    await update.message.reply_text("\n".join(lines))

async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Dùng: /buy <item_id>")
        return
    try:
        item_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("item_id phải là số.")
        return
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. /start để tạo.")
        return
    uid, _, balance, *_ = u
    @with_db
    def _info(con, iid):
        return con.execute("SELECT name, price FROM shop WHERE item_id=?", (iid,)).fetchone()
    item = _info(item_id)
    if not item:
        await update.message.reply_text("Item không tồn tại.")
        return
    name, price = item
    if balance < price:
        await update.message.reply_text("Không đủ coin.")
        return
    new_bal = balance - price
    update_balance(uid, new_bal)
    @with_db
    def _save(con):
        con.execute("INSERT INTO inventory(user_id, item_id, acquired_at) VALUES (?,?,?)", (uid, item_id, now_iso()))
    _save()
    await update.message.reply_text(f"✅ Mua {name} thành công! Số dư còn: {new_bal}💰")

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. /start để tạo.")
        return
    uid = u[0]
    @with_db
    def _inv(con, _uid):
        return con.execute("""SELECT s.name, s.price, i.acquired_at FROM inventory i JOIN shop s ON i.item_id = s.item_id WHERE i.user_id=? ORDER BY i.id DESC""", (_uid,)).fetchall()
    items = _inv(uid)
    if not items:
        await update.message.reply_text("📦 Túi đồ trống.")
        return
    text = ["📦 Túi đồ của bạn:"]
    for name, price, when in items:
        text.append(f"- {name} (giá {price}) – {when}")
    await update.message.reply_text("\n".join(text))

# ========== SOCIAL ==========
async def _transfer_generic(update: Update, context: ContextTypes.DEFAULT_TYPE, verb: str):
    if len(context.args) < 2:
        await update.message.reply_text(f"Dùng: /{verb} @user <tiền>")
        return
    target = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Tiền phải là số.")
        return
    if amount <= 0:
        await update.message.reply_text("Tiền phải > 0.")
        return
    src_u = get_user(update.effective_user.id)
    if not src_u:
        await update.message.reply_text("Bạn chưa có ví. /start để tạo.")
        return
    src_id, _, src_bal, *_ = src_u
    tgt = find_user_by_username_or_id(target)
    if not tgt:
        await update.message.reply_text("Không tìm thấy người nhận. Họ phải /start trước.")
        return
    tgt_id, tgt_tid, tgt_name = tgt
    if tgt_tid == update.effective_user.id:
        await update.message.reply_text("Không thể chuyển cho chính mình.")
        return
    if src_bal < amount:
        await update.message.reply_text("Bạn không đủ coin.")
        return
    new_src = src_bal - amount
    update_balance(src_id, new_src)
    @with_db
    def _credit(con):
        cur = con.execute("SELECT balance FROM users WHERE id=?", (tgt_id,)).fetchone()
        cur_bal = cur[0] if cur else 0
        con.execute("UPDATE users SET balance=? WHERE id=?", (cur_bal + amount, tgt_id))
        con.execute("INSERT INTO transfers(from_user, to_user, amount, created_at) VALUES (?,?,?,?)", (src_id, tgt_id, amount, now_iso()))
    _credit()
    await update.message.reply_text(f"✅ Đã chuyển {amount} coin cho {tgt_name or tgt_tid}. Số dư còn: {new_src}💰")
# ========== Part 4/4 (paste after Part 3) ==========
# ========== QUEST, WEEKLY, ADMIN, TAIXIU INLINE handlers & main ==========
@with_db
def _quest_get(con: sqlite3.Connection, uid: int):
    return con.execute("SELECT last_claim_date FROM quests WHERE user_id=?", (uid,)).fetchone()

@with_db
def _quest_set_today(con: sqlite3.Connection, uid: int):
    today = date.today().isoformat()
    if con.execute("SELECT user_id FROM quests WHERE user_id=?", (uid,)).fetchone():
        con.execute("UPDATE quests SET last_claim_date=? WHERE user_id=?", (today, uid))
    else:
        con.execute("INSERT INTO quests(user_id, last_claim_date) VALUES (?,?)", (uid, today))

async def cmd_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("quest"):
        await update.message.reply_text("Quest đang tắt.")
        return
    await update.message.reply_text(f"🧭 Quest ngày: gõ /quest_claim để nhận thưởng (khoảng {QUEST_MIN}-{QUEST_MAX} coin).")

async def cmd_quest_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_switch("quest"):
        await update.message.reply_text("Quest đang tắt.")
        return
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Bạn chưa có ví. /start để tạo.")
        return
    uid, _, balance, *_ = u
    q = _quest_get(uid)
    today = date.today().isoformat()
    if q and q[0] == today:
        await update.message.reply_text("Hôm nay bạn đã nhận quest rồi. Quay lại ngày mai!")
        return
    rng = _rand(QUEST_MAX - QUEST_MIN + 1) + QUEST_MIN
    new_bal = balance + rng
    update_balance(uid, new_bal)
    _quest_set_today(uid)
    await update.message.reply_text(f"🎁 Nhận thưởng quest: +{rng} coin! Số dư: {new_bal}💰")

# Weekly leaderboard
async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = leaderboard(10)
    if not top:
        await update.message.reply_text("Chưa có dữ liệu cho bảng tuần.")
        return
    text = ["📅 BẢNG TUẦN (Top hiện tại):"]
    for i, (username, bal) in enumerate(top, start=1):
        text.append(f"{i}. {username or 'Người chơi'} — {bal}💰")
    await update.message.reply_text("\n".join(text))

# ADMIN
def _is_owner(user_id: int) -> bool:
    return OWNER_ID and user_id == OWNER_ID

def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if OWNER_ID and user.id != OWNER_ID:
            await update.message.reply_text("Chỉ OWNER mới dùng lệnh này.")
            return
        return await func(update, context)
    return wrapper

@owner_only
async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Dùng: /give @user <tiền>")
        return
    target = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Tiền phải là số.")
        return
    if amount <= 0:
        await update.message.reply_text("Tiền phải > 0.")
        return
    tgt = find_user_by_username_or_id(target)
    if not tgt:
        await update.message.reply_text("Không tìm thấy user (họ phải /start trước)")
        return
    tgt_id, tgt_tid, tgt_name = tgt
    @with_db
    def _add(con):
        cur_bal = con.execute("SELECT balance FROM users WHERE id=?", (tgt_id,)).fetchone()[0]
        con.execute("UPDATE users SET balance=? WHERE id=?", (cur_bal + amount, tgt_id))
    _add()
    await update.message.reply_text(f"✅ Đã cộng {amount} coin cho {tgt_name or tgt_tid}.")

@owner_only
async def cmd_setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Dùng: /setbal @user <tiền>")
        return
    target = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Tiền phải là số.")
        return
    tgt = find_user_by_username_or_id(target)
    if not tgt:
        await update.message.reply_text("Không tìm thấy user.")
        return
    tgt_id, tgt_tid, tgt_name = tgt
    update_balance(tgt_id, amount)
    await update.message.reply_text(f"✅ Set số dư của {tgt_name or tgt_tid} = {amount} coin.")

@owner_only
async def cmd_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Dùng: /toggle <taixiu|dice|roulette|troll|shop|quest> <on|off>")
        return
    key = context.args[0].lower()
    val = context.args[1].lower()
    if key not in DEFAULT_SWITCHES:
        await update.message.reply_text("Key không hợp lệ.")
        return
    if val not in {"on","off"}:
        await update.message.reply_text("Giá trị phải là on/off.")
        return
    set_switch(key, val == "on")
    await update.message.reply_text(f"🔁 {key} → {'BẬT' if val=='on' else 'TẮT'}")

# ========== TÀI XỈU INLINE FLOW ==========
# - start_taixiu_inline: send buttons to pick Tai/Xiu
# - taixiu_callback: after pick, show amount buttons
# - taixiu_amount_callback: resolve bet, update DB, send result

async def start_taixiu_inline(trigger_obj, context: ContextTypes.DEFAULT_TYPE):
    # trigger_obj might be CallbackQuery or Update
    if hasattr(trigger_obj, "answer"):
        q = trigger_obj
        await q.answer()
        chat_id = q.message.chat_id
        send_method = q.message.reply_text
    else:
        # Update from message
        upd = trigger_obj
        chat_id = upd.effective_chat.id
        send_method = upd.message.reply_text

    kb = [
        [InlineKeyboardButton("🎲 Tài", callback_data="tx_choice_tai"), InlineKeyboardButton("🎲 Xỉu", callback_data="tx_choice_xiu")],
        [InlineKeyboardButton("Huỷ", callback_data="tx_cancel")]
    ]
    await send_method("Chọn cửa cược:", reply_markup=InlineKeyboardMarkup(kb))

async def taixiu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user
    if data == "tx_cancel":
        await q.message.edit_text("Đã huỷ Tài/Xỉu.")
        return
    if data.startswith("tx_choice_"):
        choice = data.split("_")[-1]  # 'tai' or 'xiu'
        # show amount buttons
        amounts = [50, 100, 200, 500, 1000]
        kb = []
        for a in amounts:
            kb.append([InlineKeyboardButton(f"{a}💰", callback_data=f"tx_amt_{choice}_{a}")])
        kb.append([InlineKeyboardButton("Huỷ", callback_data="tx_cancel")])
        await q.message.edit_text(f"Bạn chọn {choice.upper()}. Chọn số tiền cược:", reply_markup=InlineKeyboardMarkup(kb))
        return
    # if user pressed amount directly handled in next handler

async def taixiu_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # format: tx_amt_<choice>_<amount>
    user = update.effective_user
    if not data.startswith("tx_amt_"):
        await q.message.reply_text("Dữ liệu không hợp lệ.")
        return
    try:
        _, _, choice, amount_s = data.split("_", 3)
        amount = int(amount_s)
    except Exception:
        await q.message.reply_text("Dữ liệu amount không hợp lệ.")
        return
    # validate user & balance
    u = get_user(user.id)
    if not u:
        await q.message.reply_text("Bạn chưa có ví. /start để tạo.")
        return
    uid, _, balance, *_ = u
    if amount < MIN_BET:
        await q.message.reply_text(f"Mức cược tối thiểu là {MIN_BET}.")
        return
    if amount > MAX_BET:
        await q.message.reply_text(f"Mức cược tối đa là {MAX_BET}.")
        return
    if amount > balance:
        await q.message.reply_text("Không đủ coin.")
        return
    # roll
    total, dice = roll_3dice()
    outcome = "tai" if total >= 11 else "xiu"
    win = (choice == outcome)
    payout = amount if win else -amount
    # apply
    new_bal = balance + payout
    update_balance(uid, new_bal)
    record_bet(uid, "taixiu_inline", amount, choice, f"{dice}={total}", payout)
    adjust_streaks(uid, win)
    # respond
    res_text = f"🎲 Kết quả: {dice} = {total} → {outcome.upper()}\n"
    if win:
        res_text += f"Bạn THẮNG +{amount}💰!\n"
    else:
        res_text += f"Bạn THUA -{amount}💰\n"
    res_text += f"Số dư hiện tại: {new_bal}💰"
    await q.message.edit_text(res_text)

# ========== FALLBACK & MAIN ==========
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Không hiểu lệnh. Gõ /help.")

def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN chưa được đặt trong biến môi trường.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(on_menu_press, pattern="^m:"))

    # help/rules
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler(["whoami","id"], cmd_whoami))
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()

