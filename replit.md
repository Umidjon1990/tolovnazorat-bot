# Overview

This project is a dual-workflow Telegram bot system designed for managing online course subscriptions, with a future vision for multi-tenancy.

The primary active workflow facilitates **Group-Based Direct Registration**: users who join a group can register by providing their name and phone number, with admin approval leading to a 30-day auto-subscription without requiring payment receipts or invite links.

The system also retains a **Legacy Mini App Payment Workflow** (currently inactive) that uses a React Mini App and FastAPI for payment-based subscriptions, where users upload payment receipts for admin approval to generate invite links. This legacy code is preserved for future multi-tenant expansion.

The system leverages PostgreSQL for data persistence and aiogram 3.x for the bot framework, including robust automated subscription management with warnings and auto-kick features.

# User Preferences

Preferred communication style: Simple, everyday language (Uzbek/English).

# System Architecture

## Bot Framework
- **Technology**: aiogram 3.x (async Telegram Bot API wrapper) for type-safe interactions.
- **Components**: Bot instance, Dispatcher for routing, Filters for commands/callbacks, State management for multi-step workflows.

## Data Storage
- **Database**: PostgreSQL with asyncpg (async driver).
- **Design**: Production-ready relational database with connection pooling (2-10 connections) for performance.
- **Tables**: `users` (core info, subscription details, `course_name`), `payments` (records, approval status), `user_groups` (many-to-many group access).

## Configuration Management
- **Approach**: Environment variables loaded via python-dotenv.
- **Key Settings**: `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`, `PRIVATE_GROUP_ID`, `SUBSCRIPTION_DAYS`, `INVITE_LINK_EXPIRE_HOURS`, `REMIND_DAYS`.
- **Validation**: Startup checks for critical configurations.

## Access Control
- **Admin System**: Role-based access using user ID whitelist.
- **Group Management**: Supports multiple private groups via ID configuration.

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
- **User Flow**: Contract acceptance, course selection, phone input, payment submission, admin approval, and group membership.
- **Admin Commands**: `/myid`, `/groups`, `/stats`, `/gstats` (detailed group statistics), payment approval, subscription management.
- **Automation**: Auto-kick loop, subscription expiry warnings with action buttons (runs every 60 seconds).

## UI/UX Decisions
- **Admin Panel**: Persistent reply keyboard for admins with essential buttons ("📊 Statistika", "✅ Tasdiqlangan to'lovlar", "⏳ Kutilayotgan to'lovlar", "🧹 Tozalash").
- **Message Cleanup**: Automatic deletion of bot messages in admin chats after actions like payment approval to maintain cleanliness.
- **Smart Chat Links**: User messages use `[username](tg://user?id=...)` for clickable profiles.

## Technical Implementations
- **Group-Based Direct Registration**: New `ChatMemberUpdated` handler for detecting new group members, triggering registration flow. Uses `allowed_updates` for member detection.
- **State Management**: `WAIT_FULLNAME_FOR`, `WAIT_CONTACT_FOR`, `WAIT_DATE_FOR` sets to manage user input steps.
- **Admin Approval**: Three callbacks (`reg_approve_now`, `reg_approve_date`, `reg_reject`) for managing direct registration requests.
- **Unlimited Invite Links (for Legacy Workflow)**: Invite links are one-time use (`member_limit=1`) but do not expire by time, allowing flexible student onboarding.
- **Profile Name & Chat Link Fix**: Uses `fetch_user_profile()` from Telegram API for fresh user names in all payment-related messages, ensuring consistency.
- **Telegram Mini App (Legacy Workflow)**: React frontend (Vite) and FastAPI backend for user registration, course selection, payment submission, and admin operations. Features Telegram `initData` verification for authentication.

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