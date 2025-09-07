import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# 🔑 Token va Admin ID
TOKEN = "8277214670:AAE14PAs7pBPbCC7U4P0PF0Ypbfj86OUtfQ"   
ADMIN_ID = 6238334772                                      # Admin Telegram ID yoz
BOT_USERNAME = "instafilms_bot"      # Masalan: kinobotuz

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- FSM ---
class AddMovie(StatesGroup):
    waiting_for_code = State()

class DeleteMovie(StatesGroup):
    waiting_for_code = State()

# --- DB funksiyalar ---
def init_db():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, invited_by INTEGER)")
    conn.commit()
    conn.close()

def add_movie_to_db(code, file_id):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO movies VALUES (?,?)", (code, file_id))
    conn.commit()
    conn.close()

def get_movie_by_code(code):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM movies WHERE code=?", (code,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_movie_from_db(code):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE code=?", (code,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def list_movies():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM movies ORDER BY code")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def add_user(user_id, invited_by=None):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, invited_by) VALUES (?,?)", (user_id, invited_by))
    conn.commit()
    conn.close()

def get_refs(user_id):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE invited_by=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# --- Start ---
@dp.message(F.text.startswith("/start"))
async def start(message: Message):
    args = message.text.split()
    invited_by = None

    if len(args) > 1:  # referral link orqali kirgan bo‘lsa
        try:
            invited_by = int(args[1])
        except ValueError:
            invited_by = None

    add_user(message.from_user.id, invited_by)

    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Salom, Admin! 👑\n\n"
            "Siz uchun komandalar:\n"
            "▫️ Video yuborib kod bilan qo‘shish\n"
            "▫️ /delete — kod bo‘yicha o‘chirish\n"
            "▫️ /list — barcha kinolar ro‘yxati\n"
            "▫️ /refs — referallarni ko‘rish"
        )
    else:
        link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
        await message.answer(
            "Salom! 🎬\n"
            "Kino ko‘rish uchun shunchaki kodni yuboring.\n\n"
            f"👉 Do‘stlaringizni taklif qiling va ular siz orqali kirsa sizga yoziladi.\n"
            f"🔗 Sizning taklif linkingiz: {link}"
        )

# --- Admin referallarni ko‘rishi ---
@dp.message(F.text == "/refs", F.from_user.id == ADMIN_ID)
async def refs(message: Message):
    all_refs = get_refs(ADMIN_ID)
    if all_refs:
        text = "👥 Sizning referallaringiz:\n" + "\n".join([f"▫️ {uid}" for uid in all_refs])
    else:
        text = "📭 Sizda hali referal yo‘q."
    await message.answer(text)

# --- Admin video qo‘shish ---
@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def admin_add_movie(message: Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await message.answer("✅ Kino fayli olindi.\nEndi unga kod yozing (masalan: 1001).")
    await state.set_state(AddMovie.waiting_for_code)

@dp.message(AddMovie.waiting_for_code, F.from_user.id == ADMIN_ID)
async def add_code(message: Message, state: FSMContext):
    data = await state.get_data()
    add_movie_to_db(code=message.text.strip(), file_id=data["file_id"])
    await message.answer(f"✅ Kino qo‘shildi! Kod: {message.text.strip()}")
    await state.clear()

# --- Admin kino o‘chirish ---
@dp.message(F.text == "/delete", F.from_user.id == ADMIN_ID)
async def delete_start(message: Message, state: FSMContext):
    await message.answer("🗑 O‘chirish uchun kino kodini yuboring:")
    await state.set_state(DeleteMovie.waiting_for_code)

@dp.message(DeleteMovie.waiting_for_code, F.from_user.id == ADMIN_ID)
async def delete_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if delete_movie_from_db(code):
        await message.answer(f"✅ Kino o‘chirildi. Kod: {code}")
    else:
        await message.answer("❌ Bunday kod topilmadi.")
    await state.clear()

# --- Admin barcha kinolar ro‘yxati ---
@dp.message(F.text == "/list", F.from_user.id == ADMIN_ID)
async def list_all_movies(message: Message):
    movies = list_movies()
    if movies:
        text = "🎬 Barcha kinolar ro‘yxati:\n\n" + "\n".join([f"▫️ {code}" for code in movies])
    else:
        text = "📭 Bazada kino yo‘q."
    await message.answer(text)

# --- Oddiy foydalanuvchi kod yuborsa ---
@dp.message()
async def movie_by_code(message: Message):
    code = message.text.strip()
    file_id = get_movie_by_code(code)
    if file_id:
        await bot.send_video(message.chat.id, file_id)
    else:
        await message.answer("❌ Bunday kod bo‘yicha kino topilmadi.")

@dp.message(F.text == "👥 Referal")
async def referral_btn(message: Message):
    link = f"https://t.me/{instafilms_bot}?start={message.from_user.id}"
    await message.answer(
        "👥 Do‘stlaringizni taklif qiling!\n\n"
        f"🔗 Sizning taklif linkingiz:\n{link}"
    )

# --- Run bot ---
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
