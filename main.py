import os
import io
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile, BufferedInputFile,
    WebAppInfo
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
INVITE_LINK_EXPIRE_HOURS = int(os.getenv("INVITE_LINK_EXPIRE_HOURS", "72"))  # 3 kun = 72 soat
REMIND_DAYS = int(os.getenv("REMIND_DAYS", "3"))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not found. Please set it in .env file")

MINI_APP_URL = os.getenv("MINI_APP_URL", "")

TZ_OFFSET = timedelta(hours=5)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# PostgreSQL connection pool
db_pool: Optional[asyncpg.Pool] = None

WAIT_DATE_FOR: dict[int, int] = {}
MULTI_PICK: dict[int, dict] = {}
WAIT_CONTACT_FOR: set[int] = set()
WAIT_FULLNAME_FOR: set[int] = set()
NOT_PAID_COUNTER: dict[tuple[int, int], int] = {}
# Admin xabarlarini kuzatish (payment_id -> [message_ids])
ADMIN_MESSAGES: dict[int, list[int]] = {}

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
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    group_id BIGINT,
    expires_at BIGINT DEFAULT 0,
    phone TEXT,
    agreed_at BIGINT
);
CREATE TABLE IF NOT EXISTS payments(
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    photo_file TEXT,
    status TEXT,
    created_at BIGINT,
    admin_id BIGINT
);
CREATE TABLE IF NOT EXISTS user_groups(
    user_id BIGINT,
    group_id BIGINT,
    expires_at BIGINT,
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

async def db_init():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        async with db_pool.acquire() as conn:
            await conn.execute(CREATE_SQL)
            
            # Migration: course_name ustunini qo'shish (agar yo'q bo'lsa)
            try:
                await conn.execute("""
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS course_name TEXT;
                """)
                logger.info("Migration: course_name column added/verified")
            except Exception as me:
                logger.warning(f"Migration warning (likely already exists): {me}")
                
        logger.info("PostgreSQL database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def add_payment(user: Message, file_id: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO payments(user_id, photo_file, status, created_at) VALUES($1,$2,$3,$4) RETURNING id",
            user.from_user.id, file_id, "pending", int(datetime.utcnow().timestamp())
        )
        return int(row['id'])

async def set_payment_status(pid: int, status: str, admin_id: Optional[int]):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE payments SET status=$1, admin_id=$2 WHERE id=$3", status, admin_id, pid)

async def get_payment(pid: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, user_id, status, photo_file FROM payments WHERE id=$1", pid)
        return (row['id'], row['user_id'], row['status'], row['photo_file']) if row else None

async def upsert_user(uid: int, username: str, full_name: str, group_id: int, expires_at: int, phone: Optional[str] = None, agreed_at: Optional[int] = None):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, username, full_name, group_id, expires_at, phone, agreed_at)
            VALUES($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT(user_id) DO UPDATE SET
                username=EXCLUDED.username,
                full_name=EXCLUDED.full_name,
                group_id=EXCLUDED.group_id,
                expires_at=EXCLUDED.expires_at,
                phone=COALESCE(EXCLUDED.phone, users.phone),
                agreed_at=COALESCE(EXCLUDED.agreed_at, users.agreed_at)
        """, uid, username, full_name, group_id, expires_at, phone, agreed_at)

async def update_user_expiry(uid: int, new_expires_at: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET expires_at=$1 WHERE user_id=$2", new_expires_at, uid)

async def update_user_phone(uid: int, phone: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone=$1 WHERE user_id=$2", phone, uid)

async def update_user_fullname(uid: int, full_name: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET full_name=$1 WHERE user_id=$2", full_name, uid)

async def update_user_agreed(uid: int, ts: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET agreed_at=$1 WHERE user_id=$2", ts, uid)

async def update_user_course(uid: int, course_name: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET course_name=$1 WHERE user_id=$2", course_name, uid)

async def clear_user_group(uid: int, gid: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET group_id=NULL WHERE user_id=$1 AND group_id=$2", uid, gid)

async def add_user_group(uid: int, gid: int, expires_at: int):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_groups(user_id, group_id, expires_at)
            VALUES($1,$2,$3)
            ON CONFLICT(user_id, group_id) DO UPDATE SET expires_at=EXCLUDED.expires_at
        """, uid, gid, expires_at)

async def clear_user_group_extra(uid: int, gid: int):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM user_groups WHERE user_id=$1 AND group_id=$2", uid, gid)

async def get_user(uid: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id, group_id, expires_at, username, full_name, phone, agreed_at FROM users WHERE user_id=$1", uid)
        return (row['user_id'], row['group_id'], row['expires_at'], row['username'], row['full_name'], row['phone'], row['agreed_at']) if row else None

async def all_members_of_group(gid: int):
    async with db_pool.acquire() as conn:
        u_rows = await conn.fetch("SELECT user_id, username, full_name, expires_at, phone FROM users WHERE group_id=$1", gid)
        g_rows = await conn.fetch("""
            SELECT ug.user_id, u.username, u.full_name, ug.expires_at, u.phone
            FROM user_groups ug
            LEFT JOIN users u ON u.user_id = ug.user_id
            WHERE ug.group_id=$1
        """, gid)
    merged = {}
    for r in list(u_rows) + list(g_rows):
        uid, username, full_name, exp, phone = r['user_id'], r['username'], r['full_name'], r['expires_at'], r['phone']
        if uid not in merged or (merged[uid][2] or 0) < (exp or 0):
            merged[uid] = (username, full_name, exp, phone)
    return [(uid, data[0], data[1], data[2], data[3]) for uid, data in merged.items()]

async def expired_users():
    now = int(datetime.utcnow().timestamp())
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, group_id, expires_at FROM users WHERE expires_at>0 AND expires_at<=$1", now)
        return [(r['user_id'], r['group_id'], r['expires_at']) for r in rows]

async def expired_user_groups():
    now = int(datetime.utcnow().timestamp())
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, group_id, expires_at FROM user_groups WHERE expires_at>0 AND expires_at<=$1", now)
        return [(r['user_id'], r['group_id'], r['expires_at']) for r in rows]

async def soon_expiring_users(days: int):
    now = int(datetime.utcnow().timestamp())
    upper = now + days * 86400
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, group_id, expires_at FROM users WHERE expires_at>$1 AND expires_at<=$2", now, upper)
        return [(r['user_id'], r['group_id'], r['expires_at']) for r in rows]

async def soon_expiring_user_groups(days: int):
    now = int(datetime.utcnow().timestamp())
    upper = now + days * 86400
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, group_id, expires_at FROM user_groups WHERE expires_at>$1 AND expires_at<=$2", now, upper)
        return [(r['user_id'], r['group_id'], r['expires_at']) for r in rows]

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

def course_selection_keyboard() -> InlineKeyboardMarkup:
    courses = [
        ("A0 Standard", "course:A0 Standard"),
        ("A0 Premium", "course:A0 Premium"),
        ("A1 Standard", "course:A1 Standard"),
        ("A1 Premium", "course:A1 Premium"),
        ("A2 Standard", "course:A2 Standard"),
        ("A2 Premium", "course:A2 Premium"),
        ("B1 Standard", "course:B1 Standard"),
        ("B1 Premium", "course:B1 Premium"),
        ("B2 Standard", "course:B2 Standard"),
        ("B2 Premium", "course:B2 Premium"),
        ("CEFR PRO Standard", "course:CEFR PRO Standard"),
        ("CEFR PRO Premium", "course:CEFR PRO Premium"),
        ("Grammatika Standard", "course:Grammatika Standard"),
        ("Grammatika Premium", "course:Grammatika Premium"),
    ]
    
    keyboard = []
    for i in range(0, len(courses), 2):
        row = []
        row.append(InlineKeyboardButton(text=courses[i][0], callback_data=courses[i][1]))
        if i + 1 < len(courses):
            row.append(InlineKeyboardButton(text=courses[i + 1][0], callback_data=courses[i + 1][1]))
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

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
        member_limit=1,
        creates_join_request=False  # Avtomatik kirish, approval yo'q
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

def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Admin uchun doim ko'rinadigan tugmalar."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="✅ Tasdiqlangan to'lovlar"), KeyboardButton(text="⏳ Kutilayotgan to'lovlar")],
            [KeyboardButton(text="📎 Guruh linklari"), KeyboardButton(text="🧹 Tozalash")]
        ],
        resize_keyboard=True,
        persistent=True
    )

@dp.message(Command("start"))
async def cmd_start(m: Message):
    try:
        # Admin uchun alohida interfeys
        if is_admin(m.from_user.id):
            await m.answer(
                "👨‍💼 *ADMIN PANEL*\n\n"
                "Quyidagi tugmalardan birini tanlang:",
                reply_markup=admin_reply_keyboard(),
                parse_mode="Markdown"
            )
            return
        
        # Oddiy foydalanuvchilar uchun shartnoma va Mini App tugmasi
        keyboard = contract_keyboard()
        
        # Agar Mini App URL o'rnatilgan bo'lsa, tugma qo'shamiz
        if MINI_APP_URL:
            webapp_button = InlineKeyboardButton(
                text="📱 Ilovani ochish",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
            # Mavjud tugmalar ustiga qo'shamiz
            keyboard.inline_keyboard.insert(0, [webapp_button])
        
        await m.answer("📄 *ONLAYN O'QUV SHARTNOMA*\n\n" + CONTRACT_TEXT, reply_markup=keyboard, parse_mode="Markdown")
        uname, full = await fetch_user_profile(m.from_user.id)
        await upsert_user(m.from_user.id, uname, full, group_id=0, expires_at=0)
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await m.answer("Xabolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.callback_query(F.data == "terms_agree")
async def cb_terms_agree(c: CallbackQuery):
    try:
        await update_user_agreed(c.from_user.id, int(datetime.utcnow().timestamp()))
        await c.message.answer(
            "✅ Shartnoma tasdiqlandi.\n\n"
            "📚 Qaysi kursni tanladingiz?",
            reply_markup=course_selection_keyboard()
        )
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_terms_agree: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "terms_decline")
async def cb_terms_decline(c: CallbackQuery):
    await c.message.answer("❌ Shartnoma rad etildi. Xizmatlardan foydalanish uchun shartnomani tasdiqlash kerak.")
    await c.answer()

@dp.callback_query(F.data.startswith("course:"))
async def cb_course_select(c: CallbackQuery):
    try:
        course_name = c.data.split(":", 1)[1]
        
        # Database'ga kurs nomini saqlash
        await update_user_course(c.from_user.id, course_name)
        
        WAIT_CONTACT_FOR.add(c.from_user.id)
        await c.message.answer(
            f"✅ Kurs tanlandi: *{course_name}*\n\n"
            "📞 Endi telefon raqamingizni yuboring:",
            reply_markup=contact_keyboard(),
            parse_mode="Markdown"
        )
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_course_select: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.message(Command("myid"))
async def cmd_myid(m: Message):
    await m.answer(f"🆔 Sizning Telegram ID: `{m.from_user.id}`", parse_mode="Markdown")

@dp.message(Command("expiring"))
async def cmd_expiring(m: Message):
    """Obunasi yaqin kunlarda tugaydigan foydalanuvchilarni ko'rsatish."""
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        soon_users = []
        for uid, gid, exp_at in await soon_expiring_users(REMIND_DAYS):
            row = await get_user(uid)
            if row:
                _uid, _gid, _exp, username, full_name, phone, _ag = row
                exp_str, left = human_left(exp_at)
                soon_users.append((uid, gid, exp_at, username, full_name, left))
        
        for uid, gid, exp_at in await soon_expiring_user_groups(REMIND_DAYS):
            row = await get_user(uid)
            if row:
                _uid, _gid, _exp, username, full_name, phone, _ag = row
                exp_str, left = human_left(exp_at)
                soon_users.append((uid, gid, exp_at, username, full_name, left))
        
        if not soon_users:
            return await m.answer(f"✅ Keyingi {REMIND_DAYS} kun ichida obunasi tugaydigan foydalanuvchilar yo'q.")
        
        soon_users.sort(key=lambda x: x[2])
        titles = dict(await resolve_group_titles())
        
        lines = [f"⏰ *Obunasi yaqin kunlarda tugaydiganlar* (keyingi {REMIND_DAYS} kun):\n"]
        for uid, gid, exp_at, username, full_name, left in soon_users[:20]:
            exp_str, _ = human_left(exp_at)
            tag = f"@{username}" if username else full_name or str(uid)
            gtitle = titles.get(gid, str(gid))
            lines.append(f"• {tag} (ID: `{uid}`)")
            lines.append(f"  Guruh: {gtitle}")
            lines.append(f"  Tugash: {exp_str} ({left} kun qoldi)\n")
        
        if len(soon_users) > 20:
            lines.append(f"... va yana {len(soon_users)-20} ta")
        
        await m.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cmd_expiring: {e}")
        await m.answer("Xatolik yuz berdi.")

@dp.message(Command("groups"))
async def cmd_groups(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    if not GROUP_IDS:
        return await m.answer("PRIVATE_GROUP_ID bo'sh. Secrets'ga kiriting.")
    rows = await resolve_group_titles()
    txt = "🔗 Ulangan guruhlar:\n" + "\n".join([f"• {t} — {gid}" for gid, t in rows])
    await m.answer(txt)

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}\nAdmin IDs: {ADMIN_IDS}")
    if not GROUP_IDS:
        return await m.answer("⚙️ PRIVATE_GROUP_ID bo'sh. Secrets'ga guruh ID'larini kiriting.")
    
    now = int(datetime.utcnow().timestamp())
    
    # Barcha guruhlardagi unique userlarni yig'amiz
    all_users = {}
    for gid in GROUP_IDS:
        members = await all_members_of_group(gid)
        for uid, username, full_name, exp, phone in members:
            if uid not in all_users or (all_users[uid] or 0) < (exp or 0):
                all_users[uid] = exp
    
    # Statistika hisoblash
    total = len(all_users)
    active = sum(1 for exp in all_users.values() if exp and exp > now)
    expired = sum(1 for exp in all_users.values() if exp and 0 < exp <= now)
    
    header = (
        "📊 Statistika (faqat guruhdagilar)\n"
        f"— Jami: {total}\n"
        f"— Aktiv: {active}\n"
        f"— Muddati tugagan: {expired}\n\n"
        "📚 Guruhlar kesimi:"
    )
    await m.answer(header)
    
    titles = dict(await resolve_group_titles())
    for gid in GROUP_IDS:
        users = await all_members_of_group(gid)
        # Faqat aktiv obunali foydalanuvchilarni qoldirish
        active_users = [(uid, username, full_name, exp, phone) 
                        for uid, username, full_name, exp, phone in users 
                        if exp and exp > now]
        
        # Telegram API orqali guruhda turganlarni tekshirish
        real_members = []
        for uid, username, full_name, exp, phone in active_users:
            try:
                member = await bot.get_chat_member(gid, uid)
                if member.status in ["member", "administrator", "creator"]:
                    real_members.append((uid, username, full_name, exp, phone))
            except Exception:
                # Agar user topilmasa yoki xato bo'lsa, o'tkazib yuboramiz
                pass
        
        title = titles.get(gid, str(gid))
        if not real_members:
            await m.answer(f"🏷 {title} — 0 a'zo")
            continue
        
        lines = [f"🏷 {title} — {len(real_members)} a'zo"]
        now_loc_date = (datetime.utcnow() + TZ_OFFSET).date()
        MAX_SHOW = 40
        users_sorted = sorted(real_members, key=lambda r: (r[3] or 0), reverse=True)
        for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted[:MAX_SHOW], start=1):
            tag = f"@{username}" if username else (full_name or uid)
            phone_s = f" 📞 {phone}" if phone else ""
            exp_str, left = human_left(exp)
            state = "✅" if (datetime.utcfromtimestamp(exp) + TZ_OFFSET).date() >= now_loc_date else "⚠️"
            lines.append(f"{i}. {tag}{phone_s} — {state} {exp_str} (qoldi: {max(left,0)} kun)")
        if len(users_sorted) > MAX_SHOW:
            lines.append(f"... va yana {len(users_sorted)-MAX_SHOW} ta")
        
        await m.answer("\n".join(lines))

@dp.message(Command("gstats"))
async def cmd_gstats(m: Message):
    """Batafsil guruh statistikasi: foydalanuvchi, telefon, tugash sanasi."""
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}\nAdmin IDs: {ADMIN_IDS}")
    
    if not GROUP_IDS:
        return await m.answer("⚙️ PRIVATE_GROUP_ID bo'sh. Secrets'ga guruh ID'larini kiriting.")
    
    try:
        titles = dict(await resolve_group_titles())
        total_groups = len(GROUP_IDS)
        
        await m.answer(f"📊 *Guruhlar statistikasi*\n\n🏫 Jami guruhlar: {total_groups}\n", parse_mode="Markdown")
        
        for idx, gid in enumerate(GROUP_IDS, start=1):
            users = await all_members_of_group(gid)
            title = titles.get(gid, f"Guruh {gid}")
            
            if not users:
                await m.answer(f"🏷 {idx}. *{title}*\nID: `{gid}`\n👥 A'zolar: 0", parse_mode="Markdown")
                continue
            
            header = f"🏷 {idx}. *{title}*\nID: `{gid}`\n👥 A'zolar: {len(users)}\n{'─' * 30}"
            buf = [header]
            
            users_sorted = sorted(users, key=lambda r: (r[3] or 0), reverse=True)
            
            for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted, start=1):
                name = full_name or f"User{uid}"
                username_s = f"@{username}" if username else "username yo'q"
                exp_str, left = human_left(exp) if exp else ("belgilanmagan", 0)
                phone_s = phone or "-"
                
                user_line = (
                    f"{i}. 👤 {name}\n"
                    f"   • Username: {username_s}\n"
                    f"   • ID: `{uid}`\n"
                    f"   • Telefon: {phone_s}\n"
                    f"   • Obuna: {exp_str} ({left} kun qoldi)"
                )
                buf.append(user_line)
            
            message = "\n\n".join(buf)
            
            if len(message) > 4000:
                parts = []
                current_part = header
                for line in buf[1:]:
                    if len(current_part) + len(line) + 2 > 4000:
                        parts.append(current_part)
                        current_part = line
                    else:
                        current_part += "\n\n" + line
                if current_part:
                    parts.append(current_part)
                
                for part in parts:
                    await m.answer(part, parse_mode="Markdown")
            else:
                await m.answer(message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cmd_gstats: {e}")
        await m.answer(f"Xatolik yuz berdi: {e}")

@dp.message(F.text == "📊 Statistika")
async def admin_stats_button(m: Message):
    """Admin Statistika tugmasi handleri."""
    if not is_admin(m.from_user.id):
        return
    
    if not GROUP_IDS:
        await m.answer("⚙️ PRIVATE_GROUP_ID bo'sh. Secrets'ga guruh ID'larini kiriting.")
        return
    
    now = int(datetime.utcnow().timestamp())
    
    # Barcha guruhlardagi unique userlarni yig'amiz
    all_users = {}
    for gid in GROUP_IDS:
        members = await all_members_of_group(gid)
        for uid, username, full_name, exp, phone in members:
            if uid not in all_users or (all_users[uid] or 0) < (exp or 0):
                all_users[uid] = exp
    
    # Statistika hisoblash
    total = len(all_users)
    active = sum(1 for exp in all_users.values() if exp and exp > now)
    expired = sum(1 for exp in all_users.values() if exp and 0 < exp <= now)
    
    header = (
        "📊 Statistika (faqat guruhdagilar)\n"
        f"— Jami: {total}\n"
        f"— Aktiv: {active}\n"
        f"— Muddati tugagan: {expired}\n\n"
        "📚 Guruhlar kesimi:"
    )
    await m.answer(header)
    
    titles = dict(await resolve_group_titles())
    for gid in GROUP_IDS:
        users = await all_members_of_group(gid)
        # Faqat aktiv obunali foydalanuvchilarni qoldirish
        active_users = [(uid, username, full_name, exp, phone) 
                        for uid, username, full_name, exp, phone in users 
                        if exp and exp > now]
        
        # Telegram API orqali guruhda turganlarni tekshirish
        real_members = []
        for uid, username, full_name, exp, phone in active_users:
            try:
                member = await bot.get_chat_member(gid, uid)
                if member.status in ["member", "administrator", "creator"]:
                    real_members.append((uid, username, full_name, exp, phone))
            except Exception:
                pass
        
        title = titles.get(gid, str(gid))
        if not real_members:
            await m.answer(f"🏷 {title} — 0 a'zo")
            continue
        
        lines = [f"🏷 {title} — {len(real_members)} a'zo"]
        MAX_SHOW = 40
        users_sorted = sorted(real_members, key=lambda r: (r[3] or 0), reverse=True)
        for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted[:MAX_SHOW], start=1):
            left_str, _ = human_left(exp) if exp else ("—", 0)
            lines.append(f"{i}. {full_name or 'Nomsiz'} — {left_str}")
        
        if len(real_members) > MAX_SHOW:
            lines.append(f"... +{len(real_members) - MAX_SHOW} ta ko'proq")
        
        await m.answer("\n".join(lines))

@dp.message(F.text == "✅ Tasdiqlangan to'lovlar")
async def admin_approved_button(m: Message):
    """Admin Tasdiqlangan to'lovlar tugmasi handleri."""
    if not is_admin(m.from_user.id):
        return
    
    # Tanlash tugmalarini ko'rsatish
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Oxirgi 3 tasi", callback_data="approved_last3")],
        [InlineKeyboardButton(text="📚 Hammasi", callback_data="approved_all")]
    ])
    
    await m.answer("✅ *Tasdiqlangan to'lovlar*\n\nQaysi birini ko'rmoqchisiz?", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "approved_last3")
async def cb_approved_last3(c: CallbackQuery):
    """Oxirgi 3 ta tasdiqlangan to'lovni ko'rsatish."""
    await c.answer()
    
    try:
        approved_payments = await db_pool.fetch(
            "SELECT id, user_id, photo_file, admin_id, created_at FROM payments WHERE status = 'approved' ORDER BY id DESC LIMIT 3"
        )
        
        if not approved_payments:
            await c.message.edit_text("✅ Hozircha tasdiqlangan to'lovlar yo'q.")
            return
        
        await c.message.delete()
        
        titles = dict(await resolve_group_titles())
        
        for payment in approved_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            created_at = payment['created_at']
            
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            primary_group_id = user_row[3] if len(user_row) > 3 else None
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            expires_at = user_row[6] if len(user_row) > 6 else None
            
            # Guruhlarni olish (user_groups + primary group)
            groups_data = await db_pool.fetch(
                "SELECT group_id FROM user_groups WHERE user_id = $1", uid
            )
            group_ids = set()
            for row in groups_data:
                group_ids.add(row['group_id'])
            
            # Primary group ham qo'shamiz (agar mavjud bo'lsa)
            if primary_group_id:
                group_ids.add(primary_group_id)
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", uid)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            group_names = [titles.get(gid, str(gid)) for gid in group_ids]
            groups_str = ", ".join(group_names) if group_names else "yo'q"
            expiry_date = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d") if expires_at else "yo'q"
            payment_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M") if created_at else "yo'q"
            
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"✅ *Tasdiqlangan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"🏫 Guruhlar: {groups_str}\n"
                f"⏳ Obuna tugashi: {expiry_date}\n"
                f"📅 To'lov sanasi: {payment_date}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`"
            )
            
            await bot.send_photo(c.from_user.id, photo_file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cb_approved_last3: {e}")
        await c.message.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "approved_all")
async def cb_approved_all(c: CallbackQuery):
    """Barcha tasdiqlangan to'lovlarni ko'rsatish."""
    await c.answer()
    
    try:
        approved_payments = await db_pool.fetch(
            "SELECT id, user_id, photo_file, admin_id, created_at FROM payments WHERE status = 'approved' ORDER BY id DESC"
        )
        
        if not approved_payments:
            await c.message.edit_text("✅ Hozircha tasdiqlangan to'lovlar yo'q.")
            return
        
        await c.message.delete()
        
        titles = dict(await resolve_group_titles())
        
        for payment in approved_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            created_at = payment['created_at']
            
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            primary_group_id = user_row[3] if len(user_row) > 3 else None
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            expires_at = user_row[6] if len(user_row) > 6 else None
            
            # Guruhlarni olish (user_groups + primary group)
            groups_data = await db_pool.fetch(
                "SELECT group_id FROM user_groups WHERE user_id = $1", uid
            )
            group_ids = set()
            for row in groups_data:
                group_ids.add(row['group_id'])
            
            # Primary group ham qo'shamiz (agar mavjud bo'lsa)
            if primary_group_id:
                group_ids.add(primary_group_id)
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", uid)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            group_names = [titles.get(gid, str(gid)) for gid in group_ids]
            groups_str = ", ".join(group_names) if group_names else "yo'q"
            expiry_date = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d") if expires_at else "yo'q"
            payment_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M") if created_at else "yo'q"
            
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"✅ *Tasdiqlangan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"🏫 Guruhlar: {groups_str}\n"
                f"⏳ Obuna tugashi: {expiry_date}\n"
                f"📅 To'lov sanasi: {payment_date}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`"
            )
            
            await bot.send_photo(c.from_user.id, photo_file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cb_approved_all: {e}")
        await c.message.answer("Xatolik yuz berdi")

@dp.message(F.text == "⏳ Kutilayotgan to'lovlar")
async def admin_pending_button(m: Message):
    """Admin Kutilayotgan to'lovlar tugmasi handleri."""
    if not is_admin(m.from_user.id):
        return
    
    try:
        # Kutilayotgan to'lovlarni olish
        pending_payments = await db_pool.fetch(
            "SELECT id, user_id, photo_file FROM payments WHERE status = 'pending' ORDER BY id ASC"
        )
        
        if not pending_payments:
            await m.answer("⏳ Kutilayotgan to'lovlar mavjud emas.")
            return
        
        # Har bir to'lov uchun ma'lumot yuborish
        for payment in pending_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            
            # User ma'lumotlarini olish
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", uid)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            # Shartnoma ma'lumotlarini olish (agar bor bo'lsa)
            agreed_at = user_row[4] if len(user_row) > 4 else None
            # agreed_at ni int ga convert qilamiz (agar str bo'lsa)
            if agreed_at and isinstance(agreed_at, str):
                try:
                    agreed_at = int(agreed_at)
                except ValueError:
                    agreed_at = None
            contract_date = (datetime.utcfromtimestamp(agreed_at) + TZ_OFFSET).strftime("%Y-%m-%d") if agreed_at and isinstance(agreed_at, int) else "yo'q"
            
            kb = approve_keyboard(pid)
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"⏳ *Kutilayotgan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"📄 Shartnoma: {contract_date}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`"
            )
            
            await m.answer_photo(photo_file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_pending_button: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(F.text == "🧹 Tozalash")
async def admin_cleanup_button(m: Message):
    """Admin chatni to'liq tozalash tugmasi."""
    if not is_admin(m.from_user.id):
        return
    
    try:
        # Oxirgi 300 ta xabarni o'chirishga harakat qilamiz (to'liq tozalash)
        current_msg_id = m.message_id
        deleted_count = 0
        
        # Orqaga qarab 300 ta xabarni o'chiramiz
        for i in range(1, 301):
            try:
                await bot.delete_message(m.from_user.id, current_msg_id - i)
                deleted_count += 1
            except Exception:
                # Agar xabar topilmasa yoki o'chirib bo'lmasa, davom etamiz
                pass
        
        # Natija xabarini yuboramiz va 3 sekunddan keyin o'chiramiz
        result_msg = await m.answer(
            f"🧹 *Chat to'liq tozalandi!*\n\n✅ {deleted_count} ta xabar o'chirildi.", 
            parse_mode="Markdown"
        )
        await asyncio.sleep(3)
        await result_msg.delete()
        await m.delete()  # Tozalash buyrug'ini ham o'chiramiz
        
        # Admin tugmalarini qayta yuborish
        await bot.send_message(
            m.from_user.id,
            "👨‍💼 *ADMIN PANEL*",
            reply_markup=admin_reply_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in admin_cleanup_button: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.message(F.text == "📎 Guruh linklari")
async def admin_group_links_button(m: Message):
    """Admin guruh linklari yaratish tugmasi - ko'p guruh tanlash."""
    if not is_admin(m.from_user.id):
        return
    
    try:
        titles = dict(await resolve_group_titles())
        if not titles:
            return await m.answer("❗ Guruhlar topilmadi. .env faylida PRIVATE_GROUP_ID ni tekshiring.")
        
        # Multi-select uchun state yaratish
        MULTI_PICK_LINKS[m.from_user.id] = {"selected": set()}
        
        # Checkbox keyboard yaratish
        keyboard = []
        for gid, title in titles.items():
            keyboard.append([InlineKeyboardButton(
                text=f"☐ {title}",
                callback_data=f"toggle_link:{gid}"
            )])
        keyboard.append([InlineKeyboardButton(
            text="✅ Davom etish",
            callback_data="confirm_link_groups"
        )])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await m.answer(
            "📎 *Guruh linklari yaratish*\n\n"
            "Qaysi guruh(lar) uchun link yaratmoqchisiz?\n"
            "Bir nechta guruhni tanlashingiz mumkin.\n\n"
            "Link *1 martalik* va muddatli bo'ladi.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in admin_group_links_button: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(F.text)
async def on_admin_date_handler(m: Message):
    # Sana kiritish (to'lov tasdiqlash uchun)
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
                
                full_name = (m.from_user.first_name or "") + (" " + (m.from_user.last_name or "") if m.from_user.last_name else "")
                full_name = full_name.strip() or f"User{m.from_user.id}"
                await update_user_fullname(m.from_user.id, full_name)
                
                txt_buf, pdf_buf = build_contract_files(full_name, phone)
                try:
                    await bot.send_document(m.from_user.id, BufferedInputFile(txt_buf.getvalue(), filename="shartnoma.txt"))
                    if pdf_buf:
                        await bot.send_document(m.from_user.id, BufferedInputFile(pdf_buf.getvalue(), filename="shartnoma.pdf"))
                    logger.info(f"Contract documents sent to user {m.from_user.id}")
                except Exception as e:
                    logger.error(f"Failed to send contract documents to user: {e}")
                
                # Shartnoma admin'ga yuborilmaydi (faqat to'lov cheki yetarli)
                logger.info(f"Contract generated for user {m.from_user.id}, not sent to admins")
                
                await m.answer("✅ Telefon raqam qabul qilindi. Endi to'lov turini tanlang:", reply_markup=start_keyboard())
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
        if not full_name:
            full_name = f"User{m.from_user.id}"
        await update_user_fullname(m.from_user.id, full_name)
        
        txt_buf, pdf_buf = build_contract_files(full_name, phone)
        try:
            await bot.send_document(m.from_user.id, BufferedInputFile(txt_buf.getvalue(), filename="shartnoma.txt"))
            if pdf_buf:
                await bot.send_document(m.from_user.id, BufferedInputFile(pdf_buf.getvalue(), filename="shartnoma.pdf"))
            logger.info(f"Contract documents sent to user {m.from_user.id}")
        except Exception as e:
            logger.error(f"Failed to send contract documents to user: {e}")
        
        # Shartnoma admin'ga yuborilmaydi (faqat to'lov cheki yetarli)
        logger.info(f"Contract generated for user {m.from_user.id}, not sent to admins")
        
        await m.answer("✅ Telefon raqam qabul qilindi. Endi to'lov turini tanlang:", reply_markup=start_keyboard())
    except Exception as e:
        logger.error(f"Error in on_contact: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")


@dp.callback_query(F.data == "pay_card")
async def cb_pay_card(c: CallbackQuery):
    await c.message.answer("💳 Karta raqami:\n9860160130847827 H.Halikova\n\nTo'lovdan so'ng chekni shu chatga yuboring.")
    await c.answer()

@dp.callback_query(F.data == "pay_link")
async def cb_pay_link(c: CallbackQuery):
    await c.message.answer(
        "🔗 To'lov havolasi\n"
        "PAYME ORQALI: https://payme.uz/fallback/merchant/?id=68aebaff42ec20bb02a46c8c\n\n"
        "CLICK ORQALI: https://indoor.click.uz/pay?id=081968&t=0\n\n"
        "To'lovdan so'ng chekni shu chatga yuboring."
    )
    await c.answer()

@dp.message(F.photo)
async def on_photo(m: Message):
    try:
        pid = await add_payment(m, m.photo[-1].file_id)
        await m.answer("✅ Chekingiz qabul qilindi. Admin tekshiradi.")
        
        # User ma'lumotlarini olish
        user_row = await get_user(m.from_user.id)
        phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
        
        # Kurs nomini olish
        async with db_pool.acquire() as conn:
            course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", m.from_user.id)
        course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
        
        # Telegram'dan profil nomini olish (har doim yangi)
        username, full_name = await fetch_user_profile(m.from_user.id)
        # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
        chat_link = f"📧 [{username}](tg://user?id={m.from_user.id})" if username else f"📧 [Chat ochish](tg://user?id={m.from_user.id})"
        
        kb = approve_keyboard(pid)
        caption = (
            f"🧾 *Yangi to'lov cheki*\n\n"
            f"👤 {full_name}\n"
            f"{chat_link}\n"
            f"📱 Telefon: {phone}\n"
            f"📚 Kurs: {course_name}\n"
            f"🆔 ID: `{m.from_user.id}`\n"
            f"💳 Payment ID: `{pid}`\n"
            f"📅 Vaqt: {(datetime.utcnow() + TZ_OFFSET).strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Admin xabarlarini kuzatish uchun
        if pid not in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid] = []
        
        for aid in ADMIN_IDS:
            try:
                msg = await bot.send_photo(aid, m.photo[-1].file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
                ADMIN_MESSAGES[pid].append(msg.message_id)
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
        _pid, _uid, _status, _ = row
        if _status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        if not GROUP_IDS:
            return await c.answer("ENV: PRIVATE_GROUP_ID bo'sh. Guruh chat_id larini kiriting.", show_alert=True)
        msg = await c.message.answer("🧭 Qanday qo'shamiz?", reply_markup=multi_select_entry_kb(pid, with_date_iso=None))
        if pid in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid].append(msg.message_id)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_approve_now: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(c: CallbackQuery):
    """Admin Statistika tugmasi handleri."""
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    if not GROUP_IDS:
        await c.message.answer("⚙️ PRIVATE_GROUP_ID bo'sh. Secrets'ga guruh ID'larini kiriting.")
        return await c.answer()
    
    now = int(datetime.utcnow().timestamp())
    
    # Barcha guruhlardagi unique userlarni yig'amiz
    all_users = {}
    for gid in GROUP_IDS:
        members = await all_members_of_group(gid)
        for uid, username, full_name, exp, phone in members:
            if uid not in all_users or (all_users[uid] or 0) < (exp or 0):
                all_users[uid] = exp
    
    # Statistika hisoblash
    total = len(all_users)
    active = sum(1 for exp in all_users.values() if exp and exp > now)
    expired = sum(1 for exp in all_users.values() if exp and 0 < exp <= now)
    
    header = (
        "📊 Statistika (faqat guruhdagilar)\n"
        f"— Jami: {total}\n"
        f"— Aktiv: {active}\n"
        f"— Muddati tugagan: {expired}\n\n"
        "📚 Guruhlar kesimi:"
    )
    await c.message.answer(header)
    
    titles = dict(await resolve_group_titles())
    for gid in GROUP_IDS:
        users = await all_members_of_group(gid)
        # Faqat aktiv obunali foydalanuvchilarni qoldirish
        active_users = [(uid, username, full_name, exp, phone) 
                        for uid, username, full_name, exp, phone in users 
                        if exp and exp > now]
        
        # Telegram API orqali guruhda turganlarni tekshirish
        real_members = []
        for uid, username, full_name, exp, phone in active_users:
            try:
                member = await bot.get_chat_member(gid, uid)
                if member.status in ["member", "administrator", "creator"]:
                    real_members.append((uid, username, full_name, exp, phone))
            except Exception:
                pass
        
        title = titles.get(gid, str(gid))
        if not real_members:
            await c.message.answer(f"🏷 {title} — 0 a'zo")
            continue
        
        lines = [f"🏷 {title} — {len(real_members)} a'zo"]
        MAX_SHOW = 40
        users_sorted = sorted(real_members, key=lambda r: (r[3] or 0), reverse=True)
        for i, (uid, username, full_name, exp, phone) in enumerate(users_sorted[:MAX_SHOW], start=1):
            left_str, _ = human_left(exp) if exp else ("—", 0)
            lines.append(f"{i}. {full_name or 'Nomsiz'} — {left_str}")
        
        if len(real_members) > MAX_SHOW:
            lines.append(f"... +{len(real_members) - MAX_SHOW} ta ko'proq")
        
        await c.message.answer("\n".join(lines))
    
    await c.answer()

@dp.callback_query(F.data == "admin_payments_approved")
async def cb_admin_payments_approved(c: CallbackQuery):
    """Admin Tasdiqlangan to'lovlar tugmasi handleri."""
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        # Tasdiqlangan to'lovlarni olish
        approved_payments = await db_pool.fetch(
            "SELECT id, user_id, photo_file, admin_id, created_at FROM payments WHERE status = 'approved' ORDER BY id DESC LIMIT 50"
        )
        
        if not approved_payments:
            await c.message.answer("✅ Hozircha tasdiqlangan to'lovlar yo'q.")
            return await c.answer()
        
        titles = dict(await resolve_group_titles())
        
        # Har bir to'lov uchun ma'lumot yuborish
        for payment in approved_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            admin_id = payment['admin_id']
            created_at = payment['created_at']
            
            # User ma'lumotlarini olish
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            group_id = user_row[3] if len(user_row) > 3 else None
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            expires_at = user_row[6] if len(user_row) > 6 else None
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", uid)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            # Guruh nomini olish
            group_name = titles.get(group_id, str(group_id)) if group_id else "yo'q"
            
            # Obuna tugash sanasi
            expiry_date = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d") if expires_at else "yo'q"
            
            # To'lov sanasi
            payment_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M") if created_at else "yo'q"
            
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"✅ *Tasdiqlangan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"🏫 Guruh: {group_name}\n"
                f"⏳ Obuna tugashi: {expiry_date}\n"
                f"📅 To'lov sanasi: {payment_date}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`"
            )
            
            await c.message.answer_photo(photo_file_id, caption=caption, parse_mode="Markdown")
        
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_admin_payments_approved: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "admin_payments_pending")
async def cb_admin_payments_pending(c: CallbackQuery):
    """Admin Kutilayotgan to'lovlar tugmasi handleri."""
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        # Kutilayotgan to'lovlarni olish
        pending_payments = await db_pool.fetch(
            "SELECT id, user_id, photo_file FROM payments WHERE status = 'pending' ORDER BY id ASC"
        )
        
        if not pending_payments:
            await c.message.answer("⏳ Hozirda kutilayotgan to'lovlar yo'q.")
            return await c.answer()
        
        # Har bir to'lov uchun ma'lumot yuborish
        for payment in pending_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            
            # User ma'lumotlarini olish
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", uid)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            # Shartnoma ma'lumotlarini olish (agar bor bo'lsa)
            agreed_at = user_row[4] if len(user_row) > 4 else None
            # agreed_at ni int ga convert qilamiz (agar str bo'lsa)
            if agreed_at and isinstance(agreed_at, str):
                try:
                    agreed_at = int(agreed_at)
                except ValueError:
                    agreed_at = None
            contract_date = (datetime.utcfromtimestamp(agreed_at) + TZ_OFFSET).strftime("%Y-%m-%d") if agreed_at and isinstance(agreed_at, int) else "yo'q"
            
            kb = approve_keyboard(pid)
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"⏳ *Kutilayotgan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"📄 Shartnoma: {contract_date}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`"
            )
            
            await c.message.answer_photo(photo_file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
        
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_admin_payments_pending: {e}")
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
        _pid, _uid, _status, _ = row
        if _status == "approved":
            return await c.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        WAIT_DATE_FOR[c.from_user.id] = pid
        msg = await c.message.answer("🗓 Boshlanish sanasini kiriting: YYYY-MM-DD (masalan 2025-10-01)")
        if pid in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid].append(msg.message_id)
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
        msg = await c.message.answer("🧭 Bitta guruhni tanlang:", reply_markup=kb)
        if pid in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid].append(msg.message_id)
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
        msg = await c.message.answer("🧭 Bir necha guruhni tanlang (✅ belgilab, so'ng Tasdiqlash):", reply_markup=kb)
        if pid in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid].append(msg.message_id)
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
        msg = await c.message.answer("✅ Yangilandi. Davom eting:", reply_markup=kb)
        if pid in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid].append(msg.message_id)
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
        _pid, user_id, status, photo_file_id = row
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
        
        # User'ga linklar yuborish
        try:
            await bot.send_message(
                user_id,
                "✅ *To'lovingiz tasdiqlandi!*\n\n"
                f"📚 Quyidagi guruhlarga kirish havolalari (har biri *1 martalik* bo'lib, boshqalarga ulashmang):\n\n"
                + "\n".join(links_out) +
                f"\n\n💡 *Eslatma:* Bu guruhga kirish linki bo'lib, guruhga kirgach siz doimiy *OBUNA REJANGIZGA* ko'ra foydalanasiz.\n\n"
                f"⏳ Obuna tugash sanasi: *{human_exp}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to send approval message to user {user_id}: {e}")
        
        # Barcha admin xabarlarni o'chirish
        if pid in ADMIN_MESSAGES:
            for msg_id in ADMIN_MESSAGES[pid]:
                try:
                    await bot.delete_message(c.from_user.id, msg_id)
                except Exception as e:
                    logger.warning(f"Failed to delete admin message {msg_id}: {e}")
            del ADMIN_MESSAGES[pid]
        
        # Yakuniy xulosa yuborish (chek rasmi bilan)
        try:
            group_names = ", ".join([titles.get(g, str(g)) for g in selected])
            user_row = await get_user(user_id)
            phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={user_id})" if username else f"📧 [Chat ochish](tg://user?id={user_id})"
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", user_id)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            final_caption = (
                f"✅ *HAVOLALAR YUBORILDI*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"🏫 Guruhlar: {group_names}\n"
                f"⏳ Tugash: {human_exp}"
            )
            final_msg = await bot.send_photo(c.from_user.id, photo_file_id, caption=final_caption, parse_mode="Markdown")
            
            # 10 sekunddan keyin yakuniy xulosa xabarini o'chirish
            async def delete_after_delay():
                await asyncio.sleep(10)
                try:
                    await bot.delete_message(c.from_user.id, final_msg.message_id)
                except Exception as e:
                    logger.warning(f"Failed to delete final summary message: {e}")
            
            asyncio.create_task(delete_after_delay())
        except Exception as e:
            logger.warning(f"Failed to send final summary: {e}")
        
        MULTI_PICK.pop(c.from_user.id, None)
        await c.answer("✅ Havolalar yuborildi, barcha xabarlar tozalandi")
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
        _pid, user_id, status, photo_file_id = row
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
        
        # Guruh nomini olish
        titles = dict(await resolve_group_titles())
        group_name = titles.get(gid, str(gid))
        
        try:
            link = await send_one_time_link(gid, user_id)
        except Exception as e:
            await c.message.answer(f"Link yaratishda xato: {e}")
            return await c.answer()
        
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # User'ga link yuborish
        try:
            await bot.send_message(
                user_id,
                "✅ *To'lovingiz tasdiqlandi!*\n\n"
                f"📚 Guruhga kirish havolasi (*1 martalik* bo'lib, boshqalarga ulashmang):\n\n"
                f"• {group_name}: {link}\n\n"
                f"💡 *Eslatma:* Bu guruhga kirish linki bo'lib, guruhga kirgach siz doimiy *OBUNA REJANGIZGA* ko'ra foydalanasiz.\n\n"
                f"⏳ Obuna tugash sanasi: *{human_exp}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to send approval message to user {user_id}: {e}")
        
        # Barcha admin xabarlarni o'chirish
        if pid in ADMIN_MESSAGES:
            for msg_id in ADMIN_MESSAGES[pid]:
                try:
                    await bot.delete_message(c.from_user.id, msg_id)
                except Exception as e:
                    logger.warning(f"Failed to delete admin message {msg_id}: {e}")
            del ADMIN_MESSAGES[pid]
        
        # Yakuniy xulosa yuborish (chek rasmi bilan)
        try:
            user_row = await get_user(user_id)
            phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={user_id})" if username else f"📧 [Chat ochish](tg://user?id={user_id})"
            
            # Kurs nomini olish
            async with db_pool.acquire() as conn:
                course_row = await conn.fetchrow("SELECT course_name FROM users WHERE user_id = $1", user_id)
            course_name = course_row['course_name'] if course_row and course_row.get('course_name') else "Kiritilmagan"
            
            final_caption = (
                f"✅ *HAVOLA YUBORILDI*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"📚 Kurs: {course_name}\n"
                f"🏫 Guruh: {group_name}\n"
                f"⏳ Tugash: {human_exp}"
            )
            final_msg = await bot.send_photo(c.from_user.id, photo_file_id, caption=final_caption, parse_mode="Markdown")
            
            # 10 sekunddan keyin yakuniy xulosa xabarini o'chirish
            async def delete_after_delay():
                await asyncio.sleep(10)
                try:
                    await bot.delete_message(c.from_user.id, final_msg.message_id)
                except Exception as e:
                    logger.warning(f"Failed to delete final summary message: {e}")
            
            asyncio.create_task(delete_after_delay())
        except Exception as e:
            logger.warning(f"Failed to send final summary: {e}")
        
        await c.answer("✅ Havola yuborildi, barcha xabarlar tozalandi")
    except Exception as e:
        logger.error(f"Error in cb_pick_group: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

# State for multi-group link creation
MULTI_PICK_LINKS: dict[int, dict] = {}  # admin_id -> {"selected": set(), "user_id": int}

@dp.callback_query(F.data.startswith("toggle_link:"))
async def cb_toggle_link_group(c: CallbackQuery):
    """Guruhni tanlash/bekor qilish (checkbox)."""
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        gid = int(c.data.split(":")[1])
        state = MULTI_PICK_LINKS.get(c.from_user.id)
        if not state:
            return await c.answer("Sessiya topilmadi. Qaytadan boshlang.", show_alert=True)
        
        selected: set = state.get("selected", set())
        if gid in selected:
            selected.remove(gid)
        else:
            selected.add(gid)
        state["selected"] = selected
        
        # Keyboard yangilash
        titles = dict(await resolve_group_titles())
        keyboard = []
        for g, title in titles.items():
            check = "☑" if g in selected else "☐"
            keyboard.append([InlineKeyboardButton(
                text=f"{check} {title}",
                callback_data=f"toggle_link:{g}"
            )])
        keyboard.append([InlineKeyboardButton(
            text="✅ Davom etish",
            callback_data="confirm_link_groups"
        )])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await c.message.edit_reply_markup(reply_markup=kb)
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_toggle_link_group: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "confirm_link_groups")
async def cb_confirm_link_groups(c: CallbackQuery):
    """Tanlangan guruhlar uchun avtomatik linklar yaratish."""
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        state = MULTI_PICK_LINKS.get(c.from_user.id)
        if not state:
            return await c.answer("Sessiya topilmadi.", show_alert=True)
        
        selected: set = state.get("selected", set())
        if not selected:
            return await c.answer("Hech bo'lmaganda bitta guruhni tanlang.", show_alert=True)
        
        # Barcha tanlangan guruhlar uchun linklar yaratish (user ID kerak emas)
        titles = dict(await resolve_group_titles())
        links_out = []
        
        # Unique link nomi uchun timestamp ishlatamiz
        import time
        link_id = int(time.time())
        
        for gid in selected:
            group_title = titles.get(gid, str(gid))
            try:
                link = await send_one_time_link(gid, link_id)
                links_out.append(f"• {group_title}: {link}")
            except Exception as e:
                logger.error(f"Failed to create link for group {gid}: {e}")
                links_out.append(f"• {group_title}: ❌ Xatolik - {str(e)}")
        
        # Admin'ga linklar ko'rsatish
        await c.message.edit_text(
            f"✅ *Linklar yaratildi!*\n\n"
            f"🔗 Linklar:\n" + "\n".join(links_out) + f"\n\n"
            f"🎫 Har biri *1 martalik*\n\n"
            f"💡 Linkni o'quvchiga o'zingiz ulashing.",
            parse_mode="Markdown"
        )
        
        # State tozalash
        MULTI_PICK_LINKS.pop(c.from_user.id, None)
        await c.answer("✅ Linklar tayyor!")
        
    except Exception as e:
        logger.error(f"Error in cb_confirm_link_groups: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("reject:"))
async def cb_reject(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        pid = int(c.data.split(":")[1])
        row = await get_payment(pid)
        if row:
            _pid, user_id, _status, _ = row
            user_row = await get_user(user_id)
            username, full_name = await fetch_user_profile(user_id)
            phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
            
            await set_payment_status(pid, "rejected", c.from_user.id)
            
            # Admin chek xabarini yangilash
            try:
                # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
                chat_link = f"📧 [{username}](tg://user?id={user_id})" if username else f"📧 [Chat ochish](tg://user?id={user_id})"
                new_caption = (
                    f"❌ *RAD ETILDI*\n\n"
                    f"👤 {full_name}\n"
                    f"{chat_link}\n"
                    f"📱 Telefon: {phone}"
                )
                await c.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Failed to edit admin message: {e}")
            
            await c.answer("❌ To'lov rad etildi")
        else:
            await c.answer("Payment topilmadi", show_alert=True)
    except Exception as e:
        logger.error(f"Error in cb_reject: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

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
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        key = (uid, gid)
        count = NOT_PAID_COUNTER.get(key, 0) + 1
        NOT_PAID_COUNTER[key] = count
        
        if count >= 3:
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
                NOT_PAID_COUNTER.pop(key, None)
                await c.message.answer(f"❌ {uid} 3 marta to'lov qilmagan. Guruhdan chiqarildi.")
                try:
                    await bot.send_message(uid, "❌ 3 marta to'lov qilmaganingiz sababli guruhdan chiqarildingiz.")
                except Exception as e:
                    logger.warning(f"Failed to notify kicked user {uid}: {e}")
            except Exception as e:
                await c.message.answer(f"Chiqarishda xato: {e}")
            await c.answer("Guruhdan chiqarildi")
        else:
            await c.message.answer(f"⌛ Foydalanuvchi {uid} hali to'lov qilmagan deb qayd etildi. ({count}/3)")
            await c.answer(f"Qayd etildi ({count}/3)")
    except Exception as e:
        logger.error(f"Error in cb_warn_notpaid: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

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
    try:
        await dp.start_polling(bot)
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Database connection pool closed")

if __name__ == "__main__":
    asyncio.run(main())
