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

## Configuration Management
- **Approach**: Hybrid - critical secrets in environment variables, dynamic data in database.
- **Environment Variables** (immutable): `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`.
- **Database-Driven** (dynamic): Groups management via `groups` table - no Railway dashboard access needed.
- **Legacy Support**: `PRIVATE_GROUP_ID` auto-migrates to database on first startup.
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
    - `/add_admin USER_ID MUDDATI` - Add new admin (30 days or 0 for unlimited)
    - `/remove_admin USER_ID` - Remove admin
    - `/pause_admin USER_ID` - Temporarily deactivate admin
    - `/resume_admin USER_ID` - Reactivate paused admin
    - `/extend_admin USER_ID MUDDATI` - Extend admin expiration
  - **Statistics**:
    - `/stats` - Overall statistics
    - `/gstats` - Detailed group statistics
    - "👥 Guruh o'quvchilari" button - View all users by group with details
  - **User Management**:
    - `/add_user USER_ID [DATE]` - Manually add single user (bugundan or YYYY-MM-DD)
    - `/add_users ID1 ID2 ID3 ... [DATE]` - Bulk add multiple users
    - `/unregistered` - Show users in group without active subscription
  - **Contract Management**:
    - `/edit_contract` - Update contract template (text or file)
  - Payment approval and subscription management via inline buttons
- **Automation**: Auto-kick loop, subscription expiry warnings with action buttons, admin expiry auto-deactivation (runs every 60 seconds).

## UI/UX Decisions
- **Admin Panel**: Persistent reply keyboard with role-based buttons:
  - **Super Admin**: Statistika, Guruh o'quvchilari, To'lovlar, Guruh qo'shish, Adminlar, Shartnoma tahrirlash, Tozalash
  - **Regular Admin**: Statistika, Guruh o'quvchilari, To'lovlar, Shartnoma tahrirlash, Tozalash
- **Message Cleanup**: Automatic deletion of bot messages in admin chats after actions like payment approval to maintain cleanliness.
- **Smart Chat Links**: User messages use `[username](tg://user?id=...)` for clickable profiles.

## Technical Implementations
- **Payment-First Registration Flow**:
  - Users register via `/start` without group membership requirement
  - Phone number collection triggers `PAYMENT_INFO` display (bank card details from environment)
  - Photo handler captures receipt and stores in `payments` table with `status='pending'`
  - Admin receives notification with payment details and approval buttons
- **24-Hour Invite Links**: `send_one_time_link()` generates time-limited links with `member_limit=1` and `expire_date=24h`
- **Auto-Subscription on Join**: `ChatMemberUpdated` handler detects group join and starts 30-day subscription automatically
- **Group-Level Security**: Admin payment views filtered by assigned groups - regular admins only see their groups, super admins see all
- **3-Day Expiry Reminders**: `REMIND_DAYS=3` triggers automated warnings to users and admins before subscription expires
- **State Management**: `WAIT_FULLNAME_FOR`, `WAIT_CONTACT_FOR`, `WAIT_PAYMENT_PHOTO`, `WAIT_DATE_FOR` sets to manage multi-step workflows
- **Admin Approval**: Callbacks (`ap_now`, `ap_date`, `reject`) with group selection and invite link generation
- **Profile Name & Chat Link Fix**: Uses `fetch_user_profile()` from Telegram API for fresh user names in all payment-related messages, ensuring consistency
- **Telegram Mini App (Legacy Workflow)**: React frontend (Vite) and FastAPI backend for user registration, course selection, payment submission, and admin operations. Features Telegram `initData` verification for authentication

# External Dependencies

- **Telegram Bot API**: Core service for bot functionality, message delivery, and user interaction.
- **Python Libraries**:
    - `aiogram`: Telegram Bot API framework.
    - `asyncpg`: Asynchronous PostgreSQL database driver.
    - `python-dotenv`: Environment variable management.
    - `reportlab`: PDF generation for contracts.
    - Standard Python libraries (`asyncio`, `logging`, `datetime`, etc.).
- **Database**: PostgreSQL (deployed with persistent volumes, e.g., on Railway).
- **Telegram WebApp SDK**: Used by the React Mini App for integration with Telegram features.