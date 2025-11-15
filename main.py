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
    Message, CallbackQuery, ChatMemberUpdated,
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

# Tarif konfiguratsiyasi
TARIFFS = {
    "demo": {
        "name": "🎁 Demo",
        "days": 7,
        "max_groups": 1,
        "price": 0,
        "description": "1 hafta, 1 ta guruh, BEPUL"
    },
    "oddiy": {
        "name": "📦 Oddiy",
        "days": 30,
        "max_groups": 2,
        "price": 50000,
        "description": "1 oy, 2 ta guruh"
    },
    "pro": {
        "name": "🚀 Pro",
        "days": 30,
        "max_groups": 4,
        "price": 75000,
        "description": "1 oy, 4 ta guruh"
    },
    "gold": {
        "name": "💎 GOLD",
        "days": 30,
        "max_groups": 5,
        "price": 100000,
        "description": "1 oy, 5 ta guruh"
    },
    "premium": {
        "name": "👑 Premium",
        "days": 30,
        "max_groups": -1,  # -1 = cheksiz
        "price": 150000,
        "description": "1 oy, cheksiz guruh"
    }
}

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
WAIT_CONTRACT_CONFIRM: set[int] = set()
WAIT_CONTRACT_EDIT: set[int] = set()
WAIT_PAYMENT_EDIT: set[int] = set()
WAIT_PAYMENT_PHOTO: set[int] = set()
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
CREATE TABLE IF NOT EXISTS contract_templates(
    id SERIAL PRIMARY KEY,
    template_text TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS groups(
    id SERIAL PRIMARY KEY,
    group_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS admins(
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'admin',
    active BOOLEAN DEFAULT TRUE,
    created_at BIGINT NOT NULL,
    expires_at BIGINT,
    created_by BIGINT,
    managed_groups BIGINT[],
    max_groups INTEGER DEFAULT -1,
    tariff TEXT,
    last_warning_sent_at BIGINT
);
CREATE TABLE IF NOT EXISTS payment_settings(
    id SERIAL PRIMARY KEY,
    bank_name TEXT NOT NULL,
    card_number TEXT NOT NULL,
    amount TEXT NOT NULL,
    additional_info TEXT,
    updated_at BIGINT NOT NULL,
    updated_by BIGINT
);
CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id);
CREATE INDEX IF NOT EXISTS idx_users_expires ON users(expires_at);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_pay_status_created ON payments(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ug_user ON user_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_ug_group ON user_groups(group_id);
CREATE INDEX IF NOT EXISTS idx_ug_expires ON user_groups(expires_at);
CREATE INDEX IF NOT EXISTS idx_admins_user ON admins(user_id);
CREATE INDEX IF NOT EXISTS idx_admins_active ON admins(active);
CREATE INDEX IF NOT EXISTS idx_admins_expires ON admins(expires_at);
"""

async def db_init():
    global db_pool, GROUP_IDS
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
            
            # Migration: admins jadvalidagi yangi ustunlarni qo'shish
            try:
                await conn.execute("""
                    ALTER TABLE admins ADD COLUMN IF NOT EXISTS max_groups INTEGER DEFAULT -1;
                """)
                logger.info("Migration: max_groups column added/verified")
            except Exception as me:
                logger.warning(f"Migration warning: {me}")
            
            try:
                await conn.execute("""
                    ALTER TABLE admins ADD COLUMN IF NOT EXISTS tariff TEXT;
                """)
                logger.info("Migration: tariff column added/verified")
            except Exception as me:
                logger.warning(f"Migration warning: {me}")
            
            try:
                await conn.execute("""
                    ALTER TABLE admins ADD COLUMN IF NOT EXISTS last_warning_sent_at BIGINT;
                """)
                logger.info("Migration: last_warning_sent_at column added/verified")
            except Exception as me:
                logger.warning(f"Migration warning: {me}")
            
            # Migration: groups jadvaliga 'type' ustuni qo'shish (group/channel farqlash uchun)
            try:
                await conn.execute("""
                    ALTER TABLE groups ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'group';
                """)
                logger.info("Migration: groups.type column added/verified")
            except Exception as me:
                logger.warning(f"Migration warning: {me}")
            
            # Default shartnoma matnini qo'shish (agar yo'q bo'lsa)
            count = await conn.fetchval("SELECT COUNT(*) FROM contract_templates")
            if count == 0:
                now = int(datetime.utcnow().timestamp())
                await conn.execute("""
                    INSERT INTO contract_templates(template_text, created_at, updated_at)
                    VALUES($1, $2, $3)
                """, CONTRACT_TEXT, now, now)
                logger.info("Default contract template inserted")
            
            # Auto-sync: Environment variable'dan yangi guruhlarni database'ga qo'shish
            # Database bo'sh bo'lmaganida ham yangi guruhlar qo'shiladi (faqat yangilari)
            if GROUP_IDS:
                now = int(datetime.utcnow().timestamp())
                synced_count = 0
                for idx, gid in enumerate(GROUP_IDS, start=1):
                    try:
                        # Har bir guruhni database'ga qo'shish (agar yo'q bo'lsa)
                        # ON CONFLICT DO NOTHING - mavjud guruhlarni o'zgartirmaydi
                        name = f"Guruh #{idx}" if len(GROUP_IDS) > 1 else "Asosiy guruh"
                        result = await conn.execute("""
                            INSERT INTO groups(group_id, name, created_at)
                            VALUES($1, $2, $3)
                            ON CONFLICT(group_id) DO NOTHING
                        """, gid, name, now)
                        synced_count += 1
                    except Exception as e:
                        logger.error(f"Failed to sync group {gid}: {e}")
                
                if synced_count > 0:
                    logger.info(f"Auto-synced {synced_count} group(s) from PRIVATE_GROUP_ID to database (new groups only)")
            
            # GROUP_IDS ni database'dan yuklash
            db_groups = await load_groups_from_db()
            if db_groups:
                GROUP_IDS = db_groups
                logger.info(f"Loaded {len(GROUP_IDS)} group(s) from database: {GROUP_IDS}")
            elif GROUP_IDS:
                # Agar database bo'sh bo'lsa lekin environment variable'da guruhlar bo'lsa, ularni saqlash
                logger.warning(f"Database has no groups, keeping {len(GROUP_IDS)} from environment variable")
            else:
                logger.warning("No groups found in database or environment - bot may not function properly")
                
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

async def get_contract_template() -> str:
    """Hozirgi shartnoma matnini olish."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT template_text FROM contract_templates ORDER BY id DESC LIMIT 1"
        )
        return row['template_text'] if row else CONTRACT_TEXT

async def update_contract_template(new_text: str):
    """Shartnoma matnini yangilash."""
    now = int(datetime.utcnow().timestamp())
    async with db_pool.acquire() as conn:
        # Yangi shartnoma matni qo'shish (tarixi saqlanadi)
        await conn.execute("""
            INSERT INTO contract_templates(template_text, created_at, updated_at)
            VALUES($1, $2, $3)
        """, new_text, now, now)

async def get_payment_settings():
    """To'lov ma'lumotlarini olish."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT bank_name, card_number, amount, additional_info FROM payment_settings ORDER BY id DESC LIMIT 1"
        )
        return row if row else None

async def update_payment_settings(bank_name: str, card_number: str, amount: str, additional_info: str, admin_id: int):
    """To'lov ma'lumotlarini yangilash."""
    now = int(datetime.utcnow().timestamp())
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO payment_settings(bank_name, card_number, amount, additional_info, updated_at, updated_by)
            VALUES($1, $2, $3, $4, $5, $6)
        """, bank_name, card_number, amount, additional_info, now, admin_id)

async def load_groups_from_db() -> list[int]:
    """Database'dan guruhlar ro'yxatini yuklash."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT group_id FROM groups ORDER BY id")
        return [row['group_id'] for row in rows]

async def add_group_to_db(group_id: int, name: Optional[str] = None, chat_type: str = 'group'):
    """Yangi guruh yoki kanal qo'shish."""
    now = int(datetime.utcnow().timestamp())
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO groups(group_id, name, created_at, type)
            VALUES($1, $2, $3, $4)
            ON CONFLICT(group_id) DO UPDATE SET name=EXCLUDED.name, type=EXCLUDED.type
        """, group_id, name, now, chat_type)

async def remove_group_from_db(group_id: int):
    """Guruhni o'chirish."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM groups WHERE group_id=$1", group_id)

async def get_all_groups():
    """Barcha guruhlarni olish (type bilan)."""
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT id, group_id, name, type, created_at FROM groups ORDER BY id")

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

async def resolve_group_titles(group_ids: Optional[list[int]] = None) -> list[tuple[int, str]]:
    """Guruh ID'larini nomlariga aylantirish.
    
    Priority: Database names > Telegram API > Group ID
    Auto-updates database if name is empty or default "Guruh #N"
    
    Args:
        group_ids: Agar berilsa, faqat shu guruhlar. Aks holda, barcha GROUP_IDS.
    """
    ids_to_resolve = group_ids if group_ids is not None else GROUP_IDS
    
    # 1. Database'dan barcha guruh nomlarini olish
    db_titles = {}
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT group_id, name FROM groups")
            for row in rows:
                # Faqat real nomlar, default "Guruh #N" emas
                if row['name'] and row['name'].strip() and not row['name'].startswith("Guruh #"):
                    db_titles[row['group_id']] = row['name']
    except Exception as e:
        logger.warning(f"Failed to fetch group names from database: {e}")
    
    # 2. Har bir guruh uchun nom aniqlash
    result = []
    for gid in ids_to_resolve:
        # Avval database'dan nom olish
        if gid in db_titles:
            title = db_titles[gid]
        else:
            # Database'da nom yo'q yoki default nom bo'lsa, Telegram API'dan olish
            try:
                chat = await bot.get_chat(gid)
                title = chat.title or str(gid)
                
                # Database'ni yangilash (agar nom topilsa)
                if title != str(gid):
                    try:
                        async with db_pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE groups SET name=$1 WHERE group_id=$2",
                                title, gid
                            )
                        logger.info(f"Updated group name in database: {gid} -> {title}")
                    except Exception as update_err:
                        logger.warning(f"Failed to update group name in database: {update_err}")
            except Exception as e:
                logger.warning(f"Failed to get title for group {gid}: {e}")
                title = str(gid)
        
        result.append((gid, title))
    return result

async def get_group_type(group_id: int) -> str:
    """Guruh yoki kanal turini database'dan olish."""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT type FROM groups WHERE group_id=$1", group_id)
            return row['type'] if row else 'group'
    except Exception:
        return 'group'  # Default

async def send_one_time_link(group_id: int, user_id: int) -> str:
    """24 soatlik bir martalik invite link yaratish (guruh/kanal uchun).
    
    Args:
        group_id: Guruh/Kanal ID
        user_id: User ID (link nomi uchun)
    
    Returns:
        24 soat amal qiladigan, 1 martalik link
    
    Note:
        member_limit=1 guruh VA kanal uchun ishlaydi (Telegram Bot API 5.1+)
    """
    expire_date = datetime.utcnow() + timedelta(hours=24)
    
    # Guruh ham, kanal ham uchun bir xil logika
    # member_limit=1 → faqat 1 kishi ishlatishi mumkin (bir martalik)
    # expire_date → 24 soatdan keyin link o'chadi
    link = await bot.create_chat_invite_link(
        chat_id=group_id,
        name=f"sub-{user_id}",
        member_limit=1,  # FAQAT 1 KISHI kirishi mumkin (guruh VA kanal uchun)
        expire_date=expire_date,  # 24 soatdan keyin amal qilmaydi
        creates_join_request=False  # Avtomatik kirish, admin tasdiq yo'q
    )
    
    return link.invite_link

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def is_super_admin(uid: int) -> bool:
    """Super admin tekshirish (ADMIN_IDS'da bo'lganlar)"""
    return uid in ADMIN_IDS

async def is_active_admin(uid: int) -> bool:
    """Faol admin yoki super admin tekshirish (database + ADMIN_IDS)"""
    if uid in ADMIN_IDS:
        return True
    
    try:
        async with db_pool.acquire() as conn:
            now = int(datetime.utcnow().timestamp())
            row = await conn.fetchrow("""
                SELECT active, expires_at FROM admins 
                WHERE user_id = $1
            """, uid)
            
            if not row:
                return False
            
            if not row['active']:
                return False
            
            if row['expires_at'] and row['expires_at'] < now:
                return False
            
            return True
    except Exception as e:
        logger.error(f"Error checking active admin {uid}: {e}")
        return False

async def get_admin_info(uid: int):
    """Admin ma'lumotlarini olish"""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM admins WHERE user_id = $1
        """, uid)

async def add_admin_to_db(user_id: int, name: str, role: str, created_by: int, expires_at: Optional[int] = None, managed_groups: Optional[list[int]] = None, max_groups: int = -1, tariff: str = "custom"):
    """Yangi admin qo'shish"""
    async with db_pool.acquire() as conn:
        now = int(datetime.utcnow().timestamp())
        await conn.execute("""
            INSERT INTO admins(user_id, name, role, active, created_at, expires_at, created_by, managed_groups, max_groups, tariff)
            VALUES($1, $2, $3, TRUE, $4, $5, $6, $7, $8, $9)
            ON CONFLICT(user_id) DO UPDATE SET
                name = $2,
                role = $3,
                active = TRUE,
                expires_at = $5,
                managed_groups = $7,
                max_groups = $8,
                tariff = $9
        """, user_id, name, role, now, expires_at, created_by, managed_groups or [], max_groups, tariff)

async def remove_admin_from_db(user_id: int):
    """Adminni o'chirish"""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)

async def pause_admin(user_id: int):
    """Adminni to'xtatish"""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admins SET active = FALSE WHERE user_id = $1", user_id)

async def resume_admin(user_id: int):
    """Adminni qayta faollashtirish"""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admins SET active = TRUE WHERE user_id = $1", user_id)

async def extend_admin(user_id: int, new_expires_at: int):
    """Admin muddatini uzaytirish"""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE admins SET expires_at = $1 WHERE user_id = $2", new_expires_at, user_id)

async def get_all_admins():
    """Barcha adminlar ro'yxati"""
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM admins ORDER BY created_at DESC")

async def get_admin_managed_groups(uid: int) -> list[int]:
    """Admin boshqaradigan guruhlar ro'yxati"""
    if uid in ADMIN_IDS:
        return GROUP_IDS
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT managed_groups FROM admins WHERE user_id = $1", uid)
        if row and row['managed_groups']:
            return list(row['managed_groups'])
        return []

async def get_allowed_groups(uid: int) -> list[int]:
    """Admin uchun ruxsat etilgan guruhlar ro'yxatini olish.
    
    Bu markazlashtirilgan funksiya barcha admin handlerlarida ishlatiladi:
    - Super adminlar uchun: barcha guruhlar (GROUP_IDS)
    - Oddiy adminlar uchun: faqat tayinlangan guruhlar (managed_groups)
    """
    if is_super_admin(uid):
        return GROUP_IDS
    
    # Database'dan adminning managed_groups'ini olish
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT managed_groups FROM admins 
            WHERE user_id = $1 AND active = TRUE
        """, uid)
        
        if row and row['managed_groups']:
            # Faqat mavjud guruhlarni qaytarish
            managed = list(row['managed_groups'])
            return [gid for gid in managed if gid in GROUP_IDS]
        
        return []

async def check_group_access(admin_id: int, group_id: int) -> bool:
    """Adminning guruhga ruxsati borligini tekshirish.
    
    Returns:
        True - agar admin guruhga ruxsat etilgan bo'lsa
        False - agar admin guruhga ruxsat etilmagan bo'lsa
    """
    allowed_groups = await get_allowed_groups(admin_id)
    return group_id in allowed_groups

async def is_member_of_any_group(uid: int) -> bool:
    """Foydalanuvchi kamida bitta guruhda ekanligini tekshirish."""
    for group_id in GROUP_IDS:
        try:
            member = await bot.get_chat_member(group_id, uid)
            if member.status in ["member", "administrator", "creator"]:
                return True
        except Exception:
            continue
    return False

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

async def build_contract_files(user_fullname: str, user_phone: Optional[str]):
    """Database'dan shartnoma matnini olib, PDF va TXT yaratish."""
    # Database'dan shartnoma matnini olish
    contract_text = await get_contract_template()
    
    stamped = f"{contract_text}\n\n---\nO'quvchi: {user_fullname}\nTelefon: {user_phone or '-'}\nSana: {(datetime.utcnow()+TZ_OFFSET).strftime('%Y-%m-%d %H:%M')}\n"
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

# Guruhga yangi a'zo qo'shilganda subscription boshlanadi
@dp.chat_member()
async def on_chat_member_updated(event: ChatMemberUpdated):
    """Guruh/kanalga yangi odam qo'shilganda yoki obuna bo'lganda 30 kunlik subscription boshlanadi (payment-first workflow)."""
    try:
        # Faqat guruhlar va kanallar uchun
        if event.chat.type not in ("group", "supergroup", "channel"):
            return
        
        # Faqat yangi a'zolar/obunachilar uchun (member bo'lmagandan member bo'lganda)
        if event.new_chat_member.status == "member" and event.old_chat_member.status not in ("member", "administrator", "creator"):
            user = event.new_chat_member.user
            
            # Botni o'zini e'tiborsiz qoldirish
            if user.id == bot.id:
                return
            
            # Database'da user'ni tekshirish - payment approved bo'lganmi?
            user_row = await get_user(user.id)
            
            # Payment'ni tekshirish
            payment_row = None
            if user_row:
                try:
                    async with db_pool.acquire() as conn:
                        payment_row = await conn.fetchrow(
                            "SELECT id, status FROM payments WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                            user.id
                        )
                except Exception:
                    pass
            
            # Agar payment approved bo'lsa - 30 kunlik subscription boshlanadi
            if payment_row and payment_row['status'] == 'approved':
                now = int(datetime.utcnow().timestamp())
                expires_at = now + SUBSCRIPTION_DAYS * 86400
                
                # Subscription boshlanadi
                username = user.username or ""
                full_name = user.full_name or user.first_name or "Nomsiz"
                phone = user_row[5] if user_row and len(user_row) > 5 else None
                
                await upsert_user(user.id, username, full_name, event.chat.id, expires_at, phone)
                await add_user_group(user.id, event.chat.id, expires_at)
                
                # User'ga xabar yuborish (guruh/kanal farqi bilan)
                expiry_date = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
                
                # Chat turini aniqlash
                if event.chat.type == "channel":
                    join_text = "kanalga obuna bo'ldingiz"
                    emoji = "📢"
                    type_name = "Kanal"
                else:
                    join_text = "guruhga qo'shildingiz"
                    emoji = "👥"
                    type_name = "Guruh"
                
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        text=(
                            f"🎉 *Tabriklayman!*\n\n"
                            f"✅ Siz {join_text} va obuna boshlanadi!\n\n"
                            f"📅 Obuna tugashi: {expiry_date}\n"
                            f"⏰ Muddat: {SUBSCRIPTION_DAYS} kun\n\n"
                            f"{emoji} {type_name}: {event.chat.title or type_name}"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"Failed to send subscription start message to user {user.id}: {e}")
                
                logger.info(f"Subscription started for user {user.id} in {event.chat.type} {event.chat.id} - expires at {expiry_date}")
            else:
                # Payment-first workflow: User guruhga faqat admin tasdiqidan keyin qo'shiladi
                # Agar payment approved bo'lmasa - bu noto'g'ri holat (edge case: admin to'g'ridan qo'shgan)
                # User'ni guruhdan chiqarish va admin'ga xabar yuborish
                try:
                    # User'ni guruhdan chiqarish
                    await bot.ban_chat_member(event.chat.id, user.id)
                    await bot.unban_chat_member(event.chat.id, user.id)  # Ban'ni olib tashlash (faqat guruhdan chiqarish)
                    
                    logger.warning(f"User {user.id} joined group {event.chat.id} without approved payment - removed from group")
                    
                    # User'ga xabar yuborish
                    bot_username = (await bot.get_me()).username
                    try:
                        await bot.send_message(
                            chat_id=user.id,
                            text=(
                                f"⚠️ *Guruhga kirish rad etildi*\n\n"
                                f"Siz guruhga to'g'ridan qo'shilgansiz, lekin obuna aktiv emas.\n\n"
                                f"📝 Obuna olish uchun:\n"
                                f"1️⃣ Mening chatimda /start bosing: @{bot_username}\n"
                                f"2️⃣ To'lov qiling va admin tasdiqini kuting\n\n"
                                f"✅ Admin tasdiqlagach, sizga invite link yuboriladi."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as msg_err:
                        logger.warning(f"Failed to send removal notice to user {user.id}: {msg_err}")
                    
                except Exception as remove_err:
                    logger.error(f"Failed to remove unapproved user {user.id} from group {event.chat.id}: {remove_err}")
            
    except Exception as e:
        logger.error(f"Error in on_chat_member_updated: {e}")

def admin_reply_keyboard(uid: int) -> ReplyKeyboardMarkup:
    """Admin uchun doim ko'rinadigan tugmalar."""
    keyboard = [
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Guruh o'quvchilari")],
        [KeyboardButton(text="💳 To'lovlar"), KeyboardButton(text="💳 To'lov ma'lumoti")],
        [KeyboardButton(text="📋 Guruhlar ro'yxati")],
    ]
    
    # Super admin uchun qo'shimcha tugmalar
    if is_super_admin(uid):
        keyboard.append([KeyboardButton(text="➕ Guruh qo'shish"), KeyboardButton(text="👥 Adminlar")])
        keyboard.append([KeyboardButton(text="📝 Shartnoma tahrirlash"), KeyboardButton(text="🧹 Tozalash")])
    else:
        keyboard.append([KeyboardButton(text="📝 Shartnoma tahrirlash"), KeyboardButton(text="🧹 Tozalash")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True
    )

@dp.message(Command("start"))
async def cmd_start(m: Message):
    try:
        # Admin uchun alohida interfeys (Super Admin yoki Faol Admin)
        if await is_active_admin(m.from_user.id):
            await m.answer(
                "👨‍💼 *ADMIN PANEL*\n\n"
                "Quyidagi tugmalardan birini tanlang:",
                reply_markup=admin_reply_keyboard(m.from_user.id),
                parse_mode="Markdown"
            )
            return
        
        # Avval ro'yxatdan o'tganlarni tekshirish
        user_row = await get_user(m.from_user.id)
        
        if user_row:
            # Foydalanuvchi database'da bor - obuna holatini tekshirish
            user_id, group_id, expires_at, username, full_name, phone, agreed_at = user_row
            now = int(datetime.utcnow().timestamp())
            
            # Barcha guruhlar bo'yicha obuna holatini olish
            async with db_pool.acquire() as conn:
                user_groups_rows = await conn.fetch(
                    "SELECT group_id, expires_at FROM user_groups WHERE user_id = $1", 
                    m.from_user.id
                )
            
            # Guruh nomlarini olish
            titles = dict(await resolve_group_titles())
            
            active_subscriptions = []
            expired_subscriptions = []
            
            # Asosiy guruhni tekshirish (users jadvalidan)
            if expires_at and group_id:
                # Telegram'dan guruh a'zoligini tekshirish
                try:
                    member = await bot.get_chat_member(group_id, m.from_user.id)
                    if member.status in ("member", "administrator", "creator"):
                        if expires_at > now:
                            exp_str, days_left = human_left(expires_at)
                            group_name = titles.get(group_id, f"Guruh {group_id}")
                            active_subscriptions.append((group_name, exp_str, days_left))
                        else:
                            exp_str, days_left = human_left(expires_at)
                            group_name = titles.get(group_id, f"Guruh {group_id}")
                            expired_subscriptions.append((group_name, exp_str))
                except Exception as e:
                    logger.debug(f"User {m.from_user.id} not in group {group_id}: {e}")
            
            # Qo'shimcha guruhlarni tekshirish (user_groups jadvalidan)
            for row in user_groups_rows:
                gid = row['group_id']
                exp = row['expires_at']
                
                if not exp or not gid:
                    continue
                
                # Telegram'dan guruh a'zoligini tekshirish
                try:
                    member = await bot.get_chat_member(gid, m.from_user.id)
                    if member.status in ("member", "administrator", "creator"):
                        if exp > now:
                            exp_str, days_left = human_left(exp)
                            group_name = titles.get(gid, f"Guruh {gid}")
                            active_subscriptions.append((group_name, exp_str, days_left))
                        else:
                            exp_str, days_left = human_left(exp)
                            group_name = titles.get(gid, f"Guruh {gid}")
                            expired_subscriptions.append((group_name, exp_str))
                except Exception as e:
                    logger.debug(f"User {m.from_user.id} not in group {gid}: {e}")
            
            # Natijalarni ko'rsatish
            if active_subscriptions:
                lines = [
                    f"✅ <b>Sizning obunalaringiz:</b>\n",
                    f"👤 Ism: {full_name}",
                    f"📞 Telefon: {phone or 'Belgilanmagan'}\n"
                ]
                
                for group_name, exp_str, days_left in active_subscriptions:
                    lines.append(f"🏷 <b>{group_name}</b>")
                    lines.append(f"   📅 Tugash: {exp_str}")
                    lines.append(f"   ⏳ Qolgan: {days_left} kun\n")
                
                if expired_subscriptions:
                    lines.append("\n⚠️ <b>Muddati tugagan obunalar:</b>\n")
                    for group_name, exp_str in expired_subscriptions:
                        lines.append(f"🏷 {group_name} - Tugagan: {exp_str}")
                
                lines.append("\n🎓 Darslarni yaxshi o'zlashtirishingizni tilaymiz!")
                
                # To'lov yo'riqnomasini qo'shish
                lines.append("\n" + "─" * 30)
                lines.append("\n💳 <b>Yangi to'lov qilish:</b>")
                
                # To'lov ma'lumotlarini olish
                try:
                    payment_settings = await get_payment_settings()
                    if payment_settings:
                        bank = payment_settings['bank_name']
                        card = payment_settings['card_number']
                        amount = payment_settings['amount']
                        
                        lines.append(f"\n🏦 Bank: {bank}")
                        lines.append(f"💰 Summa: {amount}")
                        lines.append(f"💳 Karta: <code>{card}</code>")
                        lines.append("\n📸 To'lovni amalga oshiring va quyidagi tugmani bosing.")
                    else:
                        lines.append("\n📸 To'lov qilish uchun quyidagi tugmani bosing.")
                except Exception:
                    lines.append("\n📸 To'lov qilish uchun quyidagi tugmani bosing.")
                
                # Tugma orqali to'lov qilish
                renewal_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 To'lov qilish", callback_data="renew_payment")]
                ])
                
                await m.answer("\n".join(lines), parse_mode="HTML", reply_markup=renewal_kb)
                logger.info(f"User {m.from_user.id} has {len(active_subscriptions)} active subscription(s)")
                return
            else:
                # Hech qaysi guruhda aktiv obuna yo'q
                lines = [
                    f"⚠️ <b>Hech qaysi guruhda aktiv obuna yo'q</b>\n",
                    f"👤 Ism: {full_name}",
                    f"📞 Telefon: {phone or 'Belgilanmagan'}\n"
                ]
                
                if expired_subscriptions:
                    lines.append("⏰ <b>Muddati tugagan obunalar:</b>\n")
                    for group_name, exp_str in expired_subscriptions:
                        lines.append(f"🏷 {group_name} - Tugagan: {exp_str}")
                
                lines.append("\n📝 Obunani yangilash uchun to'lov qiling.")
                
                # To'lov ma'lumotlarini ko'rsatish
                lines.append("\n" + "─" * 30)
                lines.append("\n💳 <b>To'lov qilish:</b>")
                
                try:
                    payment_settings = await get_payment_settings()
                    if payment_settings:
                        bank = payment_settings['bank_name']
                        card = payment_settings['card_number']
                        amount = payment_settings['amount']
                        
                        lines.append(f"\n🏦 Bank: {bank}")
                        lines.append(f"💰 Summa: {amount}")
                        lines.append(f"💳 Karta: <code>{card}</code>")
                        lines.append("\n📸 To'lovni amalga oshiring va quyidagi tugmani bosing.")
                    else:
                        lines.append("\n📸 To'lov qilish uchun quyidagi tugmani bosing.")
                except Exception:
                    lines.append("\n📸 To'lov qilish uchun quyidagi tugmani bosing.")
                
                # Tugma orqali to'lov qilish
                renewal_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 To'lov qilish", callback_data="renew_payment")]
                ])
                
                await m.answer("\n".join(lines), parse_mode="HTML", reply_markup=renewal_kb)
                logger.info(f"User {m.from_user.id} has no active subscriptions")
                return
        
        # Yangi foydalanuvchi - ro'yxatdan o'tish jarayoni
        WAIT_FULLNAME_FOR.add(m.from_user.id)
        
        await m.answer(
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "📝 Iltimos, <b>to'liq ismingizni</b> (Ism Familiya) kiriting:\n\n"
            "Misol: Ali Valiyev",
            parse_mode="HTML"
        )
        
        logger.info(f"User {m.from_user.id} started registration - waiting for fullname")
        
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

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

@dp.callback_query(F.data == "renew_payment")
async def cb_renew_payment(c: CallbackQuery):
    """Qayta to'lov qilish - mavjud userlar uchun."""
    try:
        # User'ni to'lov kutish rejimiga qo'shish
        WAIT_PAYMENT_PHOTO.add(c.from_user.id)
        
        # To'lov ma'lumotlarini olish
        payment_settings = await get_payment_settings()
        
        if payment_settings:
            bank = payment_settings['bank_name']
            card = payment_settings['card_number']
            amount = payment_settings['amount']
            additional = payment_settings.get('additional_info', '')
            
            payment_info = (
                f"💳 <b>To'lov ma'lumoti:</b>\n\n"
                f"🏦 Bank: {bank}\n"
                f"💰 Summa: {amount}\n"
                f"📋 Karta: <code>{card}</code>\n"
            )
            
            if additional:
                payment_info += f"\n📝 {additional}\n"
        else:
            payment_info = (
                "💳 <b>To'lov ma'lumoti:</b>\n\n"
                "📸 To'lov chekini yuboring.\n"
            )
        
        await c.message.answer(
            f"{payment_info}\n\n"
            "📸 <b>To'lov chekini yuklang:</b>\n\n"
            "To'lov qilganingizdan so'ng chekni surat qilib yuboring.\n"
            "Admin tekshirib, tasdiqlaydi.",
            parse_mode="HTML"
        )
        
        await c.answer("✅ To'lov chekini yuboring")
        logger.info(f"User {c.from_user.id} started renewal payment process")
        
    except Exception as e:
        logger.error(f"Error in cb_renew_payment: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

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
    """Barcha guruhlarni ko'rsatish (database'dan) - nomlar bilan."""
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    groups = await get_all_groups()
    if not groups:
        return await m.answer(
            "❌ Hozircha guruhlar mavjud emas.\n\n"
            "➕ Yangi guruh qo'shish:\n"
            "<code>/add_group GROUP_ID [Guruh nomi]</code>",
            parse_mode="HTML"
        )
    
    lines = ["🔗 <b>Ulangan guruhlar:</b>\n"]
    for row in groups:
        gid = row['group_id']
        name = row['name']
        gtype = row.get('type', 'group')
        created_at = row['created_at']
        created_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # Agar nom bo'sh bo'lsa, Telegram'dan olish va yangilash
        if not name or name.startswith("Guruh #"):
            try:
                chat = await bot.get_chat(gid)
                name = chat.title or f"Guruh #{gid}"
                
                # Database'ni yangilash
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE groups SET name = $1 WHERE group_id = $2",
                        name, gid
                    )
                logger.info(f"Updated group name for {gid}: {name}")
            except Exception as e:
                logger.warning(f"Failed to get chat title for {gid}: {e}")
                name = f"Guruh #{gid}"
        
        # Guruh turi emoji
        type_emoji = "📢" if gtype == "channel" else "👥"
        
        lines.append(f"{type_emoji} <b>{name}</b>\n   ID: <code>{gid}</code>\n   Qo'shilgan: {created_date}\n")
    
    lines.append("\n💡 Buyruqlar:")
    lines.append("➕ <code>/add_group GROUP_ID [Guruh nomi]</code>")
    lines.append("➖ <code>/remove_group GROUP_ID</code>")
    
    await m.answer("\n".join(lines), parse_mode="HTML")

@dp.message(Command("add_group"))
async def cmd_add_group(m: Message):
    """Yangi guruh yoki kanal qo'shish (faqat super admin)."""
    global GROUP_IDS
    
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 2:
            return await m.answer(
                "❌ <b>Noto'g'ri format!</b>\n\n"
                "📋 <b>To'g'ri format:</b>\n"
                "<code>/add_group -1001234567890 [Nom]</code>\n\n"
                "📌 <b>Misol:</b>\n"
                "• <code>/add_group -1002950957206 Python kursi</code> (Guruh)\n"
                "• <code>/add_group -1003047829296 E'lonlar kanali</code> (Kanal)\n\n"
                "💡 <b>Izoh:</b> Guruh ham, kanal ham qo'shishingiz mumkin!",
                parse_mode="HTML"
            )
        
        group_id = int(parts[1])
        name = parts[2] if len(parts) > 2 else None
        
        # Guruh yoki kanal turini aniqlash (Telegram API orqali)
        try:
            chat = await bot.get_chat(group_id)
            actual_name = chat.title or name or "Nomsiz"
            
            # Chat turini aniqlash
            if chat.type == "channel":
                chat_type = "channel"
                type_emoji = "📢"
                type_name = "Kanal"
            elif chat.type in ("group", "supergroup"):
                chat_type = "group"
                type_emoji = "👥"
                type_name = "Guruh"
            else:
                chat_type = "group"  # Default
                type_emoji = "❓"
                type_name = "Noma'lum"
            
            # Database'ga qo'shish
            await add_group_to_db(group_id, actual_name, chat_type)
            
        except Exception as e:
            error_msg = str(e).lower()
            logger.warning(f"Failed to get chat info for {group_id}: {e}")
            
            # Aniq xatolik xabarlari
            if "chat not found" in error_msg or "chat_not_found" in error_msg:
                return await m.answer(
                    f"❌ <b>Guruh topilmadi!</b>\n\n"
                    f"🆔 ID: <code>{group_id}</code>\n\n"
                    f"💡 <b>Sabablari:</b>\n"
                    f"• Guruh ID noto'g'ri\n"
                    f"• Bot guruhda admin emas\n"
                    f"• Bot guruhda umuman yo'q\n\n"
                    f"✅ <b>Yechim:</b>\n"
                    f"1. Botni guruhga qo'shing\n"
                    f"2. Bot'ni admin qiling\n"
                    f"3. Qayta urinib ko'ring",
                    parse_mode="HTML"
                )
            elif "forbidden" in error_msg or "not enough rights" in error_msg:
                return await m.answer(
                    f"❌ <b>Bot'da huquq yo'q!</b>\n\n"
                    f"🆔 ID: <code>{group_id}</code>\n\n"
                    f"✅ <b>Yechim:</b>\n"
                    f"Bot'ni guruhda <b>admin</b> qiling va qayta urinib ko'ring.",
                    parse_mode="HTML"
                )
            else:
                # Boshqa xatoliklar uchun - default qiymat bilan qo'shish
                actual_name = name or "Nomsiz"
                chat_type = "group"
                type_emoji = "❓"
                type_name = "Noma'lum"
                await add_group_to_db(group_id, actual_name, chat_type)
        
        # GROUP_IDS ni yangilash
        GROUP_IDS = await load_groups_from_db()
        
        await m.answer(
            f"✅ <b>Muvaffaqiyatli qo'shildi!</b>\n\n"
            f"{type_emoji} <b>Tur:</b> {type_name}\n"
            f"📚 <b>Nom:</b> {actual_name}\n"
            f"🆔 <b>ID:</b> <code>{group_id}</code>\n\n"
            f"🔢 <b>Jami:</b> {len(GROUP_IDS)} ta",
            parse_mode="HTML"
        )
        logger.info(f"Admin {m.from_user.id} added {chat_type} {group_id} ({actual_name})")
        
    except ValueError:
        await m.answer("❌ ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_add_group: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("remove_group"))
async def cmd_remove_group(m: Message):
    """Guruhni o'chirish (faqat super admin)."""
    global GROUP_IDS
    
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 2:
            return await m.answer(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format:\n"
                "<code>/remove_group -1001234567890</code>",
                parse_mode="HTML"
            )
        
        group_id = int(parts[1])
        
        # Guruh mavjudligini tekshirish
        if group_id not in GROUP_IDS:
            return await m.answer(f"❌ Guruh topilmadi: <code>{group_id}</code>", parse_mode="HTML")
        
        # Guruhni database'dan o'chirish
        await remove_group_from_db(group_id)
        
        # GROUP_IDS ni yangilash
        GROUP_IDS = await load_groups_from_db()
        
        await m.answer(
            f"✅ <b>Guruh muvaffaqiyatli o'chirildi!</b>\n\n"
            f"🆔 ID: <code>{group_id}</code>\n\n"
            f"🔢 Qolgan guruhlar: {len(GROUP_IDS)}",
            parse_mode="HTML"
        )
        logger.info(f"Admin {m.from_user.id} removed group {group_id}")
        
    except ValueError:
        await m.answer("❌ Guruh ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_remove_group: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("admins"))
async def cmd_admins(m: Message):
    """Barcha adminlar ro'yxati (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    admins = await get_all_admins()
    if not admins:
        return await m.answer(
            "❌ Hozircha adminlar mavjud emas.\n\n"
            "➕ Yangi admin qo'shish:\n"
            "<code>/add_admin USER_ID MUDDATI [Guruhlar]</code>\n\n"
            "Misol:\n"
            "<code>/add_admin 123456789 30</code> - 30 kunlik admin\n"
            "<code>/add_admin 123456789 0</code> - Cheksiz muddatli admin",
            parse_mode="HTML"
        )
    
    now = int(datetime.utcnow().timestamp())
    lines = ["👥 <b>Adminlar ro'yxati:</b>\n"]
    
    for row in admins:
        uid = row['user_id']
        name = row['name'] or f"User {uid}"
        role = row['role']
        active = row['active']
        expires_at = row['expires_at']
        created_at = row['created_at']
        managed_groups = row['managed_groups'] or []
        max_groups = row.get('max_groups', -1)
        tariff_key = row.get('tariff', 'custom')
        
        status_emoji = "✅" if active else "⏸️"
        role_text = "🔴 Super Admin" if role == 'super_admin' else "🔵 Admin"
        
        # Tarif ma'lumoti
        if tariff_key in TARIFFS:
            tariff_info = TARIFFS[tariff_key]
            tariff_text = f"{tariff_info['name']}"
        else:
            tariff_text = "Custom"
        
        created_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        if expires_at:
            exp_str, days_left = human_left(expires_at)
            if expires_at < now:
                expiry_text = f"❌ Muddati tugagan ({exp_str})"
            else:
                expiry_text = f"📅 {exp_str} ({days_left} kun)"
        else:
            expiry_text = "♾️ Cheksiz"
        
        # Guruh va limit ma'lumoti
        current_groups = len(managed_groups)
        if max_groups == -1:
            groups_text = f"{current_groups} ta guruh (cheksiz limit)"
        elif max_groups == 0:
            groups_text = "0 ta guruh (limit yo'q)"
        else:
            groups_text = f"{current_groups}/{max_groups} ta guruh"
        
        lines.append(
            f"{status_emoji} <b>{name}</b> {role_text}\n"
            f"   ID: <code>{uid}</code>\n"
            f"   📦 Tarif: {tariff_text}\n"
            f"   📊 Guruhlar: {groups_text}\n"
            f"   📅 Muddat: {expiry_text}\n"
            f"   🕒 Qo'shilgan: {created_date}\n"
        )
    
    lines.append("\n💡 <b>Buyruqlar:</b>")
    lines.append("➕ <code>/add_admin USER_ID MUDDATI</code> (0=cheksiz)")
    lines.append("➖ <code>/remove_admin USER_ID</code>")
    lines.append("⏸️ <code>/pause_admin USER_ID</code>")
    lines.append("▶️ <code>/resume_admin USER_ID</code>")
    lines.append("📅 <code>/extend_admin USER_ID MUDDATI</code> (kun qo'shish)")
    
    await m.answer("\n".join(lines), parse_mode="HTML")

@dp.message(Command("add_admin"))
async def cmd_add_admin(m: Message):
    """Yangi admin qo'shish (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 3:
            return await m.answer(
                "❌ <b>Noto'g'ri format!</b>\n\n"
                "📋 <b>To'g'ri format:</b>\n"
                "<code>/add_admin USER_ID MUDDATI</code>\n\n"
                "📌 <b>Misol:</b>\n"
                "• <code>/add_admin 123456789 30</code> - 30 kunlik admin\n"
                "• <code>/add_admin 123456789 7</code> - 7 kunlik admin\n"
                "• <code>/add_admin 123456789 0</code> - Cheksiz muddatli admin\n\n"
                "💡 <b>Izoh:</b> 0 = Cheksiz muddat",
                parse_mode="HTML"
            )
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        # Super admin bo'lsa
        if user_id in ADMIN_IDS:
            return await m.answer("❌ Bu foydalanuvchi allaqachon super admin!")
        
        # Muddatni hisoblash
        if days > 0:
            expires_at = int((datetime.utcnow() + timedelta(days=days)).timestamp())
            expiry_text = f"{days} kun"
        else:
            expires_at = None
            expiry_text = "Cheksiz"
        
        # Foydalanuvchi ma'lumotlarini olish
        try:
            username, full_name = await fetch_user_profile(user_id)
            admin_name = full_name or username or f"User {user_id}"
        except Exception:
            admin_name = f"User {user_id}"
        
        # Admin qo'shish (boshida guruhlar bo'sh - super admin keyin tayinlaydi)
        await add_admin_to_db(
            user_id=user_id,
            name=admin_name,
            role='admin',
            created_by=m.from_user.id,
            expires_at=expires_at,
            managed_groups=[],  # Boshida bo'sh - keyin super admin guruh tayinlaydi
            max_groups=0,  # Cheksiz guruh
            tariff='custom'  # Maxsus
        )
        
        await m.answer(
            f"✅ <b>Admin muvaffaqiyatli qo'shildi!</b>\n\n"
            f"👤 Ism: {admin_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📅 Muddat: {expiry_text}\n"
            f"📊 Guruh limiti: Cheksiz\n\n"
            f"⚠️ <b>Guruhlar hali tayinlanmagan!</b>\n"
            f"Guruhlarni /groups buyrug'i orqali tayinlang.",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} added admin {user_id} with tariff {tariff_key}")
        
        # Yangi adminga xabar yuborish
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Siz admin sifatida tayinlandingiz!\n\n"
                f"📦 Tarif: {tariff['name']}\n"
                f"📅 Muddat: {expiry_text}\n"
                f"📊 Guruh limiti: {groups_text}\n"
                f"💰 Narx: {tariff['price']:,} so'm\n\n"
                f"Bot'ga /start buyrug'ini yuboring.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify new admin {user_id}: {e}")
        
    except ValueError:
        await m.answer("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_add_admin: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("remove_admin"))
async def cmd_remove_admin(m: Message):
    """Adminni o'chirish (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 2:
            return await m.answer(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format:\n"
                "<code>/remove_admin USER_ID</code>",
                parse_mode="HTML"
            )
        
        user_id = int(parts[1])
        
        # Super admin bo'lsa
        if user_id in ADMIN_IDS:
            return await m.answer("❌ Super adminni o'chirish mumkin emas!")
        
        # Admin mavjudligini tekshirish
        admin_info = await get_admin_info(user_id)
        if not admin_info:
            return await m.answer(f"❌ Admin topilmadi: <code>{user_id}</code>", parse_mode="HTML")
        
        # Adminni o'chirish
        await remove_admin_from_db(user_id)
        
        await m.answer(
            f"✅ <b>Admin muvaffaqiyatli o'chirildi!</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {admin_info['name']}",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} removed admin {user_id}")
        
        # O'chirilgan adminga xabar yuborish
        try:
            await bot.send_message(
                user_id,
                "⚠️ <b>Diqqat!</b>\n\n"
                "Sizning admin huquqlaringiz bekor qilindi.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
    except ValueError:
        await m.answer("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_remove_admin: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("pause_admin"))
async def cmd_pause_admin(m: Message):
    """Adminni vaqtincha to'xtatish (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 2:
            return await m.answer(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format:\n"
                "<code>/pause_admin USER_ID</code>",
                parse_mode="HTML"
            )
        
        user_id = int(parts[1])
        
        if user_id in ADMIN_IDS:
            return await m.answer("❌ Super adminni to'xtatish mumkin emas!")
        
        admin_info = await get_admin_info(user_id)
        if not admin_info:
            return await m.answer(f"❌ Admin topilmadi: <code>{user_id}</code>", parse_mode="HTML")
        
        if not admin_info['active']:
            return await m.answer("⚠️ Admin allaqachon to'xtatilgan!")
        
        await pause_admin(user_id)
        
        await m.answer(
            f"⏸️ <b>Admin vaqtincha to'xtatildi!</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {admin_info['name']}\n\n"
            f"Qayta faollashtirish: <code>/resume_admin {user_id}</code>",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} paused admin {user_id}")
        
    except ValueError:
        await m.answer("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_pause_admin: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("resume_admin"))
async def cmd_resume_admin(m: Message):
    """Adminni qayta faollashtirish (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 2:
            return await m.answer(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format:\n"
                "<code>/resume_admin USER_ID</code>",
                parse_mode="HTML"
            )
        
        user_id = int(parts[1])
        
        admin_info = await get_admin_info(user_id)
        if not admin_info:
            return await m.answer(f"❌ Admin topilmadi: <code>{user_id}</code>", parse_mode="HTML")
        
        if admin_info['active']:
            return await m.answer("⚠️ Admin allaqachon faol!")
        
        await resume_admin(user_id)
        
        await m.answer(
            f"▶️ <b>Admin qayta faollashtirildi!</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {admin_info['name']}",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} resumed admin {user_id}")
        
    except ValueError:
        await m.answer("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_resume_admin: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("extend_admin"))
async def cmd_extend_admin(m: Message):
    """Admin muddatini uzaytirish (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 3:
            return await m.answer(
                "❌ <b>Noto'g'ri format!</b>\n\n"
                "📋 <b>To'g'ri format:</b>\n"
                "<code>/extend_admin USER_ID MUDDATI</code>\n\n"
                "📌 <b>Misol:</b>\n"
                "• <code>/extend_admin 123456789 30</code> - 30 kun qo'shish\n"
                "• <code>/extend_admin 123456789 7</code> - 7 kun qo'shish\n"
                "• <code>/extend_admin 123456789 0</code> - Cheksiz muddatga o'zgartirish\n\n"
                "💡 <b>Izoh:</b> Hozirgi muddatga qo'shiladi (0 bo'lsa cheksiz bo'ladi)",
                parse_mode="HTML"
            )
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        admin_info = await get_admin_info(user_id)
        if not admin_info:
            return await m.answer(f"❌ Admin topilmadi: <code>{user_id}</code>", parse_mode="HTML")
        
        # Muddatni uzaytirish
        if days > 0:
            # Agar hozirgi muddat cheksiz bo'lsa yoki yo'q bo'lsa, hozirgi vaqtdan boshlaymiz
            if admin_info['expires_at'] is None:
                base_time = datetime.utcnow()
            else:
                # Agar hozirgi muddat bor bo'lsa, unga qo'shamiz
                current_expiry = datetime.fromtimestamp(admin_info['expires_at'])
                if current_expiry > datetime.utcnow():
                    base_time = current_expiry  # Hozirgi muddatga qo'shamiz
                else:
                    base_time = datetime.utcnow()  # Muddat o'tgan bo'lsa, yangi boshlaymiz
            
            new_expires_at = int((base_time + timedelta(days=days)).timestamp())
            expiry_text = f"{days} kun qo'shildi"
        else:
            new_expires_at = None
            expiry_text = "Cheksiz muddatga o'zgartirildi"
        
        # Admin ma'lumotlarini yangilash
        await add_admin_to_db(
            user_id=user_id,
            name=admin_info['name'],
            role=admin_info['role'],
            created_by=m.from_user.id,
            expires_at=new_expires_at,
            managed_groups=admin_info['managed_groups'] or [],
            max_groups=admin_info.get('max_groups', 0),
            tariff=admin_info.get('tariff', 'custom')
        )
        
        await m.answer(
            f"📅 <b>Admin muddati uzaytirildi va tarif yangilandi!</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {admin_info['name']}\n"
            f"📦 Yangi tarif: {tariff['name']}\n"
            f"📅 Muddat: {expiry_text}\n"
            f"📊 Guruh limit: {tariff['max_groups']} ta",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} extended admin {user_id} with tariff {tariff_key}")
        
        # Admin'ga xabar yuborish
        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Tarifingiz yangilandi!</b>\n\n"
                f"📦 Tarif: {tariff['name']}\n"
                f"📅 Muddat: {expiry_text}\n"
                f"📊 Guruh limit: {tariff['max_groups']} ta\n"
                f"💰 Narx: {tariff['price']:,} so'm",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify admin {user_id}: {e}")
        
    except ValueError:
        await m.answer("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_extend_admin: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("assign_groups"))
async def cmd_assign_groups(m: Message):
    """Adminga guruhlar tayinlash (faqat super admin)."""
    if not is_super_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat super adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        parts = (m.text or "").split()
        if len(parts) < 3:
            # Mavjud guruhlarni ko'rsatish
            if GROUP_IDS:
                groups_list = "\n".join([f"• <code>{gid}</code>" for gid in GROUP_IDS])
            else:
                groups_list = "Guruhlar mavjud emas"
            
            return await m.answer(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format:\n"
                "<code>/assign_groups ADMIN_ID GROUP_ID1 GROUP_ID2 ...</code>\n\n"
                f"<b>Mavjud guruhlar:</b>\n{groups_list}\n\n"
                "Misol:\n"
                "<code>/assign_groups 123456789 -1001234567890</code> - 1 ta guruh\n"
                "<code>/assign_groups 123456789 -1001234567890 -1009876543210</code> - 2 ta guruh",
                parse_mode="HTML"
            )
        
        admin_id = int(parts[1])
        group_ids_str = parts[2:]
        
        # Admin mavjudligini tekshirish
        admin_info = await get_admin_info(admin_id)
        if not admin_info:
            return await m.answer(f"❌ Admin topilmadi: <code>{admin_id}</code>", parse_mode="HTML")
        
        # Guruh ID'larini parse qilish
        group_ids = []
        for gid_str in group_ids_str:
            try:
                gid = int(gid_str)
                if gid not in GROUP_IDS:
                    return await m.answer(f"❌ Guruh topilmadi: <code>{gid}</code>", parse_mode="HTML")
                group_ids.append(gid)
            except ValueError:
                return await m.answer(f"❌ Noto'g'ri guruh ID: <code>{gid_str}</code>", parse_mode="HTML")
        
        # max_groups limitini tekshirish
        max_groups = admin_info.get('max_groups', -1)
        if max_groups > 0 and len(group_ids) > max_groups:
            return await m.answer(
                f"❌ <b>Guruh limiti oshib ketdi!</b>\n\n"
                f"📊 Admin limiti: {max_groups} ta guruh\n"
                f"❌ Siz tayinlashga uringan: {len(group_ids)} ta guruh\n\n"
                f"Tarifni oshiring yoki kamroq guruh tayinlang.",
                parse_mode="HTML"
            )
        
        # Guruhlarni tayinlash
        await add_admin_to_db(
            user_id=admin_id,
            name=admin_info['name'],
            role=admin_info['role'],
            created_by=m.from_user.id,
            expires_at=admin_info['expires_at'],
            managed_groups=group_ids,
            max_groups=max_groups,
            tariff=admin_info.get('tariff', 'custom')
        )
        
        await m.answer(
            f"✅ <b>Guruhlar muvaffaqiyatli tayinlandi!</b>\n\n"
            f"🆔 Admin ID: <code>{admin_id}</code>\n"
            f"👤 Ism: {admin_info['name']}\n"
            f"📊 Tayinlangan guruhlar: {len(group_ids)}/{max_groups if max_groups > 0 else 'cheksiz'}\n"
            f"🏷 Guruh ID'lar: {', '.join(map(str, group_ids))}",
            parse_mode="HTML"
        )
        logger.info(f"Super admin {m.from_user.id} assigned {len(group_ids)} groups to admin {admin_id}")
        
        # Admin'ga xabar yuborish
        try:
            await bot.send_message(
                admin_id,
                f"✅ <b>Sizga guruhlar tayinlandi!</b>\n\n"
                f"📊 Guruhlar soni: {len(group_ids)}\n"
                f"🏷 Guruh ID'lar: {', '.join(map(str, group_ids))}\n\n"
                f"Bot'da /start bosing!",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id}: {e}")
        
    except ValueError:
        await m.answer("❌ Admin ID va guruh ID'lar raqam bo'lishi kerak!")
    except Exception as e:
        logger.error(f"Error in cmd_assign_groups: {e}")
        await m.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("edit_payment"))
async def cmd_edit_payment(m: Message):
    """Admin uchun to'lov ma'lumotlarini tahrirlash."""
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        # Hozirgi to'lov ma'lumotlarini olish
        payment_settings = await get_payment_settings()
        
        if payment_settings:
            bank = payment_settings['bank_name']
            card = payment_settings['card_number']
            amount = payment_settings['amount']
            additional = payment_settings.get('additional_info', '') or 'Yo\'q'
            
            current_info = (
                f"💳 <b>Hozirgi to'lov ma'lumotlari:</b>\n\n"
                f"🏦 Bank: {bank}\n"
                f"💰 Summa: {amount}\n"
                f"📋 Karta raqam: {card}\n"
                f"📝 Qo'shimcha: {additional}\n\n"
            )
        else:
            current_info = "💳 <b>To'lov ma'lumotlari hali kiritilmagan.</b>\n\n"
        
        await m.answer(
            f"{current_info}"
            f"✏️ <b>Yangi to'lov ma'lumotlarini kiriting</b>\n\n"
            f"📝 Quyidagi formatda yuboring:\n\n"
            f"<code>Bank nomi\n"
            f"Karta raqam\n"
            f"Summa\n"
            f"Qo'shimcha ma'lumot (ixtiyoriy)</code>\n\n"
            f"<b>Misol:</b>\n"
            f"<code>Xalq Banki\n"
            f"8600 1234 5678 9012\n"
            f"150,000 so'm\n"
            f"To'lov amalga oshirilgandan keyin chekni yuboring</code>",
            parse_mode="HTML"
        )
        
        # Yangi to'lov ma'lumotlarini kutish
        WAIT_PAYMENT_EDIT.add(m.from_user.id)
        logger.info(f"Admin {m.from_user.id} started payment info editing")
        
    except Exception as e:
        logger.error(f"Error in cmd_edit_payment: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.message(Command("edit_contract"))
async def cmd_edit_contract(m: Message):
    """Admin uchun shartnoma matnini tahrirlash."""
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        # Hozirgi shartnoma matnini olish
        contract_text = await get_contract_template()
        
        # Shartnoma matnini .txt file sifatida yuborish
        txt_bytes = contract_text.encode('utf-8')
        txt_file = BufferedInputFile(txt_bytes, filename="shartnoma.txt")
        
        await m.answer_document(
            txt_file,
            caption=(
                "📄 <b>Hozirgi shartnoma matni</b>\n\n"
                "📝 Shartnoma matnini o'zgartirish uchun:\n"
                "1️⃣ .txt faylni yuklang\n"
                "2️⃣ Yoki to'g'ridan-to'g'ri matn yuboring\n\n"
                "⚠️ Yangi matnni faylda yoki xabarda yuboring."
            ),
            parse_mode="HTML"
        )
        
        # Yangi shartnoma matnini kutish
        WAIT_CONTRACT_EDIT.add(m.from_user.id)
        logger.info(f"Admin {m.from_user.id} started contract editing")
        
    except Exception as e:
        logger.error(f"Error in cmd_edit_contract: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("bulk_add"))
async def cmd_bulk_add(m: Message):
    """Guruhning barcha a'zolarini bir vaqtda ro'yxatdan o'tkazish.
    
    Foydalanish:
    - /bulk_add  yoki  /bulk_add now  - bugundan 30 kun
    - /bulk_add 2025-11-01  - belgilangan sanadan 30 kun
    """
    if not is_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    # Faqat guruhlarda ishlaydi
    if m.chat.type not in ("group", "supergroup"):
        return await m.answer("❗ Bu buyruq faqat guruhlarda ishlaydi.")
    
    group_id = m.chat.id
    
    try:
        # Sana parametrini tekshirish
        parts = m.text.split(maxsplit=1)
        start_date = datetime.utcnow()
        
        if len(parts) > 1 and parts[1].strip().lower() != "now":
            # Sana kiritilgan
            date_str = parts[1].strip().replace("/", "-")
            if not DATE_RE.match(date_str):
                return await m.answer("❗ Format noto'g'ri. To'g'ri ko'rinish: /bulk_add 2025-11-01")
            try:
                start_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                return await m.answer("❗ Sana tushunilmadi. Misol: /bulk_add 2025-11-01")
        
        # Obuna tugash sanasini hisoblash
        expires_at = int((start_date + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        human_start = (start_date + TZ_OFFSET).strftime("%Y-%m-%d")
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # Jarayonni boshlash xabari
        processing_msg = await m.answer("⏳ Guruh a'zolari tekshirilmoqda...")
        
        # Guruhning barcha a'zolarini olish
        added_count = 0
        already_count = 0
        skipped_count = 0
        
        # Telegram API orqali guruh a'zolarini olish (admin count API'dan boshlaymiz)
        try:
            chat_member_count = await bot.get_chat_member_count(group_id)
            await processing_msg.edit_text(f"⏳ Guruhda {chat_member_count} a'zo topildi. Tekshirilmoqda...")
        except Exception:
            pass
        
        # Guruh a'zolarini olish uchun ChatMemberAdministrator va oddiy a'zolarni olishimiz kerak
        # Lekin Telegram Bot API bu funksiyani to'liq qo'llab-quvvatlamaydi (premium feature)
        # Shuning uchun biz mavjud database'dagi foydalanuvchilarni tekshiramiz
        
        # Alternative yechim: Guruhda yozgan har bir foydalanuvchini tracking qilish o'rniga
        # Admin manual ravishda user ID'larni kiritishi mumkin
        
        await processing_msg.edit_text(
            "ℹ️ *Telegram Bot API cheklovi*\n\n"
            "Afsuski, Telegram Bot API guruhning barcha a'zolari ro'yxatini olishga ruxsat bermaydi (bu premium feature).\n\n"
            "*Alternativ yechimlar:*\n\n"
            "1️⃣ *Har bir foydalanuvchini alohida qo'shish:*\n"
            "   `/add_user USER_ID 2025-11-01`\n"
            "   Misol: `/add_user 123456789 now`\n\n"
            "2️⃣ *Guruhda xabar yozishlarini kutish:*\n"
            "   Guruh a'zolari xabar yozganda bot avtomatik tracker qiladi\n\n"
            "3️⃣ *Telegram Desktop orqali:*\n"
            "   Guruh a'zolari ro'yxatini ko'chirib, har birini `/add_user` bilan qo'shing\n\n"
            "Men sizga `/add_user` commandini yaratib beraman - bir nechta foydalanuvchini tez qo'shish uchun.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in cmd_bulk_add: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("add_user"))
async def cmd_add_user(m: Message):
    """Foydalanuvchini qo'lda obunaga qo'shish.
    
    Foydalanish:
    - /add_user USER_ID  yoki  /add_user USER_ID now  - bugundan 30 kun
    - /add_user USER_ID 2025-11-01  - belgilangan sanadan 30 kun
    
    Misol:
    - /add_user 123456789 now
    - /add_user 987654321 2025-11-15
    """
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(m.from_user.id)
        if not allowed_groups:
            return await m.answer("❌ Sizga hech qanday guruhga ruxsat yo'q!")
        
        # Parametrlarni parsing qilish
        parts = m.text.split()
        
        if len(parts) < 2:
            return await m.answer(
                "❗ *Foydalanish:*\n\n"
                "`/add_user USER_ID [SANA]`\n\n"
                "*Misollar:*\n"
                "• `/add_user 123456789` - bugundan 30 kun\n"
                "• `/add_user 123456789 now` - bugundan 30 kun\n"
                "• `/add_user 123456789 2025-11-15` - belgilangan sanadan 30 kun",
                parse_mode="Markdown"
            )
        
        # User ID
        try:
            user_id = int(parts[1])
        except ValueError:
            return await m.answer("❗ User ID raqam bo'lishi kerak.\n\nMisol: `/add_user 123456789 now`", parse_mode="Markdown")
        
        # Sana (agar kiritilgan bo'lsa)
        start_date = datetime.utcnow()
        
        if len(parts) > 2 and parts[2].strip().lower() != "now":
            date_str = parts[2].strip().replace("/", "-")
            if not DATE_RE.match(date_str):
                return await m.answer("❗ Format noto'g'ri. To'g'ri ko'rinish: 2025-11-01")
            try:
                start_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                return await m.answer("❗ Sana tushunilmadi. Misol: 2025-11-01")
        
        # Obuna tugash sanasini hisoblash
        expires_at = int((start_date + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        human_start = (start_date + TZ_OFFSET).strftime("%Y-%m-%d")
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # Foydalanuvchi ma'lumotlarini olish
        username, fullname = await fetch_user_profile(user_id)
        
        # Adminning birinchi ruxsat etilgan guruhiga qo'shish
        primary_gid = allowed_groups[0]
        
        # Database'ga qo'shish
        await upsert_user(uid=user_id, username=username, full_name=fullname, group_id=primary_gid, expires_at=expires_at)
        
        # User'ga xabar yuborish (agar mumkin bo'lsa)
        try:
            await bot.send_message(
                user_id,
                f"✅ *Tabriklaymiz! Obuna faollashtirildi!*\n\n"
                f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun\n"
                f"⏳ Tugash sanasi: {human_exp}\n\n"
                f"🎓 Darslarni yaxshi o'zlashtirishingizni tilaymiz!",
                parse_mode="Markdown"
            )
            user_notified = "✅ Foydalanuvchiga xabar yuborildi"
        except Exception as e:
            logger.warning(f"Failed to notify user {user_id}: {e}")
            user_notified = "⚠️ Foydalanuvchiga xabar yuborib bo'lmadi (bot bilan chat ochilmagan)"
        
        # Admin'ga tasdiqlash
        await m.answer(
            f"✅ *FOYDALANUVCHI QO'SHILDI*\n\n"
            f"👤 {fullname}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun\n"
            f"⏳ Tugash: {human_exp}\n"
            f"🏷 Guruh: {primary_gid}\n\n"
            f"{user_notified}",
            parse_mode="Markdown"
        )
        
        logger.info(f"User {user_id} manually added by admin {m.from_user.id} with subscription until {human_exp}")
        
    except Exception as e:
        logger.error(f"Error in cmd_add_user: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("add_users"))
async def cmd_add_users(m: Message):
    """Bir nechta foydalanuvchini bir vaqtda bir xil sana bilan qo'shish.
    
    Foydalanish:
    - /add_users USER_ID1 USER_ID2 USER_ID3 ... [SANA]
    
    Misol:
    - /add_users 123456789 987654321 555111222 now
    - /add_users 123456789 987654321 2025-11-15
    - /add_users 111 222 333 444 555 2025-12-01
    """
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    # Admin'ning ruxsat etilgan guruhlarini olish
    allowed_groups = await get_allowed_groups(m.from_user.id)
    if not allowed_groups:
        return await m.answer("❌ Sizga hech qanday guruhga ruxsat yo'q!")
    
    try:
        # Parametrlarni parsing qilish
        parts = m.text.split()
        
        if len(parts) < 3:
            return await m.answer(
                "❗ *Foydalanish:*\n\n"
                "`/add_users USER_ID1 USER_ID2 ... [SANA]`\n\n"
                "*Misollar:*\n"
                "• `/add_users 123456789 987654321 now` - 2 ta user, bugundan\n"
                "• `/add_users 111 222 333 2025-11-15` - 3 ta user, belgilangan sanadan\n"
                "• `/add_users 111 222 333 444 555` - 5 ta user, bugundan",
                parse_mode="Markdown"
            )
        
        # Oxirgi element sana yoki "now" yoki user ID ekanligini aniqlash
        last_part = parts[-1].strip().lower()
        
        # Sana parametrini ajratish
        start_date = datetime.utcnow()
        user_id_parts = parts[1:]  # /add_users ni o'tkazib yuborish
        
        if last_part == "now":
            # Oxirgi "now" ni o'chirish
            user_id_parts = user_id_parts[:-1]
        elif DATE_RE.match(last_part.replace("/", "-")):
            # Oxirgi qism sana
            date_str = last_part.replace("/", "-")
            try:
                start_date = datetime.strptime(date_str, "%Y-%m-%d")
                user_id_parts = user_id_parts[:-1]
            except Exception:
                return await m.answer("❗ Sana tushunilmadi. Misol: 2025-11-01")
        # else: Oxirgi qism ham user ID, hamma narsa bugundan
        
        # User ID'larni parse qilish
        user_ids = []
        for part in user_id_parts:
            try:
                uid = int(part)
                user_ids.append(uid)
            except ValueError:
                return await m.answer(f"❗ '{part}' user ID emas. Faqat raqamlar kiriting.")
        
        if not user_ids:
            return await m.answer("❗ Kamida 1 ta user ID kiriting.")
        
        # Obuna tugash sanasini hisoblash
        expires_at = int((start_date + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        human_start = (start_date + TZ_OFFSET).strftime("%Y-%m-%d")
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # Adminning birinchi ruxsat etilgan guruhiga qo'shish
        primary_gid = allowed_groups[0]
        
        # Jarayonni boshlash
        processing_msg = await m.answer(f"⏳ {len(user_ids)} ta foydalanuvchi qo'shilmoqda...")
        
        # Barcha userlarni qo'shish
        added_users = []
        failed_users = []
        
        for user_id in user_ids:
            try:
                # Foydalanuvchi ma'lumotlarini olish
                username, fullname = await fetch_user_profile(user_id)
                
                # Database'ga qo'shish
                await upsert_user(uid=user_id, username=username, full_name=fullname, group_id=primary_gid, expires_at=expires_at)
                
                # User'ga xabar yuborish (agar mumkin bo'lsa)
                try:
                    await bot.send_message(
                        user_id,
                        f"✅ *Tabriklaymiz! Obuna faollashtirildi!*\n\n"
                        f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun\n"
                        f"⏳ Tugash sanasi: {human_exp}\n\n"
                        f"🎓 Darslarni yaxshi o'zlashtirishingizni tilaymiz!",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass  # Xabar yuborilmasa ham davom etamiz
                
                added_users.append((user_id, fullname))
                logger.info(f"User {user_id} added via bulk add by admin {m.from_user.id}")
                
            except Exception as e:
                logger.error(f"Failed to add user {user_id}: {e}")
                failed_users.append((user_id, str(e)))
        
        # Natijani ko'rsatish
        await processing_msg.delete()
        
        # Muvaffaqiyatli qo'shilganlar
        if added_users:
            success_lines = [
                f"✅ <b>{len(added_users)} TA FOYDALANUVCHI QOSHILDI</b>\n",
                f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun",
                f"⏳ Tugash: {human_exp}",
                f"🏷 Guruh: {primary_gid}\n"
            ]
            
            for user_id, fullname in added_users[:20]:
                safe_name = (fullname or f'User{user_id}').replace('<', '&lt;').replace('>', '&gt;')
                success_lines.append(f"• {safe_name} (ID: <code>{user_id}</code>)")
            
            if len(added_users) > 20:
                success_lines.append(f"... va yana {len(added_users) - 20} ta")
            
            await m.answer("\n".join(success_lines), parse_mode="HTML")
        
        # Xato bo'lganlar
        if failed_users:
            error_lines = [f"❌ <b>{len(failed_users)} TA XATOLIK</b>\n"]
            for user_id, error in failed_users[:10]:
                safe_error = str(error).replace('<', '&lt;').replace('>', '&gt;')
                error_lines.append(f"• User {user_id}: {safe_error}")
            
            if len(failed_users) > 10:
                error_lines.append(f"... va yana {len(failed_users) - 10} ta")
            
            await m.answer("\n".join(error_lines), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in cmd_add_users: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("unregistered"))
async def cmd_unregistered(m: Message):
    """Database'da obuna belgilanmagan foydalanuvchilarni ko'rsatish (tez versiya).
    
    Foydalanish:
    - Database'dan foydalanuvchilarni oladi
    - Obuna yo'q yoki tugaganlarni ko'rsatadi
    - Telegram API'ga murojaat qilmaydi (tez ishlaydi)
    """
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(m.from_user.id)
        if not allowed_groups:
            return await m.answer("❌ Sizga hech qanday guruhga ruxsat yo'q!")
        
        processing_msg = await m.answer("⏳ Database tekshirilmoqda...")
        
        now = int(datetime.utcnow().timestamp())
        unregistered_users = []
        
        # Faqat ruxsat etilgan guruhlarni tekshirish
        titles = dict(await resolve_group_titles(allowed_groups))
        
        for gid in allowed_groups:
            # Database'dan guruhga tegishli barcha userlarni olish
            async with db_pool.acquire() as conn:
                # users jadvalidan obuna yo'q yoki tugaganlarni olish
                query = """
                    SELECT DISTINCT u.user_id, u.username, u.full_name, u.phone, u.expires_at
                    FROM users u
                    LEFT JOIN user_groups ug ON u.user_id = ug.user_id AND ug.group_id = $1
                    WHERE u.group_id = $1 OR ug.user_id IS NOT NULL
                """
                all_users = await conn.fetch(query, gid)
            
            # Har bir userni tekshirish
            for row in all_users:
                user_id = row['user_id']
                username = row['username']
                fullname = row['full_name'] or f"User{user_id}"
                phone = row['phone']
                expires_at = row['expires_at']
                
                # Obuna yo'q yoki tugagan
                if not expires_at or expires_at == 0:
                    unregistered_users.append({
                        'user_id': user_id,
                        'username': username,
                        'fullname': fullname,
                        'group_id': gid,
                        'phone': phone,
                        'reason': 'Obuna belgilanmagan',
                        'expires_at': None
                    })
                elif expires_at < now:
                    # Obuna tugagan
                    exp_str, _ = human_left(expires_at)
                    unregistered_users.append({
                        'user_id': user_id,
                        'username': username,
                        'fullname': fullname,
                        'group_id': gid,
                        'phone': phone,
                        'reason': f'Obuna tugagan ({exp_str})',
                        'expires_at': expires_at
                    })
        
        # Natijalarni ko'rsatish
        if not unregistered_users:
            await processing_msg.edit_text("✅ Barcha guruh a'zolarida aktiv obuna bor!")
            return
        
        # Guruh bo'yicha guruhlash
        groups_dict = {}
        for user_info in unregistered_users:
            gid = user_info['group_id']
            if gid not in groups_dict:
                groups_dict[gid] = []
            groups_dict[gid].append(user_info)
        
        # Xabarni shakllantirish
        await processing_msg.delete()
        
        header = f"⚠️ <b>OBUNA BELGILANMAGANLAR</b>\n\nJami: {len(unregistered_users)} ta\n"
        await m.answer(header, parse_mode="HTML")
        
        for gid, users_list in groups_dict.items():
            gtitle = titles.get(gid, f"Guruh {gid}")
            lines = [f"🏷 <b>{gtitle}</b> — {len(users_list)} ta\n"]
            
            for i, user_info in enumerate(users_list[:40], start=1):
                name = user_info['fullname'] or f"User{user_info['user_id']}"
                safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
                username = user_info['username']
                user_tag = f"@{username}" if username else safe_name
                phone = user_info.get('phone', '')
                phone_str = f" 📞 {phone}" if phone else ""
                reason = user_info['reason']
                
                lines.append(f"{i}. {user_tag}{phone_str}")
                lines.append(f"   • ID: <code>{user_info['user_id']}</code>")
                lines.append(f"   • Holat: {reason}\n")
            
            if len(users_list) > 40:
                lines.append(f"... va yana {len(users_list) - 40} ta")
            
            await m.answer("\n".join(lines), parse_mode="HTML")
        
        # Yordam xabari
        help_text = (
            "💡 <b>Qanday qilib qoshish mumkin?</b>\n\n"
            "1️⃣ Har birini alohida:\n"
            "   <code>/add_user USER_ID now</code>\n\n"
            "2️⃣ Ularga bot orqali royxatdan otishni aytish:\n"
            "   Botga /start bosing va malumotlaringizni kiriting"
        )
        await m.answer(help_text, parse_mode="HTML")
        
        logger.info(f"Admin {m.from_user.id} checked unregistered users: {len(unregistered_users)} found")
        
    except Exception as e:
        logger.error(f"Error in cmd_unregistered: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("subscribers"))
async def cmd_subscribers(m: Message):
    """Barcha aktiv obunachilarni ko'rsatish - Telegram guruhdan haqiqiy ma'lumot."""
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    try:
        # Ruxsat etilgan guruhlarni olish
        allowed_groups = await get_allowed_groups(m.from_user.id)
        if not allowed_groups:
            return await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
        
        processing_msg = await m.answer("⏳ Guruh a'zolarini tekshiryapman...")
        
        now = int(datetime.utcnow().timestamp())
        titles = dict(await resolve_group_titles(allowed_groups))
        
        total_subscribers = 0
        
        for gid in allowed_groups:
            gtitle = titles.get(gid, f"Guruh {gid}")
            
            # Database'dagi userlar
            db_users = await all_members_of_group(gid)
            active_db_users = {
                uid: (username, full_name, exp, phone)
                for uid, username, full_name, exp, phone in db_users
                if exp and exp > now
            }
            
            # Telegram'dagi haqiqiy memberlar
            real_members = []
            for uid in active_db_users.keys():
                try:
                    member = await bot.get_chat_member(gid, uid)
                    if member.status in ["member", "administrator", "creator"]:
                        username, full_name, exp, phone = active_db_users[uid]
                        days_left = max(0, int((exp - now) / 86400))
                        real_members.append({
                            'uid': uid,
                            'username': username,
                            'fullname': full_name,
                            'phone': phone,
                            'exp': exp,
                            'days_left': days_left
                        })
                except Exception:
                    pass
            
            if not real_members:
                await m.answer(f"🏷 <b>{gtitle}</b>\n\n❌ Aktiv obunachi yo'q", parse_mode="HTML")
                continue
            
            # Sort by expiry (soonest first)
            real_members.sort(key=lambda x: x['exp'])
            
            total_subscribers += len(real_members)
            
            lines = [f"🏷 <b>{gtitle}</b> — {len(real_members)} ta obunachi\n"]
            
            for i, sub in enumerate(real_members[:50], start=1):
                name = sub['fullname'] or f"User{sub['uid']}"
                safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
                username = sub['username']
                user_tag = f"@{username}" if username else safe_name
                phone_str = f" 📞 {sub['phone']}" if sub['phone'] else ""
                days_str = f"{sub['days_left']} kun"
                
                lines.append(f"{i}. {user_tag}{phone_str}")
                lines.append(f"   • ID: <code>{sub['uid']}</code>")
                lines.append(f"   • ⏳ Qoldi: {days_str}\n")
            
            if len(real_members) > 50:
                lines.append(f"... va yana {len(real_members) - 50} ta")
            
            await m.answer("\n".join(lines), parse_mode="HTML")
        
        await processing_msg.delete()
        
        summary = (
            f"✅ <b>JAMI OBUNCHILAR: {total_subscribers} ta</b>\n\n"
            f"📚 Guruhlar soni: {len(allowed_groups)}\n"
            f"🔍 Faqat Telegram guruhda haqiqatan turgan va aktiv obunasi bor foydalanuvchilar ko'rsatildi."
        )
        await m.answer(summary, parse_mode="HTML")
        
        logger.info(f"Admin {m.from_user.id} checked subscribers: {total_subscribers} found")
        
    except Exception as e:
        logger.error(f"Error in cmd_subscribers: {e}")
        await m.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    # Ruxsat etilgan guruhlarni olish
    allowed_groups = await get_allowed_groups(m.from_user.id)
    if not allowed_groups:
        return await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
    
    now = int(datetime.utcnow().timestamp())
    
    # Faqat ruxsat etilgan guruhlardagi unique userlarni yig'amiz
    all_users = {}
    for gid in allowed_groups:
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
        f"📚 Guruhlar kesimi ({len(allowed_groups)} ta):"
    )
    await m.answer(header)
    
    titles = dict(await resolve_group_titles(allowed_groups))
    for gid in allowed_groups:
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
    if not await is_active_admin(m.from_user.id):
        return await m.answer(f"⛔ Bu buyruq faqat adminlar uchun.\n\nSizning ID: {m.from_user.id}")
    
    # Ruxsat etilgan guruhlarni olish
    allowed_groups = await get_allowed_groups(m.from_user.id)
    if not allowed_groups:
        return await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
    
    try:
        titles = dict(await resolve_group_titles(allowed_groups))
        total_groups = len(allowed_groups)
        
        await m.answer(f"📊 *Guruhlar statistikasi*\n\n🏫 Jami guruhlar: {total_groups}\n", parse_mode="Markdown")
        
        for idx, gid in enumerate(allowed_groups, start=1):
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
    if not await is_active_admin(m.from_user.id):
        return
    
    # Ruxsat etilgan guruhlarni olish
    allowed_groups = await get_allowed_groups(m.from_user.id)
    if not allowed_groups:
        await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
        return
    
    now = int(datetime.utcnow().timestamp())
    
    # Faqat ruxsat etilgan guruhlardagi unique userlarni yig'amiz
    all_users = {}
    for gid in allowed_groups:
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
        f"📚 Guruhlar kesimi ({len(allowed_groups)} ta):"
    )
    await m.answer(header)
    
    titles = dict(await resolve_group_titles(allowed_groups))
    for gid in allowed_groups:
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

@dp.message(F.text == "👥 Guruh o'quvchilari")
async def admin_group_users_button(m: Message):
    """Admin Guruh o'quvchilari tugmasi handleri."""
    if not await is_active_admin(m.from_user.id):
        return
    
    # Ruxsat etilgan guruhlarni olish
    allowed_groups = await get_allowed_groups(m.from_user.id)
    if not allowed_groups:
        await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
        return
    
    # Faqat ruxsat etilgan guruhlar ro'yxatini ko'rsatish
    titles = dict(await resolve_group_titles(allowed_groups))
    buttons = []
    for gid in allowed_groups:
        title = titles.get(gid, str(gid))
        buttons.append([InlineKeyboardButton(text=f"📚 {title}", callback_data=f"gusers_{gid}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await m.answer("👥 *Guruh tanlang*\n\nQaysi guruhdagi o'quvchilarni ko'rmoqchisiz?", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("group_users"))
async def cmd_group_users(m: Message):
    """Guruh o'quvchilarini ko'rish."""
    if not is_admin(m.from_user.id):
        return
    
    # Guruhlar ro'yxatini ko'rsatish
    titles = dict(await resolve_group_titles())
    buttons = []
    for gid in GROUP_IDS:
        title = titles.get(gid, str(gid))
        buttons.append([InlineKeyboardButton(text=f"📚 {title}", callback_data=f"gusers_{gid}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await m.answer("👥 <b>Guruh tanlang</b>\n\nQaysi guruhdagi o'quvchilarni ko'rmoqchisiz?", reply_markup=kb, parse_mode="HTML")

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

@dp.callback_query(F.data.startswith("gusers_"))
async def cb_group_users(c: CallbackQuery):
    """Tanlangan guruhdagi barcha o'quvchilarni ko'rsatish."""
    await c.answer()
    
    try:
        group_id = int(c.data.split("_")[1])
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, group_id):
            await c.message.answer("❌ Sizga bu guruhga ruxsat yo'q!")
            return
        
        # Guruh nomini olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        titles = dict(await resolve_group_titles(allowed_groups))
        group_name = titles.get(group_id, str(group_id))
        
        # Guruhdagi barcha o'quvchilarni olish
        users = await all_members_of_group(group_id)
        
        if not users:
            await c.message.edit_text(f"👥 <b>{group_name}</b>\n\n❌ Bu guruhda o'quvchilar yo'q.", parse_mode="HTML")
            return
        
        # Telegram API orqali guruhda turganlarni tekshirish
        real_members = []
        for uid, username, full_name, exp, phone in users:
            try:
                member = await bot.get_chat_member(group_id, uid)
                if member.status in ["member", "administrator", "creator"]:
                    real_members.append((uid, username, full_name, exp, phone))
            except Exception:
                pass
        
        if not real_members:
            await c.message.edit_text(f"👥 <b>{group_name}</b>\n\n❌ Bu guruhda hozirda o'quvchilar yo'q.", parse_mode="HTML")
            return
        
        # O'quvchilarni saralash - obuna sanasi bo'yicha
        users_sorted = sorted(real_members, key=lambda r: (r[3] or 0), reverse=True)
        
        # Xabarni shakllantirish
        await c.message.delete()
        
        header = f"👥 <b>{group_name}</b>\n📊 Jami: {len(users_sorted)} ta o'quvchi\n\n"
        await c.message.answer(header, parse_mode="HTML")
        
        # O'quvchilarni 20 tadan xabar yuborish
        MAX_PER_MSG = 20
        for i in range(0, len(users_sorted), MAX_PER_MSG):
            batch = users_sorted[i:i+MAX_PER_MSG]
            lines = []
            
            for j, (uid, username, full_name, exp, phone) in enumerate(batch, start=i+1):
                # Profil linki
                chat_link = f"<a href='tg://user?id={uid}'>{full_name or 'Nomsiz'}</a>"
                
                # Obuna sanasi
                if exp:
                    exp_date = (datetime.utcfromtimestamp(exp) + TZ_OFFSET).strftime("%Y-%m-%d")
                    now = int(datetime.utcnow().timestamp())
                    if exp > now:
                        days_left = (datetime.utcfromtimestamp(exp) + TZ_OFFSET).date() - (datetime.utcnow() + TZ_OFFSET).date()
                        status = f"✅ {exp_date} ({days_left.days} kun)"
                    else:
                        status = f"❌ {exp_date} (tugagan)"
                else:
                    status = "—"
                
                # Telefon
                phone_str = phone if phone else "—"
                
                lines.append(
                    f"{j}. {chat_link}\n"
                    f"   🆔 ID: <code>{uid}</code>\n"
                    f"   📞 Telefon: {phone_str}\n"
                    f"   ⏳ Obuna: {status}\n"
                )
            
            await c.message.answer("\n".join(lines), parse_mode="HTML")
            await asyncio.sleep(0.3)  # Telegram limitidan qochish
        
    except Exception as e:
        logger.error(f"Error in cb_group_users: {e}")
        await c.message.answer(f"Xatolik yuz berdi: {e}")

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

@dp.message(F.text == "💳 To'lovlar")
async def admin_payments_button(m: Message):
    """Admin To'lovlar tugmasi handleri."""
    if not await is_active_admin(m.from_user.id):
        return
    
    try:
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(m.from_user.id)
        
        # Pending va approved to'lovlar sonini olish (faqat ruxsat etilgan guruhlarga tegishli)
        async with db_pool.acquire() as conn:
            if is_super_admin(m.from_user.id):
                # Super admin barcha to'lovlarni ko'radi
                pending_count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
                approved_count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
            else:
                # Regular admin faqat o'z guruhlariga tegishli to'lovlarni ko'radi
                if not allowed_groups:
                    await m.answer("❌ Sizga hech qanday guruh tayinlanmagan!")
                    return
                
                # User_groups jadvalidan user'lar ro'yxatini olish
                user_ids_in_groups = await conn.fetch(
                    "SELECT DISTINCT user_id FROM user_groups WHERE group_id = ANY($1)", 
                    allowed_groups
                )
                user_ids = [row['user_id'] for row in user_ids_in_groups]
                
                if not user_ids:
                    pending_count = 0
                    approved_count = 0
                else:
                    pending_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM payments WHERE status = 'pending' AND user_id = ANY($1)", 
                        user_ids
                    )
                    approved_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM payments WHERE status = 'approved' AND user_id = ANY($1)", 
                        user_ids
                    )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⏳ Kutilayotganlar ({pending_count})", callback_data="payments_pending")],
            [InlineKeyboardButton(text=f"✅ Tasdiqlangan ({approved_count})", callback_data="payments_approved")]
        ])
        
        await m.answer(
            "💳 <b>To'lovlar</b>\n\n"
            "Qaysi birini ko'rmoqchisiz?",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in admin_payments_button: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.callback_query(F.data == "payments_pending")
async def cb_payments_pending(c: CallbackQuery):
    """Kutilayotgan to'lovlarni ko'rsatish."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    await c.answer()
    
    try:
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        
        if is_super_admin(c.from_user.id):
            # Super admin barcha to'lovlarni ko'radi
            pending_payments = await db_pool.fetch(
                "SELECT id, user_id, photo_file, created_at FROM payments WHERE status = 'pending' ORDER BY id ASC"
            )
        else:
            # Regular admin faqat o'z guruhlariga tegishli to'lovlarni ko'radi
            if not allowed_groups:
                await c.message.edit_text("❌ Sizga hech qanday guruh tayinlanmagan!")
                return
            
            # User_groups jadvalidan user'lar ro'yxatini olish
            user_ids_in_groups = await db_pool.fetch(
                "SELECT DISTINCT user_id FROM user_groups WHERE group_id = ANY($1)", 
                allowed_groups
            )
            user_ids = [row['user_id'] for row in user_ids_in_groups]
            
            if not user_ids:
                await c.message.edit_text("⏳ Hozircha kutilayotgan to'lovlar yo'q.")
                return
            
            pending_payments = await db_pool.fetch(
                "SELECT id, user_id, photo_file, created_at FROM payments WHERE status = 'pending' AND user_id = ANY($1) ORDER BY id ASC",
                user_ids
            )
        
        if not pending_payments:
            await c.message.edit_text("⏳ Hozircha kutilayotgan to'lovlar yo'q.")
            return
        
        await c.message.delete()
        
        for payment in pending_payments:
            pid = payment['id']
            uid = payment['user_id']
            photo_file_id = payment['photo_file']
            created_at = payment['created_at']
            
            user_row = await get_user(uid)
            if not user_row:
                continue
            
            # Telegram'dan profil nomini olish (har doim yangi)
            username, full_name = await fetch_user_profile(uid)
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            payment_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M") if created_at else "yo'q"
            
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            
            kb = approve_keyboard(pid)
            caption = (
                f"⏳ *Kutilayotgan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`\n"
                f"📅 Vaqt: {payment_date}"
            )
            
            await bot.send_photo(c.from_user.id, photo_file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cb_payments_pending: {e}")
        await bot.send_message(c.from_user.id, f"Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data == "payments_approved")
async def cb_payments_approved(c: CallbackQuery):
    """Tasdiqlangan to'lovlarni ko'rsatish."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    await c.answer()
    
    try:
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        
        if is_super_admin(c.from_user.id):
            # Super admin barcha to'lovlarni ko'radi
            approved_payments = await db_pool.fetch(
                "SELECT id, user_id, photo_file, created_at FROM payments WHERE status = 'approved' ORDER BY id DESC LIMIT 10"
            )
        else:
            # Regular admin faqat o'z guruhlariga tegishli to'lovlarni ko'radi
            if not allowed_groups:
                await c.message.edit_text("❌ Sizga hech qanday guruh tayinlanmagan!")
                return
            
            # User_groups jadvalidan user'lar ro'yxatini olish
            user_ids_in_groups = await db_pool.fetch(
                "SELECT DISTINCT user_id FROM user_groups WHERE group_id = ANY($1)", 
                allowed_groups
            )
            user_ids = [row['user_id'] for row in user_ids_in_groups]
            
            if not user_ids:
                await c.message.edit_text("✅ Hozircha tasdiqlangan to'lovlar yo'q.")
                return
            
            approved_payments = await db_pool.fetch(
                "SELECT id, user_id, photo_file, created_at FROM payments WHERE status = 'approved' AND user_id = ANY($1) ORDER BY id DESC LIMIT 10",
                user_ids
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
            phone = user_row[5] if len(user_row) > 5 else "yo'q"
            payment_date = (datetime.utcfromtimestamp(created_at) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M") if created_at else "yo'q"
            
            # Guruhlarni olish
            groups_data = await db_pool.fetch(
                "SELECT group_id FROM user_groups WHERE user_id = $1", uid
            )
            group_names = [titles.get(row['group_id'], str(row['group_id'])) for row in groups_data]
            groups_str = ", ".join(group_names) if group_names else "yo'q"
            
            # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
            chat_link = f"📧 [{username}](tg://user?id={uid})" if username else f"📧 [Chat ochish](tg://user?id={uid})"
            caption = (
                f"✅ *Tasdiqlangan to'lov*\n\n"
                f"👤 {full_name}\n"
                f"{chat_link}\n"
                f"📞 Telefon: {phone}\n"
                f"🏫 Guruhlar: {groups_str}\n"
                f"🆔 User ID: `{uid}`\n"
                f"💳 Payment ID: `{pid}`\n"
                f"📅 Vaqt: {payment_date}"
            )
            
            await bot.send_photo(c.from_user.id, photo_file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in cb_payments_approved: {e}")
        await bot.send_message(c.from_user.id, f"Xatolik yuz berdi: {str(e)}")

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
            reply_markup=admin_reply_keyboard(m.from_user.id),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in admin_cleanup_button: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.message(F.text == "➕ Guruh qo'shish")
async def admin_add_group_button(m: Message):
    """Admin Guruh qo'shish tugmasi handleri."""
    if not is_super_admin(m.from_user.id):
        return await m.answer("⛔ Bu tugma faqat super adminlar uchun.")
    
    await m.answer(
        "➕ <b>Guruh qo'shish</b>\n\n"
        "Guruh qo'shish uchun quyidagi buyruqni yuboring:\n\n"
        "<code>/add_group GURUH_ID [Guruh nomi]</code>\n\n"
        "<b>Misol:</b>\n"
        "<code>/add_group -1001234567890 Python kursi</code>\n\n"
        "💡 <b>Guruh ID'ni qanday topish mumkin?</b>\n"
        "1️⃣ Guruhga botni qo'shing\n"
        "2️⃣ Guruhda /myid buyrug'ini yuboring\n"
        "3️⃣ Bot guruh ID'ni ko'rsatadi",
        parse_mode="HTML"
    )

@dp.message(F.text == "📋 Guruhlar ro'yxati")
async def admin_groups_list_button(m: Message):
    """Guruhlar ro'yxatini ko'rsatish va boshqarish."""
    if not await is_active_admin(m.from_user.id):
        return await m.answer("⛔ Bu tugma faqat adminlar uchun.")
    
    try:
        # Faqat ruxsat etilgan guruhlarni olish
        allowed_groups = await get_allowed_groups(m.from_user.id)
        
        if not allowed_groups:
            return await m.answer("📋 Sizda hech qanday guruh yo'q.")
        
        # Guruh ma'lumotlarini olish
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT group_id, name, type, created_at 
                FROM groups 
                WHERE group_id = ANY($1::bigint[])
                ORDER BY created_at DESC
            """, allowed_groups)
        
        if not rows:
            return await m.answer("📋 Guruhlar ro'yxati bo'sh.")
        
        # Inline keyboard yaratish - har bir guruh uchun o'chirish tugmasi
        keyboard = []
        for row in rows:
            gid = row['group_id']
            name = row['name']
            gtype = row['type']
            
            # Guruh turi emoji
            type_emoji = "📢" if gtype == "channel" else "👥"
            
            # Har bir guruh uchun 2 ta tugma: Ma'lumot va O'chirish
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{type_emoji} {name}",
                    callback_data=f"group_info:{gid}"
                ),
                InlineKeyboardButton(
                    text="🗑 O'chirish",
                    callback_data=f"group_delete:{gid}"
                )
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await m.answer(
            f"📋 <b>Guruhlar ro'yxati</b>\n\n"
            f"📊 Jami: {len(rows)} ta guruh/kanal\n\n"
            f"💡 Guruhni o'chirish uchun 🗑 tugmasini bosing.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in admin_groups_list_button: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.message(F.text == "👥 Adminlar")
async def admin_list_button(m: Message):
    """Admin Adminlar ro'yxati tugmasi handleri."""
    if not is_super_admin(m.from_user.id):
        return await m.answer("⛔ Bu tugma faqat super adminlar uchun.")
    
    # /admins buyrug'ini chaqirish
    await cmd_admins(m)

@dp.message(F.text == "💳 To'lov ma'lumoti")
async def admin_edit_payment_button(m: Message):
    """Admin To'lov ma'lumotini tahrirlash tugmasi handleri."""
    if not await is_active_admin(m.from_user.id):
        return
    
    try:
        # Hozirgi to'lov ma'lumotlarini olish
        payment_settings = await get_payment_settings()
        
        if payment_settings:
            bank = payment_settings['bank_name']
            card = payment_settings['card_number']
            amount = payment_settings['amount']
            additional = payment_settings.get('additional_info', '') or 'Yo\'q'
            
            current_info = (
                f"💳 <b>Hozirgi to'lov ma'lumotlari:</b>\n\n"
                f"🏦 Bank: {bank}\n"
                f"💰 Summa: {amount}\n"
                f"📋 Karta raqam: {card}\n"
                f"📝 Qo'shimcha: {additional}"
            )
        else:
            current_info = "💳 <b>To'lov ma'lumotlari hali kiritilmagan.</b>"
        
        await m.answer(
            f"{current_info}\n\n"
            f"✏️ <b>To'lov ma'lumotlarini yangilash:</b>\n\n"
            f"Quyidagi buyruqni yuboring:\n"
            f"<code>/edit_payment</code>\n\n"
            f"📝 Yoki to'g'ridan-to'g'ri /edit_payment buyrug'ini bosing.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in admin_edit_payment_button: {e}")
        await m.answer("Xatolik yuz berdi")

@dp.message(F.text == "📝 Shartnoma tahrirlash")
async def admin_edit_contract_button(m: Message):
    """Admin Shartnoma tahrirlash tugmasi handleri."""
    if not is_admin(m.from_user.id):
        return
    
    try:
        # Hozirgi shartnoma matnini olish
        contract_text = await get_contract_template()
        
        # Shartnoma matnini .txt file sifatida yuborish
        txt_bytes = contract_text.encode('utf-8')
        txt_file = BufferedInputFile(txt_bytes, filename="shartnoma.txt")
        
        await m.answer_document(
            txt_file,
            caption=(
                "📄 <b>Hozirgi shartnoma matni</b>\n\n"
                "📝 Shartnomani tahrirlash uchun:\n"
                "1️⃣ Yangi matnni xabar sifatida yuboring\n"
                "2️⃣ Yoki yangi .txt faylini yuklang\n\n"
                "💡 Shablonlar:\n"
                "• <code>{name}</code> - To'liq ism\n"
                "• <code>{phone}</code> - Telefon raqam\n"
                "• <code>{date}</code> - Sana"
            ),
            parse_mode="HTML"
        )
        
        # Tahrirlash rejimini yoqish
        WAIT_CONTRACT_EDIT.add(m.from_user.id)
        
    except Exception as e:
        logger.error(f"Error in admin_edit_contract_button: {e}")
        await m.answer(f"❌ Xatolik: {e}")

@dp.message(F.text)
async def on_admin_date_handler(m: Message):
    # Shartnoma matnini tahrirlash (admin)
    if m.from_user.id in WAIT_CONTRACT_EDIT:
        try:
            new_contract_text = (m.text or "").strip()
            
            if len(new_contract_text) < 50:
                return await m.answer("❗ Shartnoma matni juda qisqa. Iltimos, to'liq matn kiriting (kamida 50 ta belgi)")
            
            # Shartnoma matnini yangilash
            await update_contract_template(new_contract_text)
            WAIT_CONTRACT_EDIT.discard(m.from_user.id)
            
            await m.answer(
                "✅ <b>Shartnoma matni yangilandi!</b>\n\n"
                f"📝 Uzunligi: {len(new_contract_text)} belgi\n\n"
                "Endi yangi ro'yxatdan o'tuvchilar bu shartnomani ko'rishadi.",
                parse_mode="HTML"
            )
            
            logger.info(f"Admin {m.from_user.id} updated contract template")
            
        except Exception as e:
            logger.error(f"Error updating contract: {e}")
            await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    # To'lov ma'lumotlarini tahrirlash (admin)
    if m.from_user.id in WAIT_PAYMENT_EDIT:
        try:
            lines = (m.text or "").strip().split('\n')
            
            if len(lines) < 3:
                return await m.answer(
                    "❗ <b>Format noto'g'ri!</b>\n\n"
                    "Quyidagi formatda kiriting:\n\n"
                    "<code>Bank nomi\n"
                    "Karta raqam\n"
                    "Summa\n"
                    "Qo'shimcha (ixtiyoriy)</code>",
                    parse_mode="HTML"
                )
            
            bank_name = lines[0].strip()
            card_number = lines[1].strip()
            amount = lines[2].strip()
            additional_info = lines[3].strip() if len(lines) > 3 else ""
            
            if not bank_name or not card_number or not amount:
                return await m.answer("❗ Bank nomi, karta raqam va summa bo'sh bo'lmasligi kerak!")
            
            # To'lov ma'lumotlarini yangilash
            await update_payment_settings(bank_name, card_number, amount, additional_info, m.from_user.id)
            WAIT_PAYMENT_EDIT.discard(m.from_user.id)
            
            await m.answer(
                "✅ <b>To'lov ma'lumotlari yangilandi!</b>\n\n"
                f"🏦 Bank: {bank_name}\n"
                f"💰 Summa: {amount}\n"
                f"📋 Karta: {card_number}\n"
                + (f"📝 Qo'shimcha: {additional_info}\n" if additional_info else "") +
                "\nEndi o'quvchilar yangi to'lov ma'lumotlarini ko'rishadi.",
                parse_mode="HTML"
            )
            
            logger.info(f"Admin {m.from_user.id} updated payment settings")
            
        except Exception as e:
            logger.error(f"Error updating payment settings: {e}")
            await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    # Ism-familiya qabul qilish (payment-first registration - guruh a'zoligi shart emas)
    if m.from_user.id in WAIT_FULLNAME_FOR:
        try:
            fullname = (m.text or "").strip()
            if len(fullname) < 3:
                return await m.answer("❗ Iltimos, to'liq ismingizni kiriting (kamida 3 ta harf)")
            
            # Ism-familiyani saqlash
            await update_user_fullname(m.from_user.id, fullname)
            WAIT_FULLNAME_FOR.discard(m.from_user.id)
            WAIT_CONTRACT_CONFIRM.add(m.from_user.id)
            
            # Shartnoma matnini olish va PDF yaratish
            contract_text = await get_contract_template()
            now_str = (datetime.utcnow() + TZ_OFFSET).strftime("%Y-%m-%d")
            
            # Shartnomaga ism va sanani qo'shish
            stamped_contract = f"{contract_text}\n\n{'='*50}\nO'quvchi: {fullname}\nSana: {now_str}"
            
            # PDF yaratish
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                pdf_buf = io.BytesIO()
                pdf_buf.name = "shartnoma.pdf"
                c = canvas.Canvas(pdf_buf, pagesize=A4)
                width, height = A4
                y = height - 40
                for line in stamped_contract.splitlines():
                    c.drawString(40, y, line[:110])
                    y -= 14
                    if y < 40:
                        c.showPage()
                        y = height - 40
                c.save()
                pdf_buf.seek(0)
                
                pdf_file = BufferedInputFile(pdf_buf.read(), filename="shartnoma.pdf")
            except Exception as e:
                logger.warning(f"Failed to create PDF contract: {e}")
                pdf_file = None
            
            # Shartnoma tasdiqlash tugmalari
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Tasdiqlayman", callback_data="contract_agree")],
                [InlineKeyboardButton(text="❌ Rad etaman", callback_data="contract_decline")]
            ])
            
            # Shartnomani yuborish
            if pdf_file:
                await m.answer_document(
                    pdf_file,
                    caption=(
                        f"📄 <b>SHARTNOMA</b>\n\n"
                        f"👤 O'quvchi: {fullname}\n"
                        f"📅 Sana: {now_str}\n\n"
                        f"Iltimos, shartnomani o'qing va tasdiqlang."
                    ),
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                # PDF yaratilmasa, matn shaklida yuborish
                short_contract = contract_text[:4000]  # Telegram limit
                await m.answer(
                    f"📄 <b>SHARTNOMA</b>\n\n{short_contract}\n\n"
                    f"{'='*30}\n"
                    f"👤 O'quvchi: {fullname}\n"
                    f"📅 Sana: {now_str}",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            
            logger.info(f"User {m.from_user.id} provided fullname: {fullname}, now waiting for contract confirmation")
            
        except Exception as e:
            logger.error(f"Error processing fullname: {e}")
            await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    # Sana kiritish (to'lov tasdiqlash yoki registration uchun)
    if m.from_user.id in WAIT_DATE_FOR:
        try:
            raw = (m.text or "").strip().replace("/", "-")
            if not DATE_RE.match(raw):
                return await m.answer("❗ Format noto'g'ri. To'g'ri ko'rinish: 2025-10-01")
            try:
                start_dt = datetime.strptime(raw, "%Y-%m-%d")
            except Exception:
                return await m.answer("❗ Sana tushunilmadi. Misol: 2025-10-01")
            
            id_value = WAIT_DATE_FOR.pop(m.from_user.id, None)
            if not id_value:
                return await m.answer("Sessiya topilmadi.")
            
            # Payment ID yoki User ID ekanligini tekshirish
            payment_row = await get_payment(id_value)
            
            if payment_row:
                # Bu to'lov tasdiqlash
                iso = start_dt.isoformat()
                await m.answer("✅ Sana qabul qilindi.\nEndi guruh(lar)ga qo'shish usulini tanlang:", reply_markup=multi_select_entry_kb(id_value, with_date_iso=iso))
            else:
                # Bu registration tasdiqlash
                user_id = id_value
                expires_at = int((start_dt + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
                
                # User ma'lumotlarini olish
                user_row = await get_user(user_id)
                username, fullname = await fetch_user_profile(user_id)
                phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
                
                # Birinchi guruhga qo'shish
                if GROUP_IDS:
                    primary_gid = GROUP_IDS[0]
                    await upsert_user(uid=user_id, username=username, full_name=fullname, group_id=primary_gid, expires_at=expires_at)
                    
                    human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
                    human_start = (start_dt + TZ_OFFSET).strftime("%Y-%m-%d")
                    
                    # User'ga xabar
                    try:
                        await bot.send_message(
                            user_id,
                            f"✅ *Tabriklaymiz! Ro'yxatdan o'tdingiz!*\n\n"
                            f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun\n"
                            f"⏳ Tugash sanasi: {human_exp}\n\n"
                            f"🎓 Darslarni yaxshi o'zlashtirishingizni tilaymiz!",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to notify user {user_id}: {e}")
                    
                    # Admin'ga xabar
                    await m.answer(
                        f"✅ *TASDIQLANDI*\n\n"
                        f"👤 {fullname}\n"
                        f"📞 Telefon: {phone}\n"
                        f"📅 Obuna: {human_start} dan {SUBSCRIPTION_DAYS} kun\n"
                        f"⏳ Tugash: {human_exp}",
                        parse_mode="Markdown"
                    )
                    
                    logger.info(f"Registration approved with custom date for user {user_id} by admin {m.from_user.id}")
                else:
                    await m.answer("❗ Guruhlar topilmadi")
                    
        except Exception as e:
            logger.error(f"Error in on_admin_date_handler: {e}")
            await m.answer("Xatolik yuz berdi")
        return
    
    if m.from_user.id in WAIT_CONTACT_FOR:
        # Payment-first registration - guruh a'zoligi shart emas
        phone_pattern = re.compile(r"^\+?\d{9,15}$")
        if phone_pattern.match((m.text or "").strip()):
            try:
                phone = m.text.strip()
                await update_user_phone(m.from_user.id, phone)
                WAIT_CONTACT_FOR.discard(m.from_user.id)
                WAIT_PAYMENT_PHOTO.add(m.from_user.id)
                
                # To'lov ma'lumotini database'dan olish
                payment_settings = await get_payment_settings()
                
                if payment_settings:
                    # Database'dan to'lov ma'lumotlari
                    bank = payment_settings['bank_name']
                    card = payment_settings['card_number']
                    amount = payment_settings['amount']
                    additional = payment_settings.get('additional_info', '')
                    
                    payment_info = (
                        f"💳 <b>To'lov ma'lumoti:</b>\n\n"
                        f"🏦 Bank: {bank}\n"
                        f"💰 Summa: {amount}\n"
                        f"📋 Karta raqam: {card}\n"
                    )
                    
                    if additional:
                        payment_info += f"\n📝 {additional}\n"
                else:
                    # Agar database'da yo'q bo'lsa, env var yoki default
                    env_payment_info = os.getenv("PAYMENT_INFO", "")
                    
                    if env_payment_info:
                        payment_info = env_payment_info
                    else:
                        # Default xabar
                        payment_info = (
                            "💳 <b>To'lov ma'lumoti:</b>\n\n"
                            "🏦 Bank: Xalq Banki\n"
                            "💰 Summa: 100,000 so'm\n"
                            "📋 Karta raqam: 8600 **** **** ****\n"
                        )
                
                await m.answer(
                    f"{payment_info}\n\n"
                    "📸 <b>To'lov chekini yuklang:</b>\n\n"
                    "To'lov qilganingizdan so'ng chekni surat qilib yuboring.\n"
                    "Admin tekshirib, tasdiqlaydi.",
                    parse_mode="HTML"
                )
                
                logger.info(f"Payment info sent to user {m.from_user.id}, waiting for photo")
                
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
        WAIT_PAYMENT_PHOTO.add(m.from_user.id)
        
        # To'lov ma'lumotini database'dan olish
        payment_settings = await get_payment_settings()
        
        if payment_settings:
            # Database'dan to'lov ma'lumotlari
            bank = payment_settings['bank_name']
            card = payment_settings['card_number']
            amount = payment_settings['amount']
            additional = payment_settings.get('additional_info', '')
            
            payment_info = (
                f"💳 <b>To'lov ma'lumoti:</b>\n\n"
                f"🏦 Bank: {bank}\n"
                f"💰 Summa: {amount}\n"
                f"📋 Karta raqam: {card}\n"
            )
            
            if additional:
                payment_info += f"\n📝 {additional}\n"
        else:
            # Agar database'da yo'q bo'lsa, env var yoki default
            env_payment_info = os.getenv("PAYMENT_INFO", "")
            
            if env_payment_info:
                payment_info = env_payment_info
            else:
                # Default xabar
                payment_info = (
                    "💳 <b>To'lov ma'lumoti:</b>\n\n"
                    "🏦 Bank: Xalq Banki\n"
                    "💰 Summa: 100,000 so'm\n"
                    "📋 Karta raqam: 8600 **** **** ****\n"
                )
        
        # User'ga to'lov ma'lumoti va chek yuborish ko'rsatmasi
        await m.answer(
            f"✅ <b>Telefon raqam qabul qilindi!</b>\n\n"
            f"{payment_info}\n\n"
            f"📸 <b>To'lov chekini yuboring!</b>\n\n"
            f"⏳ To'lovni amalga oshirgandan so'ng, <b>chek rasmini</b> yuboring.",
            parse_mode="HTML"
        )
        
        logger.info(f"User {m.from_user.id} completed phone registration, waiting for payment photo")
        
    except Exception as e:
        logger.error(f"Error in on_contact: {e}")
        await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

@dp.message(F.document)
async def on_document(m: Message):
    """Document (fayl) qabul qilish - shartnoma matni uchun."""
    # Shartnoma matnini .txt file orqali qabul qilish
    if m.from_user.id in WAIT_CONTRACT_EDIT:
        try:
            document = m.document
            
            # Faqat .txt fayllarni qabul qilish
            if not document.file_name.endswith('.txt'):
                return await m.answer("❗ Faqat .txt fayllarni yuklang")
            
            # Faylni yuklab olish
            file = await bot.get_file(document.file_id)
            file_bytes = await bot.download_file(file.file_path)
            
            # Matnni o'qish
            new_contract_text = file_bytes.read().decode('utf-8').strip()
            
            if len(new_contract_text) < 50:
                return await m.answer("❗ Shartnoma matni juda qisqa. Iltimos, to'liq matn kiriting (kamida 50 ta belgi)")
            
            # Shartnoma matnini yangilash
            await update_contract_template(new_contract_text)
            WAIT_CONTRACT_EDIT.discard(m.from_user.id)
            
            await m.answer(
                "✅ <b>Shartnoma matni yangilandi!</b>\n\n"
                f"📝 Uzunligi: {len(new_contract_text)} belgi\n\n"
                "Endi yangi ro'yxatdan o'tuvchilar bu shartnomani ko'rishadi.",
                parse_mode="HTML"
            )
            
            logger.info(f"Admin {m.from_user.id} updated contract template via file")
            
        except Exception as e:
            logger.error(f"Error processing contract file: {e}")
            await m.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return

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
    # To'lov cheki kutilayotganlarni tekshirish
    if m.from_user.id not in WAIT_PAYMENT_PHOTO:
        return
    
    try:
        WAIT_PAYMENT_PHOTO.discard(m.from_user.id)
        
        # To'lovni database'ga qo'shish
        pid = await add_payment(m, m.photo[-1].file_id)
        await m.answer(
            "✅ <b>To'lov cheki qabul qilindi!</b>\n\n"
            "⏳ Admin tekshiradi va tasdiqlashini kuting.\n"
            "Tez orada xabar beramiz!",
            parse_mode="HTML"
        )
        
        # User ma'lumotlarini olish
        user_row = await get_user(m.from_user.id)
        phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
        fullname = user_row[4] if user_row and len(user_row) > 4 else "Noma'lum"
        
        # Telegram'dan profil nomini olish (har doim yangi)
        username, full_name = await fetch_user_profile(m.from_user.id)
        # Username bor bo'lsa username ko'rsatamiz, yo'qsa "Chat ochish" - ikkalasi ham link
        chat_link = f"📧 [{username}](tg://user?id={m.from_user.id})" if username else f"📧 [Chat ochish](tg://user?id={m.from_user.id})"
        
        kb = approve_keyboard(pid)
        caption = (
            f"🧾 *Yangi to'lov cheki*\n\n"
            f"👤 {fullname}\n"
            f"{chat_link}\n"
            f"📱 Telefon: {phone}\n"
            f"🆔 ID: `{m.from_user.id}`\n"
            f"💳 Payment ID: `{pid}`\n"
            f"📅 Vaqt: {(datetime.utcnow() + TZ_OFFSET).strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Admin xabarlarini kuzatish uchun
        if pid not in ADMIN_MESSAGES:
            ADMIN_MESSAGES[pid] = []
        
        # Barcha adminlarga xabar yuborish
        for aid in ADMIN_IDS:
            try:
                msg = await bot.send_photo(aid, m.photo[-1].file_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
                ADMIN_MESSAGES[pid].append(msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to send payment notification to admin {aid}: {e}")
        
        logger.info(f"User {m.from_user.id} uploaded payment photo, payment ID: {pid}")
        
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1])
        with_date_iso = None
        if len(parts) >= 4 and parts[2] == "with_date":
            with_date_iso = parts[3]
        
        # Faqat ruxsat etilgan guruhlarni olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        groups = await resolve_group_titles(allowed_groups)
        
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1])
        with_date_iso = None
        if len(parts) >= 4 and parts[2] == "with_date":
            with_date_iso = parts[3]
        
        # Faqat ruxsat etilgan guruhlarni olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        groups = await resolve_group_titles(allowed_groups)
        
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        pid = int(parts[1]); gid = int(parts[2])
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, gid):
            return await c.answer("❌ Sizga bu guruhga ruxsat yo'q!", show_alert=True)
        
        state = MULTI_PICK.get(c.from_user.id)
        if not state or state.get("pid") != pid:
            return await c.answer("Sessiya topilmadi. Qaytadan oching.", show_alert=True)
        sel: set = state["selected"]
        if gid in sel:
            sel.remove(gid)
        else:
            sel.add(gid)
        
        # Faqat ruxsat etilgan guruhlarni olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        groups = await resolve_group_titles(allowed_groups)
        
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
    if not await is_active_admin(c.from_user.id):
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
        
        # Tanlangan barcha guruhlarning ruxsatini tekshirish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        for gid in selected:
            if gid not in allowed_groups:
                return await c.answer(f"❌ Sizga guruh {gid}ga ruxsat yo'q!", show_alert=True)
        
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        try:
            pid = int(parts[1])
            gid = int(parts[2])
        except Exception:
            return await c.answer("Xatolik: noto'g'ri callback.", show_alert=True)
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, gid):
            return await c.answer("❌ Sizga bu guruhga ruxsat yo'q!", show_alert=True)
        
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

@dp.callback_query(F.data.startswith("group_info:"))
async def cb_group_info(c: CallbackQuery):
    """Guruh/kanal ma'lumotlarini ko'rsatish."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("⛔ Faqat adminlar uchun", show_alert=True)
    
    try:
        gid = int(c.data.split(":")[1])
        
        # Guruh ma'lumotlarini olish
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT group_id, name, type, created_at 
                FROM groups 
                WHERE group_id = $1
            """, gid)
            
            if not row:
                return await c.answer("Guruh topilmadi", show_alert=True)
            
            # Guruh statistikasini hisoblash
            user_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT user_id) 
                FROM user_groups 
                WHERE group_id = $1
            """, gid)
            
            active_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT user_id) 
                FROM user_groups 
                WHERE group_id = $1 AND expires_at > $2
            """, gid, int(datetime.utcnow().timestamp()))
        
        # Guruh turini aniqlash
        gtype = row['type']
        type_emoji = "📢" if gtype == "channel" else "👥"
        type_name = "Kanal" if gtype == "channel" else "Guruh"
        
        # Yaratilgan sanani formatlash
        created_date = (datetime.utcfromtimestamp(row['created_at']) + TZ_OFFSET).strftime("%Y-%m-%d %H:%M")
        
        info_text = (
            f"{type_emoji} <b>{row['name']}</b>\n\n"
            f"🆔 ID: <code>{gid}</code>\n"
            f"📊 Tur: {type_name}\n"
            f"📅 Qo'shildi: {created_date}\n\n"
            f"👥 Jami o'quvchilar: {user_count}\n"
            f"✅ Faol obunalar: {active_count}\n"
            f"❌ Tugagan: {user_count - active_count}"
        )
        
        await c.answer()
        await c.message.answer(info_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in cb_group_info: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("group_delete:"))
async def cb_group_delete(c: CallbackQuery):
    """Guruh/kanalni o'chirish (tasdiqlash bilan)."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("⛔ Faqat adminlar uchun", show_alert=True)
    
    try:
        gid = int(c.data.split(":")[1])
        
        # Guruh ma'lumotlarini olish
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT group_id, name, type 
                FROM groups 
                WHERE group_id = $1
            """, gid)
            
            if not row:
                return await c.answer("Guruh topilmadi", show_alert=True)
            
            # Foydalanuvchilar sonini hisoblash
            user_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT user_id) 
                FROM user_groups 
                WHERE group_id = $1
            """, gid)
        
        # Tasdiqlash tugmalari
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"group_delete_confirm:{gid}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="group_delete_cancel")
            ]
        ])
        
        gtype = row['type']
        type_name = "kanalni" if gtype == "channel" else "guruhni"
        
        await c.message.edit_text(
            f"⚠️ <b>Ogohlantirish!</b>\n\n"
            f"Siz <b>{row['name']}</b> {type_name} o'chirmoqchisiz.\n\n"
            f"👥 Bu guruhda {user_count} ta o'quvchi bor.\n\n"
            f"🗑 O'chirilgandan keyin:\n"
            f"• Guruh ro'yxatdan olib tashlanadi\n"
            f"• O'quvchilar ma'lumotlari saqlanadi\n"
            f"• Yangi to'lovlar qabul qilinmaydi\n\n"
            f"Davom etasizmi?",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_group_delete: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("group_delete_confirm:"))
async def cb_group_delete_confirm(c: CallbackQuery):
    """Guruh o'chirishni tasdiqlash."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("⛔ Faqat adminlar uchun", show_alert=True)
    
    try:
        gid = int(c.data.split(":")[1])
        
        # Guruh nomini olish
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM groups WHERE group_id = $1", gid)
            if not row:
                return await c.answer("Guruh topilmadi", show_alert=True)
            
            group_name = row['name']
            
            # Guruhni o'chirish
            await conn.execute("DELETE FROM groups WHERE group_id = $1", gid)
            
            # Admin_groups jadvalidan ham o'chirish
            await conn.execute("DELETE FROM admin_groups WHERE group_id = $1", gid)
        
        # GROUP_IDS global o'zgaruvchisidan ham o'chirish
        global GROUP_IDS
        if gid in GROUP_IDS:
            GROUP_IDS.remove(gid)
        
        await c.message.edit_text(
            f"✅ <b>Guruh o'chirildi!</b>\n\n"
            f"📋 Nom: {group_name}\n"
            f"🆔 ID: <code>{gid}</code>\n\n"
            f"Guruh muvaffaqiyatli o'chirildi.",
            parse_mode="HTML"
        )
        await c.answer("✅ Guruh o'chirildi")
        
        logger.info(f"Group {gid} ({group_name}) deleted by admin {c.from_user.id}")
    except Exception as e:
        logger.error(f"Error in cb_group_delete_confirm: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "group_delete_cancel")
async def cb_group_delete_cancel(c: CallbackQuery):
    """Guruh o'chirishni bekor qilish."""
    await c.message.edit_text(
        "❌ Guruh o'chirish bekor qilindi.",
        parse_mode="HTML"
    )
    await c.answer("Bekor qilindi")

_WARNED_CACHE: dict[tuple[int, int, str], int] = {}
_REMOVED_GROUPS_CACHE: set[int] = set()  # O'chirilgan guruhlar cache'i

async def handle_missing_chat(group_id: int, reason: str = "chat not found"):
    """Agar guruh topilmasa, database'dan avtomatik o'chirish."""
    try:
        # Agar bu guruh allaqachon o'chirilgan bo'lsa, qayta ishlamaslik
        if group_id in _REMOVED_GROUPS_CACHE:
            logger.debug(f"Group {group_id} already processed for removal, skipping")
            return
        
        # Cache'ga qo'shamiz - bir marta ishlasin
        _REMOVED_GROUPS_CACHE.add(group_id)
        
        logger.error(f"Group {group_id} not found in Telegram ({reason}) - removing from database")
        
        # Guruh nomini olish (log uchun)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM groups WHERE group_id = $1", group_id)
            group_name = row['name'] if row else str(group_id)
            
            # Database'dan o'chirish
            await conn.execute("DELETE FROM groups WHERE group_id = $1", group_id)
            await conn.execute("DELETE FROM user_groups WHERE group_id = $1", group_id)
        
        # Global o'zgaruvchilardan o'chirish
        global GROUP_IDS
        if group_id in GROUP_IDS:
            GROUP_IDS.remove(group_id)
        
        # Cache'larni tozalash
        keys_to_remove = [k for k in _WARNED_CACHE.keys() if k[1] == group_id]
        for k in keys_to_remove:
            del _WARNED_CACHE[k]
        
        logger.info(f"Successfully removed invalid group {group_id} ({group_name}) from database")
        
        # Super adminlarga FAQAT BIR MARTA xabar yuborish
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ <b>Guruh avtomatik o'chirildi</b>\n\n"
                    f"📋 Nom: {group_name}\n"
                    f"🆔 ID: <code>{group_id}</code>\n"
                    f"❌ Sabab: {reason}\n\n"
                    f"Bot guruhga kirib bo'lmadi yoki guruh o'chirilgan.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error in handle_missing_chat for group {group_id}: {e}")

async def _warn_and_buttons(uid: int, gid: int, exp_at: int, reason: str):
    now_ts = int(datetime.utcnow().timestamp())
    key = (uid, gid or 0, reason)
    last = _WARNED_CACHE.get(key, 0)
    if now_ts - last < 3600:
        return
    
    # 1. User guruhda hozir borligini tekshirish
    try:
        member = await bot.get_chat_member(gid, uid)
        if member.status not in ("member", "administrator", "creator"):
            # User guruhda emas - eslatma yubormaymiz
            logger.info(f"User {uid} is not in group {gid} (status: {member.status}), skipping warning")
            return
        
        # 2. User admin yoki creator bo'lsa, eslatma yubormaymiz
        if member.status in ("administrator", "creator"):
            logger.info(f"User {uid} is admin/creator in group {gid}, skipping warning")
            return
    except Exception as e:
        error_msg = str(e)
        # Agar guruh topilmasa, database'dan avtomatik o'chirish
        if "chat not found" in error_msg.lower() or "chat_not_found" in error_msg.lower():
            await handle_missing_chat(gid, error_msg)
            return
        # Boshqa xatoliklar uchun - eslatma yubormaymiz
        logger.warning(f"Failed to check membership for user {uid} in group {gid}: {e}")
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
    
    # 3. Faqat bu guruhga access bo'lgan adminlarga yuborish
    async with db_pool.acquire() as conn:
        admin_list = await conn.fetch("""
            SELECT DISTINCT a.user_id 
            FROM admins a
            LEFT JOIN admin_groups ag ON a.user_id = ag.admin_id
            WHERE a.active = TRUE
              AND (a.role = 'super_admin' OR ag.group_id = $1)
        """, gid)
        
        for admin_row in admin_list:
            aid = admin_row['user_id']
            try:
                await bot.send_message(aid, msg, reply_markup=kb, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Failed to send warning to admin {aid}: {e}")

async def send_expiry_warnings():
    """2 kun ichida muddati tugaydigan adminlarga eslatma yuborish"""
    try:
        async with db_pool.acquire() as conn:
            now = int(datetime.utcnow().timestamp())
            warning_threshold = now + (2 * 24 * 60 * 60)  # 2 kun
            
            # 2 kun ichida expire bo'ladigan adminlarni topish
            expiring_admins = await conn.fetch("""
                SELECT user_id, name, expires_at, tariff, last_warning_sent_at FROM admins
                WHERE active = TRUE 
                  AND expires_at IS NOT NULL 
                  AND expires_at > $1 
                  AND expires_at < $2
            """, now, warning_threshold)
            
            for row in expiring_admins:
                uid = row['user_id']
                name = row['name']
                expires_at = row['expires_at']
                tariff = row['tariff'] or 'custom'
                last_warning = row['last_warning_sent_at']
                
                # Agar oxirgi warning 24 soatdan eski bo'lsa yoki hech yuborilmagan bo'lsa
                if last_warning is None or (now - last_warning) > (24 * 60 * 60):
                    exp_str, days_left = human_left(expires_at)
                    
                    # Admin'ga eslatma yuborish
                    try:
                        tariff_info = TARIFFS.get(tariff, {})
                        await bot.send_message(
                            uid,
                            f"⏰ <b>Admin muddatingiz tugashiga {days_left} kun qoldi!</b>\n\n"
                            f"📅 Tugash sanasi: {exp_str}\n"
                            f"📦 Hozirgi tarif: {tariff_info.get('name', tariff)}\n\n"
                            f"Davom ettirish uchun super admin bilan bog'laning yoki to'lov qiling.",
                            parse_mode="HTML"
                        )
                        logger.info(f"Sent expiry warning to admin {uid} ({name}) - {days_left} days left")
                    except Exception as e:
                        logger.warning(f"Could not send warning to admin {uid}: {e}")
                    
                    # Super adminlarga xabar yuborish
                    for super_admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                super_admin_id,
                                f"⏰ <b>Admin muddati tugayapti!</b>\n\n"
                                f"👤 Admin: {name}\n"
                                f"🆔 ID: <code>{uid}</code>\n"
                                f"📦 Tarif: {tariff_info.get('name', tariff)}\n"
                                f"📅 Tugash: {exp_str}\n"
                                f"⏳ Qolgan kun: {days_left}\n\n"
                                f"Mijozga qo'ng'iroq qiling va to'lovni eslatib qo'ying!",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Could not notify super admin {super_admin_id}: {e}")
                    
                    # last_warning_sent_at ni yangilash
                    await conn.execute("""
                        UPDATE admins SET last_warning_sent_at = $1 WHERE user_id = $2
                    """, now, uid)
    
    except Exception as e:
        logger.error(f"Error in send_expiry_warnings: {e}")

async def check_expired_admins():
    """Muddati tugagan adminlarni auto-deactivate qilish"""
    try:
        async with db_pool.acquire() as conn:
            now = int(datetime.utcnow().timestamp())
            expired_admins = await conn.fetch("""
                SELECT user_id, name, expires_at, tariff FROM admins
                WHERE active = TRUE AND expires_at IS NOT NULL AND expires_at < $1
            """, now)
            
            for row in expired_admins:
                uid = row['user_id']
                name = row['name']
                expires_at = row['expires_at']
                tariff = row['tariff'] or 'custom'
                
                await pause_admin(uid)
                logger.info(f"Auto-deactivated admin {uid} ({name}) - expired at {expires_at}")
                
                # Admin'ga yakuniy xabar
                try:
                    exp_str, _ = human_left(expires_at)
                    tariff_info = TARIFFS.get(tariff, {})
                    await bot.send_message(
                        uid,
                        f"⚠️ <b>Admin huquqlaringiz to'xtatildi!</b>\n\n"
                        f"📅 Muddat tugash sanasi: {exp_str}\n"
                        f"📦 Tarif edi: {tariff_info.get('name', tariff)}\n\n"
                        f"Davom ettirish uchun super admin bilan bog'laning:\n"
                        f"To'lov qiling va tarifni yangilang.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify expired admin {uid}: {e}")
                
                # Super adminlarga xabar yuborish
                for super_admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            super_admin_id,
                            f"⛔ <b>Admin muddati tugadi va to'xtatildi!</b>\n\n"
                            f"👤 Admin: {name}\n"
                            f"🆔 ID: <code>{uid}</code>\n"
                            f"📦 Tarif: {tariff_info.get('name', tariff)}\n"
                            f"📅 Tugagan sana: {exp_str}\n\n"
                            f"Mijozga qo'ng'iroq qiling!",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify super admin {super_admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in check_expired_admins: {e}")

async def auto_kick_loop():
    await asyncio.sleep(5)
    while True:
        try:
            # Admin muddati tugashini tekshirish
            try:
                await check_expired_admins()
            except Exception:
                logger.exception("check_expired_admins failed")
            
            # Admin muddati tugashidan 2 kun oldin eslatma
            try:
                await send_expiry_warnings()
            except Exception:
                logger.exception("send_expiry_warnings failed")
            
            # O'quvchilar uchun eskisi
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, gid):
            return await c.answer("❌ Sizga bu guruhga ruxsat yo'q!", show_alert=True)
        
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
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, gid):
            return await c.answer("❌ Sizga bu guruhga ruxsat yo'q!", show_alert=True)
        
        key = (uid, gid)
        count = NOT_PAID_COUNTER.get(key, 0) + 1
        NOT_PAID_COUNTER[key] = count
        
        if count >= 3:
            # User guruhda borligini va admin emasligini tekshirish
            try:
                member = await bot.get_chat_member(gid, uid)
                
                # Admin yoki creator bo'lsa, chiqarib bo'lmaydi
                if member.status in ("administrator", "creator"):
                    await c.message.answer("❗ Bu foydalanuvchi guruhda admin/egadir. Chiqarib bo'lmaydi.")
                    return await c.answer()
                
                # User guruhda emas bo'lsa, skip qilamiz
                if member.status not in ("member", "administrator", "creator"):
                    await c.message.answer(f"ℹ️ Foydalanuvchi {uid} guruhda emas. Chiqarish kerak emas.")
                    NOT_PAID_COUNTER.pop(key, None)
                    return await c.answer("Guruhda emas")
                    
            except Exception as e:
                logger.warning(f"Failed to get member status for {uid} in {gid}: {e}")
                await c.message.answer(f"⚠️ Foydalanuvchi holati tekshirilmadi: {e}")
                return await c.answer("Xatolik", show_alert=True)
            
            # Kick qilish
            try:
                # Ban qilib, keyin unban qilish = kick
                await bot.ban_chat_member(chat_id=gid, user_id=uid)
                await asyncio.sleep(0.5)  # Biroz kutamiz
                await bot.unban_chat_member(chat_id=gid, user_id=uid)
                
                # Database'dan tozalash
                await clear_user_group(uid, gid)
                await clear_user_group_extra(uid, gid)
                NOT_PAID_COUNTER.pop(key, None)
                
                await c.message.answer(f"✅ Foydalanuvchi {uid} guruhdan chiqarildi (3 marta to'lov qilmagan).")
                logger.info(f"User {uid} kicked from group {gid} by admin {c.from_user.id}")
                
                # Userga xabar yuborish
                try:
                    await bot.send_message(uid, "❌ 3 marta to'lov qilmaganingiz sababli guruhdan chiqarildingiz.")
                except Exception as e:
                    logger.warning(f"Failed to notify kicked user {uid}: {e}")
                
                await c.answer("✅ Guruhdan chiqarildi")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error kicking user {uid} from group {gid}: {error_msg}")
                
                # Xatolik turini aniqlash
                if "not enough rights" in error_msg.lower():
                    await c.message.answer(
                        f"❌ <b>Xatolik!</b>\n\n"
                        f"Bot'da guruhda a'zolarni chiqarish huquqi yo'q.\n\n"
                        f"Guruh sozlamalarida bot'ga 'Foydalanuvchilarni ban qilish' huquqini bering.",
                        parse_mode="HTML"
                    )
                elif "user not found" in error_msg.lower():
                    await c.message.answer("ℹ️ Foydalanuvchi guruhda topilmadi.")
                else:
                    await c.message.answer(f"❌ Chiqarishda xatolik: {error_msg}")
                
                await c.answer("❌ Xatolik yuz berdi", show_alert=True)
        else:
            await c.message.answer(f"⌛ Foydalanuvchi {uid} hali to'lov qilmagan deb qayd etildi. ({count}/3)")
            await c.answer(f"Qayd etildi ({count}/3)")
    except Exception as e:
        logger.error(f"Error in cb_warn_notpaid: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("warn_kick:"))
async def cb_warn_kick(c: CallbackQuery):
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    try:
        parts = c.data.split(":")
        uid = int(parts[1]); gid = int(parts[2])
        
        # Guruh ruxsatini tekshirish
        if not await check_group_access(c.from_user.id, gid):
            return await c.answer("❌ Sizga bu guruhga ruxsat yo'q!", show_alert=True)
        
        # Guruh nomini olish
        titles = dict(await resolve_group_titles())
        group_name = titles.get(gid, f"Guruh {gid}")
        
        try:
            member = await bot.get_chat_member(gid, uid)
            if member.status in ("administrator", "creator"):
                await c.message.answer("❗ Bu foydalanuvchi guruhda admin/egadir. Chiqarib bo'lmaydi.")
                return await c.answer()
        except Exception as e:
            logger.warning(f"Could not check member status for {uid} in {gid}: {e}")
        
        try:
            # Avval bot'ning admin ekanligini tekshirish
            try:
                bot_member = await bot.get_chat_member(gid, bot.id)
                if bot_member.status not in ("administrator", "creator"):
                    await c.message.answer(
                        f"❌ <b>Xatolik!</b>\n\n"
                        f"Bot <b>{group_name}</b> guruhida admin emas.\n\n"
                        f"✅ Botni guruhda admin qiling va <b>\"Foydalanuvchilarni cheklash\"</b> huquqini bering.",
                        parse_mode="HTML"
                    )
                    logger.error(f"Bot is not admin in group {gid}")
                    return await c.answer("Bot guruhda admin emas!", show_alert=True)
                
                # Bot adminlik huquqlarini tekshirish
                if not bot_member.can_restrict_members:
                    await c.message.answer(
                        f"❌ <b>Xatolik!</b>\n\n"
                        f"Bot'da <b>{group_name}</b> guruhida yetarli huquq yo'q.\n\n"
                        f"✅ Bot uchun <b>\"Foydalanuvchilarni cheklash\"</b> huquqini yoqing.",
                        parse_mode="HTML"
                    )
                    logger.error(f"Bot does not have restrict_members permission in group {gid}")
                    return await c.answer("Bot'da huquq yetarli emas!", show_alert=True)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Could not check bot permissions in group {gid}: {error_msg}")
                
                # Agar guruh topilmasa, database'dan avtomatik o'chirish
                if "chat not found" in error_msg.lower() or "chat_not_found" in error_msg.lower():
                    await handle_missing_chat(gid, error_msg)
                    await c.message.answer(
                        f"⚠️ <b>Guruh o'chirildi</b>\n\n"
                        f"📋 Guruh: {group_name}\n"
                        f"🆔 ID: <code>{gid}</code>\n\n"
                        f"❌ Guruh Telegram'da topilmadi va database'dan avtomatik o'chirildi.",
                        parse_mode="HTML"
                    )
                    return await c.answer("Guruh o'chirildi", show_alert=True)
                
                await c.message.answer(
                    f"❌ <b>Xatolik!</b>\n\n"
                    f"Guruh holatini tekshirib bo'lmadi: {error_msg}\n\n"
                    f"Bot guruhda admin ekanligini va <b>\"Foydalanuvchilarni cheklash\"</b> huquqi borligini tekshiring.",
                    parse_mode="HTML"
                )
                return await c.answer("Guruh holatini tekshirib bo'lmadi", show_alert=True)
            
            # Endi guruhdan chiqarish
            await bot.ban_chat_member(gid, uid)
            await bot.unban_chat_member(gid, uid)
            await clear_user_group(uid, gid)
            await clear_user_group_extra(uid, gid)
            
            # Muvaffaqiyatli xabar
            uname, _ = await fetch_user_profile(uid)
            user_link = f"[{uname or uid}](tg://user?id={uid})"
            
            await c.message.answer(
                f"✅ <b>Guruhdan chiqarildi!</b>\n\n"
                f"👤 Foydalanuvchi: {user_link}\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"📍 Guruh: {group_name}",
                parse_mode="HTML"
            )
            
            logger.info(f"User {uid} was kicked from group {gid} by admin {c.from_user.id}")
            
            # Foydalanuvchiga xabar yuborish
            try:
                await bot.send_message(
                    uid, 
                    f"❌ <b>Obuna yangilanmagani sababli guruhdan chiqarildingiz.</b>\n\n"
                    f"📍 Guruh: {group_name}\n\n"
                    f"📞 Admin bilan bog'laning.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to notify kicked user {uid}: {e}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error kicking user {uid} from group {gid}: {e}")
            
            # Aniqroq xato xabarlari
            if "not enough rights" in error_msg.lower() or "CHAT_ADMIN_REQUIRED" in error_msg:
                await c.message.answer(
                    f"❌ <b>Xatolik!</b>\n\n"
                    f"Bot'da <b>{group_name}</b> guruhida yetarli huquq yo'q.\n\n"
                    f"✅ Botni guruhda admin qiling va <b>\"Foydalanuvchilarni cheklash\"</b> huquqini bering.",
                    parse_mode="HTML"
                )
            elif "user not found" in error_msg.lower():
                await c.message.answer(
                    f"❌ Foydalanuvchi guruhda topilmadi.\n\n"
                    f"Ehtimol allaqachon chiqib ketgan."
                )
            else:
                await c.message.answer(
                    f"❌ <b>Chiqarishda xato:</b>\n\n"
                    f"<code>{error_msg}</code>\n\n"
                    f"📍 Guruh: {group_name}",
                    parse_mode="HTML"
                )
        
        await c.answer()
    except Exception as e:
        logger.error(f"Error in cb_warn_kick: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

# Shartnoma tasdiqlash callback'lari
@dp.callback_query(F.data == "contract_agree")
async def cb_contract_agree(c: CallbackQuery):
    """Shartnoma tasdiqlash."""
    if c.from_user.id not in WAIT_CONTRACT_CONFIRM:
        return await c.answer("Sessiya topilmadi", show_alert=True)
    
    try:
        # Shartnomani tasdiqlash
        await update_user_agreed(c.from_user.id, int(datetime.utcnow().timestamp()))
        WAIT_CONTRACT_CONFIRM.discard(c.from_user.id)
        WAIT_CONTACT_FOR.add(c.from_user.id)
        
        # Telefon so'rash
        await c.message.answer(
            "✅ <b>Shartnoma tasdiqlandi!</b>\n\n"
            "📞 Endi <b>telefon raqamingizni</b> yuboring:\n\n"
            "Tugmani bosib yuboring yoki matn sifatida kiriting:\n"
            "Misol: +998901234567",
            reply_markup=contact_keyboard(),
            parse_mode="HTML"
        )
        
        await c.answer("✅ Tasdiqlandi!")
        logger.info(f"User {c.from_user.id} agreed to contract, now waiting for phone")
        
    except Exception as e:
        logger.error(f"Error in cb_contract_agree: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "contract_decline")
async def cb_contract_decline(c: CallbackQuery):
    """Shartnomani rad etish."""
    if c.from_user.id in WAIT_CONTRACT_CONFIRM:
        WAIT_CONTRACT_CONFIRM.discard(c.from_user.id)
    
    await c.message.answer(
        "❌ <b>Shartnoma rad etildi</b>\n\n"
        "Xizmatlardan foydalanish uchun shartnomani tasdiqlash kerak.\n\n"
        "Agar yana ro'yxatdan o'tmoqchi bo'lsangiz, /start bosing.",
        parse_mode="HTML"
    )
    await c.answer()
    logger.info(f"User {c.from_user.id} declined contract")

# Yangi ro'yxatdan o'tish tasdiqlash callback'lari
@dp.callback_query(F.data.startswith("reg_approve_now:"))
async def cb_reg_approve_now(c: CallbackQuery):
    """Bugundan tasdiqlash - 30 kunlik obuna."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        user_id = int(c.data.split(":")[1])
        
        # Admin'ning ruxsat etilgan guruhlarini olish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        if not allowed_groups:
            return await c.answer("❌ Sizga hech qanday guruhga ruxsat yo'q!", show_alert=True)
        
        # 30 kunlik obuna bugundan
        start_dt = datetime.utcnow()
        expires_at = int((start_dt + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
        
        # User ma'lumotlarini olish
        user_row = await get_user(user_id)
        username, fullname = await fetch_user_profile(user_id)
        phone = user_row[5] if user_row and len(user_row) > 5 else "yo'q"
        
        # Adminning birinchi ruxsat etilgan guruhiga qo'shish (primary)
        primary_gid = allowed_groups[0]
        await upsert_user(uid=user_id, username=username, full_name=fullname, group_id=primary_gid, expires_at=expires_at)
        
        human_exp = (datetime.utcfromtimestamp(expires_at) + TZ_OFFSET).strftime("%Y-%m-%d")
        
        # User'ga xabar
        try:
            await bot.send_message(
                user_id,
                f"✅ *Tabriklaymiz! Ro'yxatdan o'tdingiz!*\n\n"
                f"📅 Obuna: {SUBSCRIPTION_DAYS} kun\n"
                f"⏳ Tugash sanasi: {human_exp}\n\n"
                f"🎓 Darslarni yaxshi o'zlashtirishingizni tilaymiz!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {user_id}: {e}")
        
        # Admin'ga xabar
        await c.message.edit_text(
            f"✅ *TASDIQLANDI*\n\n"
            f"👤 {fullname}\n"
            f"📞 Telefon: {phone}\n"
            f"📅 Obuna: bugundan {SUBSCRIPTION_DAYS} kun\n"
            f"⏳ Tugash: {human_exp}",
            parse_mode="Markdown"
        )
        await c.answer("✅ Tasdiqlandi!")
        
        logger.info(f"Registration approved for user {user_id} by admin {c.from_user.id}")
            
    except Exception as e:
        logger.error(f"Error in cb_reg_approve_now: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("reg_approve_date:"))
async def cb_reg_approve_date(c: CallbackQuery):
    """Sana tanlash uchun."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        user_id = int(c.data.split(":")[1])
        
        # Admin'ning ruxsat etilgan guruhlarini tekshirish
        allowed_groups = await get_allowed_groups(c.from_user.id)
        if not allowed_groups:
            return await c.answer("❌ Sizga hech qanday guruhga ruxsat yo'q!", show_alert=True)
        
        # Admin'dan sanani so'rash
        WAIT_DATE_FOR[c.from_user.id] = user_id  # User ID ni payment ID o'rniga ishlatamiz
        
        await c.message.edit_text(
            "📅 *Obuna boshlanish sanasini kiriting:*\n\n"
            "Format: YYYY-MM-DD\n"
            "Misol: 2025-10-20",
            parse_mode="Markdown"
        )
        await c.answer("📅 Sana kiriting")
        
    except Exception as e:
        logger.error(f"Error in cb_reg_approve_date: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data.startswith("reg_reject:"))
async def cb_reg_reject(c: CallbackQuery):
    """Ro'yxatdan o'tishni rad etish."""
    if not await is_active_admin(c.from_user.id):
        return await c.answer("Faqat adminlar uchun", show_alert=True)
    
    try:
        user_id = int(c.data.split(":")[1])
        
        # User'ga xabar
        try:
            await bot.send_message(
                user_id,
                "❌ Kechirasiz, ro'yxatdan o'tish so'rovingiz rad etildi.\n\n"
                "Qo'shimcha ma'lumot olish uchun admin bilan bog'laning."
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {user_id}: {e}")
        
        # Admin'ga xabar
        username, fullname = await fetch_user_profile(user_id)
        await c.message.edit_text(
            f"❌ *RAD ETILDI*\n\n"
            f"👤 {fullname}\n"
            f"🆔 User ID: {user_id}",
            parse_mode="Markdown"
        )
        await c.answer("❌ Rad etildi")
        
        logger.info(f"Registration rejected for user {user_id} by admin {c.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error in cb_reg_reject: {e}")
        await c.answer("Xatolik yuz berdi", show_alert=True)

async def main():
    logger.info("Starting bot...")
    await db_init()
    asyncio.create_task(auto_kick_loop())
    logger.info("Bot is now polling for updates")
    try:
        # chat_member update'larini qabul qilish uchun allowed_updates qo'shildi
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Database connection pool closed")

if __name__ == "__main__":
    asyncio.run(main())
