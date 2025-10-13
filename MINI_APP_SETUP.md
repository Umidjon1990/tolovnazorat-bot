# 🚀 Telegram Mini App - Setup Guide

## ✅ Nima Tayyor?

- **FastAPI Backend** - Port 8000'da ishlayapti
- **React Frontend** - Port 5000'da ishlayapti
- **Telegram Bot** - Avvalgi bot ishlayapti (admin funksiyalar uchun)
- **PostgreSQL Database** - Barcha ma'lumotlar saqlanadi

---

## 📋 Tizim Arxitekturasi

```
User → Telegram Mini App (React) → FastAPI API → PostgreSQL Database
                                  ↓
                         Telegram Bot (admin, automation)
```

---

## 🔧 BotFather orqali Mini App sozlash

### 1. BotFather'ni oching
Telegram'da `@BotFather` botini oching

### 2. Mini App yaratish
```
/newapp
```

### 3. Bot tanlash
Botingizni tanlang (sizning kurs botingiz)

### 4. App nomi
```
Course App
```
(yoki boshqa nom)

### 5. App tavsifi
```
Onlayn kurs obunalari uchun ilova
```

### 6. App rasmi
64x64 yoki 512x512 rasm yuklang (logo.png)

### 7. GIF (ixtiyoriy)
Skip qilishingiz mumkin

### 8. **WEB APP URL** (Muhim!)
**Development (Replit):**
```
https://[replit-username]-[repl-name].replit.app
```

**Production (Railway):**
```
https://[your-railway-app].up.railway.app
```

### 9. Short name
```
courseapp
```
(yoki boshqa qisqa nom)

### 10. Tayyor!
BotFather sizga link beradi:
```
https://t.me/[botusername]/courseapp
```

---

## 🎯 Mini App'ni Botga Ulash

### Variant 1: Menu Button (Tavsiya)
```
/setmenubutton
```
Botingizni tanlang → Mini App URL kiriting

### Variant 2: Inline tugma orqali
`main.py` ga qo'shish:

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# /start komandaga qo'shing
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="📱 Ilovani ochish",
        web_app=WebAppInfo(url="https://your-app-url.com")
    )]
])

await m.answer("Ilovani ochish:", reply_markup=keyboard)
```

---

## 🌐 Deployment

### Replit Development
1. Barcha 3 workflow ishlayapti:
   - Bot (Test only)
   - FastAPI Backend  
   - Mini App Frontend

2. Mini App URL:
   ```
   https://[your-repl].replit.app
   ```

### Railway Production

#### 1. GitHub'ga push
```bash
git add .
git commit -m "Add Telegram Mini App"
git push origin main
```

#### 2. Railway'da 3 ta service kerak:
- **Bot Service:** `python main.py`
- **API Service:** `uvicorn api.main:app --host 0.0.0.0 --port 8000`
- **Frontend Service:** `cd webapp && npm run build && npm run preview`

#### 3. Environment Variables
Barcha servicelarga qo'shing:
```
BOT_TOKEN=...
DATABASE_URL=...
ADMIN_IDS=...
PRIVATE_GROUP_ID=...
SUBSCRIPTION_DAYS=30
INVITE_LINK_EXPIRE_HOURS=72
```

#### 4. Frontend Build
Frontend serviceda:
```bash
cd webapp
npm install
npm run build
npm run preview -- --host 0.0.0.0 --port 5000
```

---

## 🧪 Testing

### 1. Replit'da test (Development)
1. BotFather'da Mini App URL = Replit URL
2. Telegram'da botni oching
3. Menu tugmasi yoki inline tugma bosing
4. Mini App ochiladi ✅

### 2. Railway'da test (Production)
1. Railway'da deploy qiling
2. BotFather'da Mini App URL = Railway URL  
3. Test qiling

---

## 📱 User Flow (Mini App)

1. **Contract** - Shartnoma qabul qilish
2. **Courses** - 14 ta kursdan birini tanlash
3. **Phone** - Telefon raqam kiritish
4. **Payment** - To'lov chekini yuklash
5. **Success** - "To'lov yuborildi" xabari

---

## 👨‍💼 Admin (Telegram Bot orqali)

Adminlar hali ham Telegram bot orqali ishlaydi:
- `/stats` - Statistika
- `/gstats` - Batafsil ma'lumot
- Kutilayotgan to'lovlar tugmasi
- Tasdiqlash/Rad etish

---

## 🔄 Bot + Mini App Ishlash Tartibi

### User funksiyalari:
- ✅ Mini App orqali ro'yxatdan o'tish
- ✅ Kurs tanlash
- ✅ To'lov yuborish

### Bot funksiyalari (avvalgidek):
- ✅ Admin to'lovni tasdiqlash
- ✅ Invite link yaratish
- ✅ Auto-kick (muddati o'tganlar)
- ✅ Eslatmalar

---

## 📊 Ma'lumotlar Oqimi

```
1. User Mini App'ni ochadi
2. Telegram initData yuboradi (user_id, username)
3. FastAPI initData'ni tasdiqlaydi
4. User ma'lumotlarini oladi
5. User kurs tanlaydi → Database'ga yoziladi
6. User to'lov yuboradi → Database'ga yoziladi
7. Admin Telegram bot'da to'lovni tasdiqlaydi
8. Bot invite link yaratadi
9. User guruhga kiradi ✅
```

---

## 🐛 Debugging

### Frontend xatoliklari:
```bash
cd webapp && npm run dev
```
Browser console'da xatolarni ko'ring

### Backend xatoliklari:
```bash
uvicorn api.main:app --reload
```
Terminal'da xatolarni ko'ring

### Bot xatoliklari:
```bash
python main.py
```
Logs'ni tekshiring

---

## 🔐 Xavfsizlik

✅ Telegram initData imzo bilan tekshiriladi  
✅ **Auth freshness validation** - 24 soatdan eski tokenlar rad etiladi (replay attack oldini olish)  
✅ Har bir so'rov autentifikatsiya qilinadi  
✅ Admin funksiyalar ADMIN_IDS orqali himoyalangan  
✅ File upload xavfsiz (uploads/ papkaga)  

**Muhim:** Telegram initData 24 soat ichida amal qiladi. Agar user Mini App'ni 24 soatdan keyin ochsa, Telegram yangi initData yuboradi.  

---

## 📝 Keyingi Qadamlar

1. ✅ BotFather orqali Mini App sozlang
2. ✅ Replit'da test qiling
3. ✅ Railway'ga deploy qiling
4. ✅ Production'da test qiling
5. ✅ Foydalanuvchilarga e'lon qiling!

---

## 📞 Qo'llab-quvvatlash

**Muammo bo'lsa:**
1. Workflow logs'ni tekshiring
2. Browser console'ni tekshiring
3. Database'ni tekshiring
4. Telegram initData kelayotganini tekshiring

**Savol bo'lsa:**
- Frontend: React sahifalari (`webapp/src/pages/`)
- Backend: API routes (`api/routes/`)
- Bot: `main.py`

---

## 🎉 Muvaffaqiyat!

Mini App tayyor! Foydalanuvchilar endi:
- ✅ Chiroyli interfeys ko'radi
- ✅ Oson ro'yxatdan o'tadi
- ✅ Tez to'lov yuboradi
- ✅ Professional tajriba oladi

**Bot + Mini App = Perfect! 🚀**
