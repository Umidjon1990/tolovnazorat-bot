import asyncio
import aiosqlite
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "./subs.db")
DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate():
    """Migrate data from SQLite to PostgreSQL"""
    
    # Check if SQLite DB exists
    if not os.path.exists(DB_PATH):
        print(f"❌ SQLite database not found at {DB_PATH}")
        print("   Ehtimol ma'lumotlar yo'q, to'g'ridan-to'g'ri PostgreSQL ishlatamiz.")
        return
    
    print(f"🔄 Migration boshlandi: {DB_PATH} -> PostgreSQL")
    
    # Connect to both databases
    sqlite_conn = await aiosqlite.connect(DB_PATH)
    pg_conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Migrate users table
        cursor = await sqlite_conn.execute("SELECT * FROM users")
        users = await cursor.fetchall()
        if users:
            print(f"📊 {len(users)} ta user topildi")
            for user in users:
                await pg_conn.execute(
                    """INSERT INTO users(user_id, username, full_name, group_id, expires_at, phone, agreed_at)
                       VALUES($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (user_id) DO UPDATE SET
                       username = EXCLUDED.username,
                       full_name = EXCLUDED.full_name,
                       group_id = EXCLUDED.group_id,
                       expires_at = EXCLUDED.expires_at,
                       phone = EXCLUDED.phone,
                       agreed_at = EXCLUDED.agreed_at""",
                    user[0], user[1], user[2], user[3], user[4], 
                    user[5] if len(user) > 5 else None,
                    user[6] if len(user) > 6 else None
                )
            print(f"✅ {len(users)} ta user ko'chirildi")
        else:
            print("ℹ️  Users table bo'sh")
        
        # Migrate payments table
        cursor = await sqlite_conn.execute("SELECT * FROM payments")
        payments = await cursor.fetchall()
        if payments:
            print(f"📊 {len(payments)} ta to'lov topildi")
            for payment in payments:
                # Check if payment already exists
                exists = await pg_conn.fetchval(
                    "SELECT id FROM payments WHERE user_id = $1 AND created_at = $2",
                    payment[1], payment[4]
                )
                if not exists:
                    await pg_conn.execute(
                        """INSERT INTO payments(user_id, photo_file, status, created_at, admin_id)
                           VALUES($1, $2, $3, $4, $5)""",
                        payment[1], payment[2], payment[3], payment[4],
                        payment[5] if len(payment) > 5 else None
                    )
            print(f"✅ {len(payments)} ta to'lov ko'chirildi")
        else:
            print("ℹ️  Payments table bo'sh")
        
        # Migrate user_groups table
        cursor = await sqlite_conn.execute("SELECT * FROM user_groups")
        user_groups = await cursor.fetchall()
        if user_groups:
            print(f"📊 {len(user_groups)} ta guruh a'zoligi topildi")
            for ug in user_groups:
                await pg_conn.execute(
                    """INSERT INTO user_groups(user_id, group_id, expires_at)
                       VALUES($1, $2, $3)
                       ON CONFLICT (user_id, group_id) DO UPDATE SET
                       expires_at = EXCLUDED.expires_at""",
                    ug[0], ug[1], ug[2]
                )
            print(f"✅ {len(user_groups)} ta guruh a'zoligi ko'chirildi")
        else:
            print("ℹ️  User_groups table bo'sh")
        
        print("\n✅ Migration muvaffaqiyatli yakunlandi!")
        print("💡 Endi bot PostgreSQL ishlatadi va ma'lumotlar xavfsiz saqlanadi")
        
    except Exception as e:
        print(f"❌ Migration xatosi: {e}")
        raise
    finally:
        await sqlite_conn.close()
        await pg_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
