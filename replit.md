# Overview

This project is a **Multi-Tenant Telegram Bot System** for managing online course subscriptions with Super Admin and Admin role-based access control.

The primary active workflow is **Payment-First Registration**: users register directly with the bot (no group membership required), submit payment receipts, receive admin approval, get 24-hour one-time invite links, and their 30-day subscription starts when they join the group. This workflow ensures payment verification before group access.

**Key Features:**
- **Payment-First Flow**: Register → Pay → Upload Receipt → Admin Approval → 24h Invite Link → Join Group → 30-Day Subscription Starts
- **Multi-Admin Security**: Admins only see payments for their assigned groups (super admins see all)
- **Auto-Subscription**: Subscription automatically starts when user joins group via invite link
- **3-Day Reminder**: Users and admins receive notifications 3 days before subscription expires

The system also retains a **Legacy Mini App Payment Workflow** (currently inactive) that uses a React Mini App and FastAPI for payment-based subscriptions. This legacy code is preserved for future expansion.

The system leverages PostgreSQL for data persistence and aiogram 3.x for the bot framework, including robust automated subscription management with warnings and auto-kick features.

**Multi-Tenant Architecture**: The system supports multiple independent administrators (Super Admin and Admins) with database-driven role management, expiration control, and group assignment.

# User Preferences

Preferred communication style: Simple, everyday language (Uzbek/English).

# System Architecture

## Bot Framework
- **Technology**: aiogram 3.x (async Telegram Bot API wrapper) for type-safe interactions.
- **Components**: Bot instance, Dispatcher for routing, Filters for commands/callbacks, State management for multi-step workflows.

## Data Storage
- **Database**: PostgreSQL with asyncpg (async driver).
- **Design**: Production-ready relational database with connection pooling (2-10 connections) for performance.
- **Tables**: 
  - `users` (core info, subscription details, `course_name`)
  - `payments` (records, approval status)
  - `user_groups` (many-to-many group access)
  - `contract_templates` (editable contract text with history)
  - **`groups`** (database-driven group management for multi-tenant support)
  - **`admins`** (multi-tenant admin management: user_id, role, active, expires_at, managed_groups)
  - **`payment_settings`** (dynamic payment info: bank_name, card_number, amount, additional_info)

## Configuration Management
- **Approach**: Hybrid - critical secrets in environment variables, dynamic data in database.
- **Environment Variables** (immutable): `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`.
- **Database-Driven** (dynamic): Groups management via `groups` table - no Railway dashboard access needed.
- **Auto-Sync on Startup**: `PRIVATE_GROUP_ID` automatically syncs to database on every restart (not just first startup) - new groups from environment variable are automatically added to database without removing existing ones.
- **Other Settings**: `SUBSCRIPTION_DAYS`, `INVITE_LINK_EXPIRE_HOURS`, `REMIND_DAYS` (environment variables).
- **Multi-Tenant Ready**: Admins can add/remove groups via bot commands without code changes or redeployment.

## Access Control
- **Multi-Tier Admin System**: 
  - **Super Admin** (`ADMIN_IDS`): Full system control, can manage other admins, unlimited access
  - **Regular Admin** (Database): Managed by Super Admin with expiration dates and group assignments
  - **Role-Based Permissions**: Different admin panels for Super Admin vs Regular Admin
  - **Auto-Deactivation**: Expired admins are automatically deactivated every 60 seconds
- **Group Management**: Supports multiple private groups via database-driven ID configuration

## Message Handling
- **Pattern**: Handler-based routing using decorators.
- **Handler Priority**: Command handlers precede F.text handler (e.g., `/start` before general text).
- **Message Types**: Supports text, callbacks, file attachments (receipts), contact sharing.
- **Keyboards**: Inline and reply keyboard markup for interaction.

## Error Handling & Logging
- **Logging**: Structured logging with timestamps and severity.
- **Error Recovery**: Try-catch blocks to prevent crashes.
- **User Feedback**: Informative error messages.

## Bot Features
- **User Flow**: Contract acceptance, name/phone input, admin approval with date selection, and group membership.
- **Security**: Group membership validation - only users in configured groups can register.
- **Admin Commands**: 
  - `/myid` - User's Telegram ID
  - **Groups Management** (Multi-Tenant Ready):
    - `/groups` - List all groups from database
    - `/add_group GROUP_ID [NAME]` - Add new group (no Railway access needed!)
    - `/remove_group GROUP_ID` - Remove group
  - **Admin Management** (Super Admin Only):
    - `/admins` - List all admins with status, role, expiry
    - `/add_admin USER_ID MUDDATI` - Add new admin (30=30 days, 0=unlimited, simple day-based)
    - `/remove_admin USER_ID` - Remove admin
    - `/pause_admin USER_ID` - Temporarily deactivate admin
    - `/resume_admin USER_ID` - Reactivate paused admin
    - `/extend_admin USER_ID MUDDATI` - Extend admin expiration (adds days to current expiry, 0=unlimited)
  - **Statistics**:
    - `/stats` - Overall statistics
    - `/gstats` - Detailed group statistics
    - `/subscribers` - View all active subscribers (real Telegram group members with active subscriptions)
    - "👥 Guruh o'quvchilari" button - View all users by group with details
  - **User Management**:
    - `/add_user USER_ID [DATE]` - Manually add single user (bugundan or YYYY-MM-DD)
    - `/add_users ID1 ID2 ID3 ... [DATE]` - Bulk add multiple users
    - `/unregistered` - Show users in group without active subscription
  - **Contract Management**:
    - `/edit_contract` - Update contract template (text or file)
  - **Payment Info Management**:
    - `/edit_payment` - Update payment info (bank, card, amount) dynamically
  - Payment approval and subscription management via inline buttons
- **Automation**: 
  - Auto-kick loop with membership validation (skips users not in group, skips admins/creators)
  - Subscription expiry warnings with action buttons (only to active group members)
  - Admin expiry auto-deactivation (runs every 60 seconds)
  - Smart warning system: checks group membership before sending, filters admins by group access
  - **Auto-cleanup for invalid groups**: Automatically removes groups from database when "chat not found" error occurs, with cache to prevent duplicate notifications

## UI/UX Decisions
- **Admin Panel**: Persistent reply keyboard with role-based buttons:
  - **Super Admin**: Statistika, Guruh o'quvchilari, To'lovlar, Guruh qo'shish, Adminlar, Shartnoma tahrirlash, To'lov ma'lumoti, Tozalash
  - **Regular Admin**: Statistika, Guruh o'quvchilari, To'lovlar, Shartnoma tahrirlash, To'lov ma'lumoti, Tozalash
- **Message Cleanup**: Automatic deletion of bot messages in admin chats after actions like payment approval to maintain cleanliness.
- **Smart Chat Links**: User messages use `[username](tg://user?id=...)` for clickable profiles.

## Technical Implementations
- **Payment-First Registration Flow**:
  - Users register via `/start` without group membership requirement
  - Phone number collection triggers payment info display (bank card details from `payment_settings` database table)
  - Photo handler captures receipt and stores in `payments` table with `status='pending'`
  - Admin receives notification with payment details and approval buttons
- **Dynamic Payment Settings**: Admin can edit payment info via `/edit_payment` command, stored in database for instant updates
- **24-Hour Invite Links**: `send_one_time_link()` generates time-limited links with `member_limit=1` and `expire_date=24h`
- **Auto-Subscription on Join**: `ChatMemberUpdated` handler detects group join and starts 30-day subscription automatically
- **Group-Level Security**: Admin payment views filtered by assigned groups - regular admins only see their groups, super admins see all
- **3-Day Expiry Reminders**: `REMIND_DAYS=3` triggers automated warnings to users and admins before subscription expires
- **State Management**: `WAIT_FULLNAME_FOR`, `WAIT_CONTACT_FOR`, `WAIT_PAYMENT_PHOTO`, `WAIT_DATE_FOR` sets to manage multi-step workflows
- **Admin Approval**: Callbacks (`ap_now`, `ap_date`, `reject`) with group selection and invite link generation
- **Profile Name & Chat Link Fix**: Uses `fetch_user_profile()` from Telegram API for fresh user names in all payment-related messages, ensuring consistency
- **Smart Group Name Resolution**: 
  - Priority: Database names > Telegram API > Group ID fallback
  - Auto-updates database with real group names from Telegram API when default "Guruh #N" names are encountered
  - Ensures admin panel shows readable group names instead of IDs
  - Single database query for performance, with automatic name caching
- **Unauthorized Join Protection**: 
  - Automatically removes users who join group without approved payment (edge case: manual admin add)
  - Uses ban + unban pattern for clean removal
  - Sends clear instructions to removed users on proper registration process
  - Prevents unauthorized group access while maintaining payment-first workflow integrity
- **Telegram Mini App (Legacy Workflow)**: React frontend (Vite) and FastAPI backend for user registration, course selection, payment submission, and admin operations. Features Telegram `initData` verification for authentication

# Deployment Architecture

## Production vs Development Environments

### **Railway (Production)**
- **Status**: Active production bot with 103+ subscribers
- **Database**: Railway internal PostgreSQL (postgres.railway.internal)
- **Deployment**: Auto-deploy from GitHub main branch
- **Purpose**: Live bot serving real users
- **Security**: Internal database hostname prevents external access

### **Replit (Development)**
- **Status**: Development and testing environment
- **Database**: Separate Neon PostgreSQL for testing (4 test users)
- **Deployment**: Manual code changes, git push to GitHub
- **Purpose**: Feature development, code testing, bug fixes
- **Workflow**: Code → Test → Git Push → Railway Auto-Deploy

### **Development Workflow**
1. Write code and test features in Replit
2. Commit changes: `git add . && git commit -m "message"`
3. Push to GitHub: `git push origin main`
4. Railway automatically deploys new code
5. 103+ production users benefit from updates

# External Dependencies

- **Telegram Bot API**: Core service for bot functionality, message delivery, and user interaction.
- **Python Libraries**:
    - `aiogram==3.22.0`: Telegram Bot API framework.
    - `asyncpg==0.30.0`: Asynchronous PostgreSQL database driver.
    - `python-dotenv==1.1.1`: Environment variable management.
    - `reportlab==4.4.4`: PDF generation for contracts.
    - `python-multipart==0.0.20`: Multipart form data parsing.
    - Standard Python libraries (`asyncio`, `logging`, `datetime`, etc.).
- **Database**: PostgreSQL (Railway internal for production, Neon for development).
- **Telegram WebApp SDK**: Used by the React Mini App for integration with Telegram features.