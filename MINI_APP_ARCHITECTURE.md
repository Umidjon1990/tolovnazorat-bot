# 🚀 Telegram Mini App Architecture

## Overview
Converting existing Telegram bot to Mini App with React + FastAPI while keeping all current functionality.

## System Architecture

```
┌─────────────────┐
│   Telegram      │
│   Mini App      │
│   (React UI)    │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│   FastAPI       │
│   REST API      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│   PostgreSQL    │◄────►│  Telegram Bot   │
│   Database      │      │  (main.py)      │
└─────────────────┘      └─────────────────┘
```

## Components

### 1. **Telegram Mini App (React Frontend)**
**Location:** `/webapp/`
**Tech Stack:** React + Vite + Telegram WebApp SDK

**Features:**
- User registration flow (contract, course selection, phone, payment)
- Course catalog display (14 courses: A0-B2, CEFR PRO, Grammatika)
- Payment submission
- User dashboard (subscription status)
- Admin dashboard (for admins only)

**Pages:**
- `/` - Welcome & Contract
- `/courses` - Course selection (14 buttons)
- `/phone` - Phone number input
- `/payment` - Payment upload
- `/dashboard` - User info
- `/admin` - Admin panel (stats, approvals)

### 2. **FastAPI Backend**
**Location:** `/api/`
**Tech Stack:** Python FastAPI + asyncpg

**API Endpoints:**

**User Endpoints:**
```
POST /api/user/register         - Register new user (after contract)
POST /api/user/select-course    - Save selected course
POST /api/user/phone            - Save phone number
POST /api/user/payment          - Submit payment photo
GET  /api/user/me               - Get current user info
GET  /api/user/subscription     - Get subscription status
```

**Admin Endpoints:**
```
GET  /api/admin/stats           - Get statistics
GET  /api/admin/payments/pending - Get pending payments
GET  /api/admin/payments/approved - Get approved payments
POST /api/admin/payment/approve - Approve payment
POST /api/admin/payment/reject  - Reject payment
GET  /api/admin/groups          - Get all groups
POST /api/admin/assign-group    - Assign user to group(s)
```

**Course Endpoints:**
```
GET  /api/courses               - Get all 14 courses
```

### 3. **Existing Bot (Automation)**
**Location:** `/main.py`
**Keeps running for:**
- Admin commands via Telegram
- Auto-kick expired users (60s loop)
- Reminder notifications
- Invite link generation
- Admin notifications

### 4. **PostgreSQL Database**
**Shared by:** FastAPI + Telegram Bot

**Tables:**
- `users` - User info (course_name included)
- `payments` - Payment records
- `user_groups` - Multi-group assignments

## File Structure

```
/
├── main.py                 # Telegram bot (existing - keep running)
├── api/
│   ├── main.py            # FastAPI app
│   ├── routes/
│   │   ├── user.py        # User endpoints
│   │   ├── admin.py       # Admin endpoints
│   │   └── courses.py     # Course endpoints
│   ├── database.py        # DB connection (shared)
│   └── auth.py            # Telegram auth verification
├── webapp/
│   ├── src/
│   │   ├── App.jsx        # Main app
│   │   ├── pages/
│   │   │   ├── Contract.jsx
│   │   │   ├── Courses.jsx
│   │   │   ├── Phone.jsx
│   │   │   ├── Payment.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── Admin.jsx
│   │   ├── components/
│   │   │   ├── CourseCard.jsx
│   │   │   └── PaymentForm.jsx
│   │   └── utils/
│   │       └── telegram.js  # Telegram SDK utils
│   ├── public/
│   │   └── logo.png
│   ├── package.json
│   └── vite.config.js
├── requirements.txt       # Python deps (add fastapi, uvicorn)
└── logo.png               # Logo (used in webapp too)
```

## Authentication Flow

1. User opens Mini App from Telegram
2. Telegram sends `initData` (includes user_id, username)
3. FastAPI validates `initData` signature
4. User authenticated automatically (no login needed!)

## Deployment

**Development (Replit):**
- Bot: `python main.py` (existing workflow)
- API: `uvicorn api.main:app --port 8000`
- Frontend: `npm run dev --port 5000` (in webapp/)

**Production (Railway):**
- Bot: `python main.py`
- API: `uvicorn api.main:app --port 8000`
- Frontend: Build static files → serve via Nginx/Railway

## Course Data (14 Courses)

```json
[
  {"id": 1, "name": "A0 Standard", "type": "standard", "level": "A0"},
  {"id": 2, "name": "A0 Premium", "type": "premium", "level": "A0"},
  {"id": 3, "name": "A1 Standard", "type": "standard", "level": "A1"},
  {"id": 4, "name": "A1 Premium", "type": "premium", "level": "A1"},
  {"id": 5, "name": "A2 Standard", "type": "standard", "level": "A2"},
  {"id": 6, "name": "A2 Premium", "type": "premium", "level": "A2"},
  {"id": 7, "name": "B1 Standard", "type": "standard", "level": "B1"},
  {"id": 8, "name": "B1 Premium", "type": "premium", "level": "B1"},
  {"id": 9, "name": "B2 Standard", "type": "standard", "level": "B2"},
  {"id": 10, "name": "B2 Premium", "type": "premium", "level": "B2"},
  {"id": 11, "name": "CEFR PRO Standard", "type": "standard", "level": "PRO"},
  {"id": 12, "name": "CEFR PRO Premium", "type": "premium", "level": "PRO"},
  {"id": 13, "name": "Grammatika Standard", "type": "standard", "level": "GRAM"},
  {"id": 14, "name": "Grammatika Premium", "type": "premium", "level": "GRAM"}
]
```

## Key Features Preserved

✅ All 14 courses with button selection
✅ Phone number input
✅ Payment photo upload
✅ Admin approval system
✅ Multi-group assignments
✅ PDF contract generation (backend)
✅ Invite link generation (1-time, 72h)
✅ Auto-kick system
✅ Statistics & reports
✅ PostgreSQL database

## Development Steps

1. ✅ Architecture planning
2. ⏳ Setup FastAPI backend
3. ⏳ Create React frontend
4. ⏳ Implement user flow
5. ⏳ Implement admin panel
6. ⏳ Connect to Telegram
7. ⏳ Deploy & test
