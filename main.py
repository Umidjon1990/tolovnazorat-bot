import os
import io
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.filters import Command
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not found. Please set it in .env file")

ADMIN_IDS: list[int] = []
_raw_admins = os.getenv("ADMIN_IDS", "")
if _raw_admins.strip():
    for x in _raw_admins.split(","):
        x = x.strip()
        if x.lstrip("-").isdigit():
            ADMIN_IDS.append(int(x))
if not ADMIN_IDS:
    logger.warning("ADMIN_IDS is empty. No admin functionality will be available.")

GROUP_IDS: list[int] = []
_raw_groups = os.getenv("PRIVATE_GROUP_ID", "")
if _raw_groups.strip():
    for x in _raw_groups.split(","):
        x = x.strip()
        if x.lstrip("-").isdigit():
            GROUP_IDS.append(int(x))
if not GROUP_IDS:
    logger.warning("PRIVATE_GROUP_ID is empty. Invite links cannot be created.")

SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
INVITE_LINK_EXPIRE_HOURS = int(os.getenv("INVITE_LINK_EXPIRE_HOURS", "1"))
REMIND_DAYS = int(os.getenv("REMIND_DAYS", "3"))

DB_PATH = os.getenv("DB_PATH", "./subs.db")
TZ_OFFSET = timedelta(hours=5)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

WAIT_DATE_FOR: dict[int, int] = {}
MULTI_PICK: dict[int, dict] = {}
WAIT_CONTACT_FOR: set[int] = set()
WAIT_FULLNAME_FOR: set[int] = set()

CONTRACT_TEXT = """ONLAYN O'QUV SHARTNOMA

O'rtasida:
"Zamonaviy Ta'lim" MCHJ (bundan keyin "Markaz" deb yuritiladi)
va
O'quvchi (bundan keyin "O'quvchi" deb yuritiladi)

1. SHARTNOMA MAQSADI
Ushbu shartnoma Markaz tomonidan tashkil etilgan "CEFR Imtihoniga Bosqichma-bosqich Tayyorlovchi Video Kurs" dasturi doirasida o'quvchining mas'uliyatini, to'lov tartibini va Markaz kafolatlarini belgilashga qaratilgan.

2. KURS TASHKILOTI
Darslar yopiq Telegram guruhlari orqali olib boriladi.
Har bosqich uchun alohida A1, A2, B1, B2 manbalar guruhi va vazifa guruhi mavjud.
Darslar kun ora video shaklida joylanadi, va har hafta jonli onlayn dars o'tkaziladi.
Har bir bosqich o'rtacha 2 oy davom etadi.
Darslar Bosqichli Arab Tili, Miftah, va CEFR standartlariga asoslangan materiallar asosida tashkil qilinadi.

3. O'QUVCHINING MAJBURIYATLARI
O'quvchi darslarni muntazam kuzatib borishi va faol ishtirok etishi shart.
O'quvchi 1 hafta davomida hech qanday vazifa yubormasa, sababsiz holda guruhdan chetlatiladi.
O'quvchi bosqichni muvaffaqiyatli yakunlamasa, keyingi bosqichga imtihon asosida o'ta oladi yoki shu bosqichni qayta o'qiydi.
O'quvchi kurs davomida barcha ichki tartib-qoidalarga rioya qilishi shart.
O'quvchi to'lovni belgilangan muddatda amalga oshirishi kerak.

4. MARKAZNING MAJBURIYATLARI
Markaz har bir bosqich uchun sifatli video darslar va materiallar bilan ta'minlaydi.
Markaz o'quvchining natijasi uchun kafolat beradi, agar o'quvchi topshiriqlarni to'liq bajargan bo'lsa.
Markaz haftasiga kamida bitta jonli sessiya o'tkazadi.
Markaz o'quvchi murojaatlariga o'z vaqtida javob beradi.

5. TO'LOV TARTIBI VA QAYTARISH SHARTLARI
Kursning oylik to'lovi taxminan 300 000 so'm miqdorida belgilanadi.
To'lov kurs uchun oldindan amalga oshiriladi.
O'quvchi kurs sifatidan norozi bo'lsa, 30% xizmat haqi ushlab qolingan holda to'lov qaytarilishi mumkin.
Boshqa hollarda to'lov qaytarilmaydi.
Qaytariladigan to'lov (agar mavjud bo'lsa) 1 oy ichida amalga oshiriladi.
O'quvchi kursni 50% yoki undan ko'prog'ini o'tgan bo'lsa, to'lov qaytarilmaydi.

6. KAFOLATLAR VA MA'SULIYAT
Markaz o'quvchi kursni to'liq o'tagan va topshiriqlarni bajargan taqdirda darajasining oshishini kafolatlaydi.
O'quvchi tomonidan intizom buzilishi, topshiriqlarning muntazam yuborilmasligi yoki muloqotdagi qo'pol xatti-harakatlar uchun Markaz chetlatish huquqiga ega.
Shartnomadagi barcha shartlarni buzgan tomon ma'suliyatni o'z zimmasiga oladi.

7. SHARTNOMA MUDDATI
Ushbu shartnoma o'quvchi kursga ro'yxatdan o'tgan paytdan boshlab kuchga kiradi.
Kurs yakunlangandan so'ng avtomatik ravishda o'z kuchini yo'qotadi.

8. MAXSUS QOIDALAR
DIQQAT: Kurs uchun qabul hali ochilmagan.
Hozirda barcha video darslar va manbalar sifatli shaklda tayyorlanmoqda.
Ro'yxatdan o'tgan o'quvchilar uchun kurs ochilishi haqida oldindan xabar beriladi.
Har bir bosqich yakunida imtihon o'tkazilib, natijalarga ko'ra keyingi bosqichga o'tiladi.

9. TOMONLARNING ROZILIGI
Quyidagi "Tasdiqlayman" tugmasini bosish orqali O'quvchi shartlar bilan tanishganini va rozi ekanini bildiradi.
"""

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    group_id INTEGER,
    expires_at INTEGER DEFAULT 0,
    phone TEXT,
    agreed_at INTEGER
);
CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    photo_file TEXT,
    status TEXT,
    created_at INTEGER,
    admin_id INTEGER
);
CREATE TABLE IF NOT EXISTS user_groups(
    user_id INTEGER,
    group_id INTEGER,
    expires_at INTEGER,
    PRIMARY KEY (user_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id);
CREATE INDEX IF NOT EXISTS idx_users_expires ON users(expires_at);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_pay_status_created ON payments(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ug_user ON user_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_ug_group ON user_groups(group_id);
CREATE INDEX IF NOT EXISTS idx_ug_expires ON user_groups(expires_at);
"""

def _ensure_db_dir():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
            logger.info(f"Created database directory: {d}")
        except Exception as e:
            logger.warning(f"Failed to create database directory: {e}")

async def db_init():
    _ensure_db_dir()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(CREATE_SQL)
            cur = await db.execute("PRAGMA table_info(users)")
            cols = [r[1] for r in await cur.fetchall()]
            if "phone" not in cols:
                await db.execute("ALTER TABLE users ADD COLUMN phone TEXT;")
            if "agreed_at" not in cols:
                await db.execute("ALTER TABLE users ADD COLUMN agreed_at INTEGER;")
            await db.commit()
        logger.info(f"Database initialized successfully at {DB_PATH}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def add_payment(user: Message, file_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments(user_id, photo_file, status, created_at) VALUES(?,?,?,?)",
            (user.from_user.id, file_id, "pending", int(datetime.utcnow().timestamp()))
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        return int(row[0])

async def set_payment_status(pid: int, status: str, admin_id: Optional[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET status=?, admin_id=? WHERE id=?", (status, admin_id, pid))
        await db.commit()

async def get_payment(pid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, user_id, status FROM payments WHERE id=?", (pid,))
        return await cur.fetchone()

async def upsert_user(uid: int, username: str, full_name: str, group_id: int, expires_at: int, phone: Optional[str] = None, agreed_at: Optional[int] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users(user_id, username, full_name, group_id, expires_at, phone, agreed_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                group_id=excluded.group_id,
                expires_at=excluded.expires_at,
                phone=COALESCE(excluded.phone, users.phone),
                agreed_at=COALESCE(excluded.agreed_at, users.agreed_at)
        """, (uid, username, full_name, group_id, expires_at, phone, agreed_at))
        await db.commit()

async def update_user_expiry(uid: int, new_expires_at: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET expires_at=? WHERE user_id=?", (new_expires_at, uid))
        await db.commit()

async def update_user_phone(uid: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, uid))
        await db.commit()

async def update_user_fullname(uid: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET full_name=? WHERE user_id=?", (full_name, uid))
        await db.commit()

async def update_user_agreed(uid: int, ts: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET agreed_at=? WHERE user_id=?", (ts, uid))
        await db.commit()

async def clear_user_group(uid: int, gid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET group_id=NULL WHERE user_id=? AND group_id=?", (uid, gid))
        await db.commit()

async def add_user_group(uid: int, gid: int, expires_at: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_groups(user_id, group_id, expires_at)
            VALUES(?,?,?)
            ON CONFLICT(user_id, group_id) DO UPDATE SET expires_at=excluded.expires_at
        """, (uid, gid, expires_at))
        await db.commit()

async def clear_user_group_extra(uid: int, gid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_groups WHERE user_id=? AND group_id=?", (uid, gid))
        await db.commit()

async def get_user(uid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, group_id, expires_at, username, full_name, phone, agreed_at FROM users WHERE user_id=?", (uid,))
        return await cur.fetchone()

async def all_members_of_group(gid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, username, full_name, expires_at, phone FROM users WHERE group_id=?", (gid,))
        u_rows = await cur.fetchall()
        cur = await db.execute("""
            SELECT ug.user_id, u.username, u.full_name, ug.expires_at, u.phone
            FROM user_groups ug
            LEFT JOIN users u ON u.user_id = ug.user_id
            WHERE ug.group_id=?
        """, (gid,))
        g_rows = await cur.fetchall()
    merged = {}
    for r in u_rows + g_rows:
        uid, username, full_name, exp, phone = r
        if uid not in merged or (merged[uid][2] or 0) < (exp or 0):
            merged[uid] = (username, full_name, exp, phone)
    return [(uid, data[0], data[1], data[2], data[3]) for uid, data in merged.items()]

async def expired_users():
    now = int(datetime.utcnow().timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, group_id, expires_at FROM users WHERE expires_at>0 AND expires_at<=?", (now,))
        return await cur.fetchall()

async def expired_user_groups():
    now = int(datetime.utcnow().timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, group_id, expires_at FROM user_groups WHERE expires_at>0 AND expires_at<=?", (now,))
        return await cur.fetchall()

async def soon_expiring_users(days: int):
    now = int(datetime.utcnow().timestamp())
    upper = now + days * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, group_id, expires_at FROM users WHERE expires_at>? AND expires_at<=?", (now, upper))
        return await cur.fetchall()

async def soon_expiring_user_groups(days: int):
    now = int(datetime.utcnow().timestamp())
    upper = now + days * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, group_id, expires_at FROM user_groups WHERE expires_at>? AND expires_at<=?", (now, upper))
        return await cur.fetchall()

def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta orqali", callback_data="pay_card")],
        [InlineKeyboardButton(text="🔗 Havola orqali", callback_data="pay_link")],
    ])

def approve_keyboard(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve (hoziroq)", callback_data=f"ap_now:{pid}")],
        [InlineKeyboardButton(text="🗓 Approve (sana tanlash)", callback_data=f"ap_date:{pid}")],
        [InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{pid}")],
    ])

def warn_keyboard(uid: int, gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ To'lov qildi", callback_data=f"warn_paid:{uid}:{gid}"),
            InlineKeyboardButton(text="⌛ Qilmadi", callback_data=f"warn_notpaid:{uid}:{gid}")
        ],
        [
            InlineKeyboardButton(text="❌ Chiqarib yubor", callback_data=f"warn_kick:{uid}:{gid}")
        ]
    ])

def multi_select_kb(pid: int, groups: list[tuple[int, str]], selected: set[int], with_date_iso: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    for gid, title in groups:
        mark = "✅" if gid in selected else "☑️"
        rows.append([InlineKeyboardButton(text=f"{mark} {title}", callback_data=f"ms_toggle:{pid}:{gid}")])
    if with_date_iso:
        confirm_cb = f"ms_confirm:{pid}:with_date:{with_date_iso}"
    else:
        confirm_cb = f"ms_confirm:{pid}"
    rows.append([InlineKeyboardButton(text="✅ Tasdiqlash (bir necha guruh)", callback_data=confirm_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def multi_select_entry_kb(pid: int, with_date_iso: Optional[str]) -> InlineKeyboardMarkup:
    if with_date_iso:
        single_cb = f"ap_single:{pid}:with_date:{with_date_iso}"
        multi_cb  = f"ms_open:{pid}:with_date:{with_date_iso}"
    else:
        single_cb = f"ap_single:{pid}"
        multi_cb  = f"ms_open:{pid}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Bir nechta guruh", callback_data=multi_cb)],
        [InlineKeyboardButton(text="➡️ Bitta guruh tanlash", callback_data=single_cb)]
    ])

def contract_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlayman", callback_data="terms_agree")],
        [InlineKeyboardButton(text="❌ Rad etaman", callback_data="terms_decline")]
    ])

def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

async def resolve_group_titles() -> list[tuple[int, str]]:
    result = []
    for gid in GROUP_IDS:
        try:
            chat = await bot.get_chat(gid)
            title = chat.title or str(gid)
        except Exception as e:
            logger.warning(f"Failed to get title for group {gid}: {e}")
            title = str(gid)
        result.append((gid, title))
    return result

async def send_one_time_link(group_id: int, user_id: int) -> str:
    expire = int((datetime.utcnow() + timedelta(hours=INVITE_LINK_EXPIRE_HOURS)).timestamp())
    link = await bot.create_chat_invite_link(
        chat_id=group_id,
        name=f"sub-{user_id}",
        expire_date=expire,
        member_limit=1
    )
    return link.invite_link

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

async def fetch_user_profile(uid: int) -> tuple[str, str]:
    try:
        ch = await bot.get_chat(uid)
        uname = ch.username or ""
        full = (ch.first_name or "")
        if getattr(ch, "last_name", None):
            full = (full + " " + ch.last_name).strip()
        if not full:
            full = str(uid)
        return uname, full
    except Exception as e:
        logger.warning(f"Failed to fetch profile for user {uid}: {e}")
        return "", str(uid)

def human_left(expires_at: int) -> tuple[str, int]:
    if not expires_at:
        return "belgilanmagan", 0
    dt_utc = datetime.utcfromtimestamp(expires_at)
    dt_loc = dt_utc + TZ_OFFSET
    days_left = (dt_loc.date() - (datetime.utcnow() + TZ_OFFSET).date()).days
    return dt_loc.strftime("%Y-%m-%d"), days_left

def build_contract_files(user_fullname: str, user_phone: Optional[str]):
    stamped = f"{CONTRACT_TEXT}\n\n---\nO'quvchi: {user_fullname}\nTelefon: {user_phone or '-'}\nSana: {(datetime.utcnow()+TZ_OFFSET).strftime('%Y-%m-%d %H:%M')}\n"
    txt_buf = io.BytesIO(stamped.encode("utf-8"))
    txt_buf.name = "shartnoma.txt"
    pdf_buf = None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        pdf_buf = io.BytesIO()
        pdf_buf.name = "shartnoma.pdf"
        c = canvas.Canvas(pdf_buf, pagesize=A4)
        width, height = A4
        y = height - 40
        for line in stamped.splitlines():
            c.drawString(40, y, line[:110])
            y -= 14
            if y < 40:
                c.showPage()
                y = height - 40
        c.save()
        pdf_buf.seek(0)
    except Exception as e:
        logger.warning(f"Failed to create PDF contract: {e}")
        pdf_buf = None
    txt_buf.seek(0)
    return txt_buf, pdf_buf

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

@dp.message(Command("start"))
async def cmd_start(m: Message):
    try:
        await m.answer("📄 *ONLAYN O'QUV SHARTNOMA*\n\n" + CONTRACT_TEXT, reply_markup=contract_keyboard(), parse_mode="Markdown")
        uname, full = await fetch_user_profile(m.from_user.id)
        await upsert_user(m.from_user.id, uname, full, group_id=0, expires_at=0)
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.callback_query(F.data == "terms_agree")
async def cb_terms_agree(c: CallbackQuery):
    try:
        await update_user_agreed(c.from_user.id, int(datetime.utcnow().timestamp()))
        WAIT_CONTACT_FOR.add(c.from_user.id)
        await c.message.answer("✅ Shartnoma tasdiqlandi.\n\nIltimos, 📱 *telefon raqamingizni* yuboring:", reply_markup=contact_keyboard(), parse_mode="Markdown")
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_terms_agree: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "terms_decline")
async def cb_terms_decline(c: CallbackQuery):
    await c.message.answer("❌ Shartnoma rad etildi. Xizmatlardan foydalanish uchun shartnomani tasdiqlash kerak.")
    await c.answer()

@dp.message(F.text)
async def on_admin_date_handler(m: Message):
    if m.from_user.id in WAIT_DATE_FOR:
        try:
            raw = (m.text or "").strip().replace("/", "-")
            if not DATE_RE.match(raw):
                return await m.answer("❗ Format noto'g'ri. To'g'ri ko'rinish: 2025-10-01")
            try:
                start_dt = datetime.strptime(raw, "%Y-%m-%d")
            except Exception:
                return await m.answer("❗ Sana tushunilmadi. Misol: 2025-10-01")
            pid = WAIT_DATE_FOR.pop(m.from_user.id, None)
            if not pid:
                return await m.answer("Sessiya topilmadi. Iltimos, Approve (sana tanlash) tugmasidan qayta boshlang.")
            iso = start_dt.isoformat()
            await m.answer("✅ Sana qabul qilindi.\nEndi guruh(lar)ga qo'shish usulini tanlang:", reply_markup=multi_select_entry_kb(pid, with_date_iso=iso))
        except Exception as e:
            logger.error(f"Error in on_admin_date_handler: {e}")
            await m.answer("Xatolik yuz berdi")
        return
    
    if m.from_user.id in WAIT_CONTACT_FOR:
        phone_pattern = re.compile(r"^\+?\d{9,15}$")
        if phone_pattern.match((m.text or "").strip()):
            try:
                phone = m.text.strip()
                await update_user_phone(m.from_user.id, phone)
                WAIT_CONTACT_FOR.discard(m.from_user.id)
                WAIT_FULLNAME_FOR.add(m.from_user.id)
                await m.answer("✅ Telefon raqam qabul qilindi.\n\n📛 Endi *ism va familiyangizni* yozing (masalan: Hasanov Alisher):", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error processing phone text: {e}")
                await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
            return

@dp.message(F.contact)
async def on_contact(m: Message):
    if m.from_user.id not in WAIT_CONTACT_FOR:
        return
    try:
        contact = m.contact
        phone = contact.phone_number
        await update_user_phone(m.from_user.id, phone)
        WAIT_CONTACT_FOR.discard(m.from_user.id)
        
        full_name = ""
        if contact.first_name:
            full_name = contact.first_name
            if contact.last_name:
                full_name += " " + contact.last_name
        if not full_name:
            full_name = (m.from_user.first_name or "") + (" " + (m.from_user.last_name or "") if m.from_user.last_name else "")
            full_name = full_name.strip()
        if full_name:
            await update_user_fullname(m.from_user.id, full_name)
        else:
            WAIT_FULLNAME_FOR.add(m.from_user.id)
        
        txt_buf, pdf_buf = build_contract_files(full_name or str(m.from_user.id), phone)
        try:
            await bot.send_document(m.from_user.id, FSInputFile(txt_buf, filename=txt_buf.name))
            if pdf_buf:
                await bot.send_document(m.from_user.id, FSInputFile(pdf_buf, filename=pdf_buf.name))
        except Exception as e:
            logger.warning(f"Failed to send contract documents to user: {e}")
        
        for aid in ADMIN_IDS:
            try:
                await bot.send_document(aid, FSInputFile(io.BytesIO(txt_buf.getvalue()), filename="shartnoma.txt"), caption=f"🆕 Shartnoma — ID: {m.from_user.id}")
                if pdf_buf:
                    await bot.send_document(aid, FSInputFile(io.BytesIO(pdf_buf.getvalue()), filename="shartnoma.pdf"))
            except Exception as e:
                logger.warning(f"Failed to send contract documents to admin {aid}: {e}")
        
        await m.answer("Rahmat! Endi to'lov turini tanlang va chekni yuboring.", reply_markup=start_keyboard())
    except Exception as e:
        logger.error(f"Error in on_contact: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.message(F.text.func(lambda t: bool(t) and len(t.strip()) >= 3))
async def on_fullname_text(m: Message):
    if m.from_user.id in WAIT_FULLNAME_FOR:
        try:
            fullname = m.text.strip()
            await update_user_fullname(m.from_user.id, fullname)
            WAIT_FULLNAME_FOR.discard(m.from_user.id)
            
            user_row = await get_user(m.from_user.id)
            if user_row:
                _uid, _gid, _exp, _username, _full, phone, _ag = user_row
                if phone:
                    txt_buf, pdf_buf = build_contract_files(fullname, phone)
                    try:
                        await bot.send_document(m.from_user.id, FSInputFile(txt_buf, filename=txt_buf.name))
                        if pdf_buf:
                            await bot.send_document(m.from_user.id, FSInputFile(pdf_buf, filename=pdf_buf.name))
                    except Exception as e:
                        logger.warning(f"Failed to send contract documents to user: {e}")
                    
                    for aid in ADMIN_IDS:
                        try:
                            await bot.send_document(aid, FSInputFile(io.BytesIO(txt_buf.getvalue()), filename="shartnoma.txt"), caption=f"🆕 Shartnoma — ID: {m.from_user.id}")
                            if pdf_buf:
                                await bot.send_document(aid, FSInputFile(io.BytesIO(pdf_buf.getvalue()), filename="shartnoma.pdf"))
                        except Exception as e:
                            logger.warning(f"Failed to send contract documents to admin {aid}: {e}")
            
            await m.answer("✅ Ism familiya saqlandi. Endi to'lov turini tanlang:", reply_markup=start_keyboard())
        except Exception as e:
            logger.error(f"Error in on_fullname_text: {e}")
            await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.callback_query(F.data == "pay_card")
async def cb_pay_card(c: CallbackQuery):
    await c.message.answer("💳 Karta raqami:\n 9860160130847827 H.Halikova ")
    await c.answer()

@dp.callback_query(F.data == "pay_link")
async def cb_pay_link(c: CallbackQuery):
    await c.message.answer(
        "🔗 To'lov havolasi\n"
        "PAYME ORQALI: https://payme.uz/fallback/merchant/?id=68aebaff42ec20bb02a46c8c\n\n"
        "To'lovdan so'ng chekni shu chatga yuboring.\n"
        "CLICK ORQALI: https://indoor.click.uz/pay?id=081968&t=0 "
    )
    await c.answer()

@dp.message(F.photo)
async def on_photo(m: Message):
    try:
        pid = await add_payment(m, m.photo[-1].file_id)
        await m.answer("✅ Chekingiz qabul qilindi. Admin tekshiradi.")
        kb = approve_keyboard(pid)
        caption = (
            f"🧾 Yangi to'lov cheki\n"
            f"{m.from_user.full_name} (@{m.from_user.username or 'no_username'})\n"
            f"ID: {m.from_user.id}\n"
            f"Payment ID: {pid}"
        )
        for aid in ADMIN_IDS:
            try:
                await bot.send_photo(aid, m.photo[-1].file_id, caption=caption, reply_markup=kb)
            except Exception as e:
                logger.warning(f"Failed to send payment notification to admin {aid}: {e}")
    except Exception as e:
        logger.error(f"Error in on_photo: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.callback_query(F.data.startswith("ap_now:"))
async def cb_approve_now(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        pid = int(c.data.split(":")[1])
        row = await get_payment(pid)
        if not row:
            return await c.answer("Payment topilmadi", show_alert=True)
        _pid, _uid, _status = row
        if _status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        if not GROUP_IDS:
            return await c.answer("ENV: PRIVATE_GROUP_ID bo'sh. Guruh chat_id larini kiriting.", show_alert=True)
        await c.message.answer("🧭 Qanday qo'shamiz?", reply_markup=multi_select_entry_kb(pid, with_date_iso=None))
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_approve_now: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("ap_date:"))
async def cb_approve_date(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        pid = int(c.data.split(":")[1])
        row = await get_payment(pid)
        if not row:
            return await c.answer("Payment topilmadi", show_alert=True)
        _pid, _uid, _status = row
        if _status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        WAIT_DATE_FOR[c.from_user.id] = pid
        await c.message.answer("🗓 Boshlanish sanasini kiriting: YYYY-MM-DD (masalan 2025-10-01)")
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_approve_date: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("ap_single:"))
async def cb_ap_single(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1])
        with_date_iso = None
        if len(parts) >= 4 and parts[2] == "with_date":
            with_date_iso = parts[3]
        groups = await resolve_group_titles()
        rows = []
        for gid, title in groups:
            cb = f"pick_group:{pid}:{gid}" if not with_date_iso else f"pick_group:{pid}:{gid}:with_date:{with_date_iso}"
            rows.append([InlineKeyboardButton(text=title, callback_data=cb)])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await c.message.answer("🧭 Bitta guruhni tanlang:", reply_markup=kb)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_ap_single: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("ms_open:"))
async def cb_ms_open(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1])
        with_date_iso = None
        if len(parts) >= 4 and parts[2] == "with_date":
            with_date_iso = parts[3]
        groups = await resolve_group_titles()
        MULTI_PICK[c.from_user.id] = {"pid": pid, "start_iso": with_date_iso, "selected": set()}
        kb = multi_select_kb(pid, groups, set(), with_date_iso)
        await c.message.answer("🧭 Bir necha guruhni tanlang (✅ belgilab, so'ng Tasdiqlash):", reply_markup=kb)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_ms_open: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("ms_toggle:"))
async def cb_ms_toggle(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1]); gid = int(parts[2])
        state = MULTI_PICK.get(c.from_user.id)
        if not state or state.get("pid") != pid:
            return await c.answer("Sessiya topilmadi. Qaytadan oching.", show_alert=True)
        sel: set = state["selected"]
        if gid in sel:
            sel.remove(gid)
        else:
            sel.add(gid)
        groups = await resolve_group_titles()
        kb = multi_select_kb(pid, groups, sel, state.get("start_iso"))
        await c.message.answer("✅ Yangilandi. Davom eting:", reply_markup=kb)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_ms_toggle: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("ms_confirm:"))
async def cb_ms_confirm(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1])
        start_iso = None
        if len(parts) >= 4 and parts[2] == "with_date":
            start_iso = parts[3]
        row = await get_payment(pid)
        if not row:
            return await c.answer("Payment topilmadi", show_alert=True)
        _pid, user_id, status = row
        if status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        start_dt = datetime.utcnow()
        if start_iso:
            try:
                start_dt = datetime.fromisoformat(start_iso)
            except Exception:
                pass
        expires_at = int((start_dt + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        username, full_name = await fetch_user_profile(user_id)
        state = MULTI_PICK.get(c.from_user.id)
        if not state or state.get("pid") != pid:
            return await c.answer("Sessiya topilmadi.", show_alert=True)
        selected: set[int] = set(state.get("selected", set()))
        if not selected:
            return await c.answer("Hech bo'lmaganda bitta guruhni tanlang.", show_alert=True)
        primary_gid = list(selected)[0]
        await upsert_user(uid=user_id, username=username, full_name=full_name, group_id=primary_gid, expires_at=expires_at)
        await set_payment_status(pid, "approved", c.from_user.id)
        extra_gids = [g for g in selected if g != primary_gid]
        for g in extra_gids:
            await add_user_group(user_id, g, expires_at)
        links_out = []
        titles = dict(await resolve_group_titles())
        try:
            link = await send_one_time_link(primary_gid, user_id)
            links_out.append(f"• {titles.get(primary_gid, primary_gid)}: {link}")
        except Exception as e:
            links_out.append(f"• {titles.get(primary_gid, primary_gid)}: link yaratishda xato ({e})")
        for g in extra_gids:
            try:
                link = await send_one_time_link(g, user_id)
                links_out.append(f"• {titles.get(g, g)}: {link}")
            except Exception as e:
                links_out.append(f"• {titles.get(g, g)}: link yaratishda xato ({e})")
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        try:
            await bot.send_message(
                user_id,
                "✅ To'lov tasdiqlandi!\n"
                f"Quyidagi guruhlarga kirish havolalari (har biri 1 martalik, {INVITE_LINK_EXPIRE_HOURS} soat ichida):\n"
                + "\n".join(links_out) +
                f"\n\n⏳ Obuna tugash sanasi: {human_exp}"
            )
        except Exception as e:
            logger.warning(f"Failed to send approval message to user {user_id}: {e}")
        await c.message.answer("✅ Tanlangan guruhlarga havolalar yuborildi. (Birinchisi asosiy guruh sifatida saqlandi)")
        MULTI_PICK.pop(c.from_user.id, None)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_ms_confirm: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("pick_group:"))
async def cb_pick_group(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        try:
            pid = int(parts[1])
            gid = int(parts[2])
        except Exception:
            return await c.answer("Xatolik: noto'g'ri callback.", show_alert=True)
        row = await get_payment(pid)
        if not row:
            return await c.answer("Payment topilmadi", show_alert=True)
        _pid, user_id, status = row
        if status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        start_dt = datetime.utcnow()
        if len(parts) >= 5 and parts[3] == "with_date":
            try:
                start_dt = datetime.fromisoformat(parts[4])
            except Exception:
                pass
        expires_at = int((start_dt + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        username, full_name = await fetch_user_profile(user_id)
        await upsert_user(uid=user_id, username=username, full_name=full_name, group_id=gid, expires_at=expires_at)
        await set_payment_status(pid, "approved", c.from_user.id)
        try:
            link = await send_one_time_link(gid, user_id)
        except Exception as e:
            await c.message.answer(f"Link yaratishda xato: {e}")
            return await c.answer()
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        try:
            await bot.send_message(
                user_id,
                "✅ To'lov tasdiqlandi!\n"
                f"Guruhga kirish havolasi (1 martalik, {INVITE_LINK_EXPIRE_HOURS} soat ichida):\n{link}\n\n"
                f"⏳ Obuna tugash sanasi: {human_exp}"
            )
        except Exception as e:
            logger.warning(f"Failed to send approval message to user {user_id}: {e}")
        await c.message.answer("✅ Tasdiqlandi va havola yuborildi.")
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_pick_group: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("reject:"))
async def cb_reject(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        pid = int(c.data.split(":")[1])
        await set_payment_status(pid, "rejected", c.from_user.id)
        await c.message.answer("❌ To'lov rad etildi.")
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_reject: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.message(Command("groups"))
async def cmd_groups(m: Message):
    if not is_admin(m.from_user.id):
        return
    if not GROUP_IDS:
        return await m.answer("PRIVATE_GROUP_ID bo'sh. Railway Variablesga kiriting.")
    rows = await resolve_group_titles()
    txt = "🔗 Ulangan guruhlar:\n" + "\n".join([f"• {t} — {gid}" for gid, t in rows])
    await m.answer(txt)

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Bu buyruq faqat adminlar uchun. Agar adminga kiritmoqchi bo'lsangiz, ADMIN_IDS env'iga ID qo'shing.\nID olish: /myid")
    if not GROUP_IDS:
        return await m.answer("⚙️ PRIVATE_GROUP_ID bo'sh. Railway > Variables da guruh chat_id'larini kiriting (vergul bilan).")
    
    now = int(datetime.utcnow().timestamp())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            total = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE expires_at > ?", (now,))
            active = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE expires_at <= ? AND expires_at > 0", (now,))
            expired = (await cur.fetchone())[0]
    except Exception as e:
        return await m.answer(f"💾 DB xatosi: {e}\nDB_PATH: {DB_PATH}")
    
    header = (
        "📊 Statistika (umumiy)\n"
        f"— Jami foydalanuvchi: {total}\n"
        f"— Aktiv: {active}\n"
        f"— Muddati tugagan: {expired}\n\n"
        "📚 Guruhlar kesimi:"
    )
    await m.answer(header)
    
    titles = dict(await resolve_group_titles())
    for gid in GROUP_IDS:
        users = await all_members_of_group(gid)
        title = titles.get(gid, str(gid))
        if not users:
            await m.answer(f"🏷 {title} — 0 a'zo")
            continue
        
        lines = [f"🏷 {title} — {len(users)} a'zo"]
        now_loc_date = (datetime.utcnow() + TZ_OFFSET).date()
        MAX_SHOW = 40
        users_sorted = sorted(users, key=lambda r: (r[3] or 0), reverse=True)
        for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted[:MAX_SHOW], start=1):
            tag = f"@{username}" if username else (full_name or uid)
            phone_s = f" 📞 {phone}" if phone else ""
            if exp and exp > 0:
                exp_str, left = human_left(exp)
                state = "✅" if (datetime.utcfromtimestamp(exp) + TZ_OFFSET).date() >= now_loc_date else "⚠️"
                lines.append(f"{i}. {tag}{phone_s} — {state} {exp_str} (qoldi: {max(left,0)} kun)")
            else:
                lines.append(f"{i}. {tag}{phone_s} — muddat belgilanmagan")
        if len(users_sorted) > MAX_SHOW:
            lines.append(f"... va yana {len(users_sorted)-MAX_SHOW} ta")
        
        await m.answer("\n".join(lines))

@dp.message(Command("gstats"))
async def cmd_gstats(m: Message):
    """Batafsil guruh statistikasi: foydalanuvchi, telefon, tugash sanasi."""
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Bu buyruq faqat adminlar uchun.")
    try:
        titles = dict(await resolve_group_titles())
        for gid in GROUP_IDS:
            users = await all_members_of_group(gid)
            title = titles.get(gid, str(gid))
            if not users:
                await m.answer(f"🏷 {title} — 0 a'zo")
                continue
            
            buf = [f"📚 *{title}* — {len(users)} a'zo\n"]
            users_sorted = sorted(users, key=lambda r: (r[3] or 0), reverse=True)
            for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted, start=1):
                tag = f"@{username}" if username else (full_name or str(uid))
                exp_str, left = human_left(exp) if exp else ("belgilanmagan", 0)
                phone_s = phone or "-"
                buf.append(f"{i}. {tag} | 📞 {phone_s} | ⏳ {exp_str} ({left} kun)")
            await m.answer("\n".join(buf), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cmd_gstats: {e}")
        await m.answer(f"Xatolik yuz berdi: {e}")

_WARNED_CACHE: dict[tuple[int, int, str], int] = {}

async def _warn_and_buttons(uid: int, gid: int, exp_at: int, reason: str):
    now_ts = int(datetime.utcnow().timestamp())
    key = (uid, gid or 0, reason)
    last = _WARNED_CACHE.get(key, 0)
    if now_ts - last < 3600:
        return
    _WARNED_CACHE[key] = now_ts
    row = await get_user(uid)
    _username = ""
    _full = str(uid)
    if row:
        _uid, _gid, _exp, _username, _full, _phone, _ag = row
    exp_str, left = human_left(exp_at)
    if reason == "soon":
        user_text = (
            "⏰ Obunangiz yaqin kunlarda tugaydi.\n"
            f"⏳ Tugash sanasi: {exp_str}\n"
            f"📆 Qolgan kun: {max(left,0)}\n\n"
            "Iltimos, to'lovni vaqtida yangilang va chekni shu botga yuboring."
        )
    else:
        user_text = (
            "⚠️ Obunangiz muddati tugagan.\n"
            f"⏳ Tugash sanasi: {exp_str}\n"
            "Iltimos, to'lovni yangilang va chekni shu botga yuboring."
        )
    try:
        await bot.send_message(uid, user_text)
    except Exception as e:
        logger.warning(f"Failed to send warning to user {uid}: {e}")
    tag = f"@{_username}" if _username else _full
    titles = dict(await resolve_group_titles())
    gtitle = titles.get(gid, str(gid))
    admin_title = "⏰ *Obuna yaqin orada tugaydi*" if reason == "soon" else "⚠️ *Obuna muddati tugagan a'zo*"
    msg = (f"{admin_title}\n" f"• Foydalanuvchi: {tag}\n" f"• ID: `{uid}`\n" f"• Guruh: {gtitle} (`{gid}`)\n" f"• Tugash: {exp_str}\n\n" "Amalni tanlang:")
    kb = warn_keyboard(uid, gid)
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, msg, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to send warning to admin {aid}: {e}")

async def auto_kick_loop():
    await asyncio.sleep(5)
    while True:
        try:
            try:
                for uid, gid, exp_at in await soon_expiring_users(REMIND_DAYS):
                    await _warn_and_buttons(uid, gid, exp_at, reason="soon")
            except Exception:
                logger.exception("soon_expiring_users failed")
            try:
                for uid, gid, exp_at in await soon_expiring_user_groups(REMIND_DAYS):
                    await _warn_and_buttons(uid, gid, exp_at, reason="soon")
            except Exception:
                logger.exception("soon_expiring_user_groups failed")
            try:
                for uid, gid, exp_at in await expired_users():
                    await _warn_and_buttons(uid, gid, exp_at, reason="expired")
            except Exception:
                logger.exception("expired_users failed")
            try:
                for uid, gid, exp_at in await expired_user_groups():
                    await _warn_and_buttons(uid, gid, exp_at, reason="expired")
            except Exception:
                logger.exception("expired_user_groups failed")
            await asyncio.sleep(60)
        except Exception as e:
            logger.exception(e)
            await asyncio.sleep(10)

@dp.callback_query(F.data.startswith("warn_paid:"))
async def cb_warn_paid(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        new_exp = int((datetime.utcnow() + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        await update_user_expiry(uid, new_exp)
        await add_user_group(uid, gid, new_exp)
        exp_str, _ = human_left(new_exp)
        try:
            await bot.send_message(uid, f"✅ To'lov tasdiqlandi. Obuna yangilandi.\n⏳ Yangi tugash sanasi: {exp_str}")
        except Exception as e:
            logger.warning(f"Failed to notify user {uid}: {e}")
        uname, _ = await fetch_user_profile(uid)
        await c.message.answer(f"✅ @{uname or uid} uchun obuna {SUBSCRIPTION_DAYS} kunga uzaytirildi. Yangi sana: {exp_str}")
        await c.answer("Yangilandi")
    except Exception as e:
        logger.error(f"Error in cb_warn_paid: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("warn_notpaid:"))
async def cb_warn_notpaid(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    parts = c.data.split(":")
    uid = int(parts[1]); gid = int(parts[2])
    await c.message.answer(f"⌛ Foydalanuvchi {uid} hali to'lov qilmagan deb qayd etildi.")
    await c.answer("Qayd etildi")

@dp.callback_query(F.data.startswith("warn_kick:"))
async def cb_warn_kick(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        try:
            member = await bot.get_chat_member(gid, uid)
            if member.status in ("administrator", "creator"):
                await c.message.answer("❗ Bu foydalanuvchi guruhda admin/egadir. Chiqarib bo'lmaydi.")
                return await c.answer()
        except Exception:
            pass
        try:
            await bot.ban_chat_member(gid, uid)
            await bot.unban_chat_member(gid, uid)
            await clear_user_group(uid, gid)
            await clear_user_group_extra(uid, gid)
            await c.message.answer(f"❌ {uid} guruhdan chiqarildi.")
            try:
                await bot.send_message(uid, "❌ Obuna yangilanmagani sababli guruhdan chiqarildingiz.")
            except Exception as e:
                logger.warning(f"Failed to notify kicked user {uid}: {e}")
        except Exception as e:
            await c.message.answer(f"Chiqarishda xato: {e}")
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_warn_kick: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

async def main():
    logger.info("Starting bot...")
    await db_init()
    asyncio.create_task(auto_kick_loop())
    logger.info("Bot is now polling for updates")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
