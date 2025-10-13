# 🚂 Railway Deployment Guide

Bu loyihani Railway'ga deploy qilish bo'yicha to'liq yo'riqnoma.

## 📋 Tayyorgarlik

### 1. GitHub Repository
```bash
# Barcha o'zgarishlarni commit qiling
git add .
git commit -m "Add Telegram Mini App - ready for Railway deployment"
git push origin main
```

### 2. Railway Account
- [railway.app](https://railway.app) ga kiring
- GitHub bilan ro'yxatdan o'ting

---

## 🚀 Deployment Qadamlari

### STEP 1: Yangi Project Yarating

1. Railway dashboard'da **"New Project"** bosing
2. **"Deploy from GitHub repo"** tanlang
3. Repository'ingizni tanlang

---

### STEP 2: 3 Ta Service Yarating

Railway'da **3 ta alohida service** kerak:

#### ⚙️ Service 1: BOT
```
Name: telegram-bot
Start Command: python main.py
Root Directory: /
```

**Environment Variables:**
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_id
PRIVATE_GROUP_ID=-1001234567890
DATABASE_URL=${{Postgres.DATABASE_URL}}
SUBSCRIPTION_DAYS=30
INVITE_LINK_EXPIRE_HOURS=72
REMIND_DAYS=3
SESSION_SECRET=any_random_string_here
```

---

#### ⚙️ Service 2: API (Backend)
```
Name: fastapi-backend
Start Command: uvicorn api.main:app --host 0.0.0.0 --port $PORT
Root Directory: /
```

**Environment Variables:**
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_id
DATABASE_URL=${{Postgres.DATABASE_URL}}
SESSION_SECRET=any_random_string_here
```

**Generate Domain:**
- Settings → Networking → Generate Domain
- Copy URL (masalan: `https://yourapp-api.up.railway.app`)

---

#### ⚙️ Service 3: Frontend (Mini App)
```
Name: mini-app-frontend
Build Command: cd webapp && npm install && npm run build
Start Command: cd webapp && npm run preview -- --host 0.0.0.0 --port $PORT
Root Directory: /
```

**Environment Variables:**
```
VITE_API_URL=https://yourapp-api.up.railway.app
```

**Generate Domain:**
- Settings → Networking → Generate Domain
- Copy URL (masalan: `https://yourapp.up.railway.app`)

---

### STEP 3: PostgreSQL Database

1. Dashboard'da **"New"** → **"Database"** → **"PostgreSQL"**
2. Database yaratilgandan keyin, variables avtomatik o'rnatiladi
3. `DATABASE_URL` avtomatik barcha service'larga ulashadi

---

### STEP 4: BotFather Sozlash

```
1. Telegram'da @BotFather'ni oching
2. /newapp - Mini App yaratish
3. Botingizni tanlang
4. Web App URL: https://yourapp.up.railway.app (Frontend URL)
5. Short name: courseapp (yoki boshqa nom)
6. Description: Course Subscription Bot
7. Photo: Logo yuklang (ixtiyoriy)
```

**Bot Menu Button:**
```
/setmenubutton
Botingizni tanlang
Text: 📱 Ilovani ochish
URL: https://yourapp.up.railway.app
```

---

### STEP 5: Deployment Tekshirish

#### Bot Service:
```bash
# Logs'da ko'rish kerak:
✅ "PostgreSQL database initialized successfully"
✅ "Bot is now polling for updates"
✅ Conflict xatosi bo'lmasligi kerak
```

#### API Service:
```bash
# Logs'da ko'rish kerak:
✅ "Uvicorn running on http://0.0.0.0:8000"
✅ "Application startup complete"
```

#### Frontend Service:
```bash
# Logs'da ko'rish kerak:
✅ "ready in XXXms"
✅ "Local: http://0.0.0.0:5000"
```

---

## 🔧 Muhim Sozlamalar

### Vite Config Yangilash (Frontend uchun)

`webapp/vite.config.js`:
```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: process.env.PORT || 5000
  }
})
```

---

## 🧪 Test Qilish

### 1. Bot'ni Test Qiling:
```
- Telegram'da /start bosing
- Shartnoma chiqishi kerak
```

### 2. Mini App'ni Test Qiling:
```
- Bot menu'dan "📱 Ilovani ochish" bosing
- Mini App ochilishi kerak
- Shartnoma → Kurs → Telefon → To'lov
```

### 3. Admin Panel Test:
```
- Telegram'da "📊 Statistika" bosing
- "⏳ Kutilayotgan to'lovlar" bosing
- To'lovni tasdiqlang
```

---

## 🐛 Troubleshooting

### Bot Conflict Error:
```
Telegram server says - Conflict: terminated by other getUpdates request
```
**Yechim:** Replit'dagi bot workflow'ni to'xtating yoki boshqa joyda bot ishlamayotganini tekshiring.

### Mini App Ochmaydi:
**Yechim:** 
1. Frontend URL to'g'ri BotFather'da o'rnatilganini tekshiring
2. Frontend service deploy bo'lganini tekshiring
3. VITE_API_URL to'g'ri o'rnatilganini tekshiring

### API 404 Error:
**Yechim:**
1. API service ishayotganini tekshiring (logs)
2. Frontend'dagi VITE_API_URL to'g'ri URL'ga ishora qilayotganini tekshiring

### Database Connection Error:
**Yechim:**
1. PostgreSQL service deploy bo'lganini tekshiring
2. DATABASE_URL barcha service'larda borligini tekshiring

---

## 📊 Service Architecture

```
User (Telegram) 
    ↓
Bot Service (main.py) ← Admin commands & automation
    ↓
PostgreSQL Database ← Shared data
    ↑
API Service (FastAPI) ← REST endpoints
    ↑
Frontend Service (React + Vite) ← User interface
    ↑
User (Mini App)
```

---

## ✅ Final Checklist

- [ ] GitHub'ga push qildingiz
- [ ] Railway'da 3 ta service yaratdingiz (Bot, API, Frontend)
- [ ] PostgreSQL database qo'shdingiz
- [ ] Environment variables to'ldirdingiz
- [ ] Frontend va API uchun domain yaratdingiz
- [ ] BotFather'da Mini App URL o'rnatdingiz
- [ ] Bot menu button qo'shdingiz
- [ ] Barcha service'lar deploy bo'ldi (logs tekshirdingiz)
- [ ] End-to-end test qildingiz

---

## 🎉 Deploy Muvaffaqiyatli!

Endi sizning Telegram Mini App to'liq ishga tushdi:

✅ User'lar Mini App orqali ro'yxatdan o'tadilar  
✅ Admin'lar Telegram bot orqali tasdiqladilar  
✅ Avtomatik guruhga qo'shiladi  
✅ Barcha ma'lumotlar PostgreSQL'da saqlanadi  

**Qo'shimcha yordam kerak bo'lsa, Railway documentation'ni o'qing:** [docs.railway.app](https://docs.railway.app)
