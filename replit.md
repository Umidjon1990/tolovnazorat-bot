# Overview

This is a Telegram bot application built using the aiogram framework (Python). The bot manages user interactions, admin functionality, and private group access through invite links for an online course subscription system. The application uses SQLite (via aiosqlite) for data persistence and is configured through environment variables for deployment flexibility.

# Recent Changes (October 13, 2025)

- **Admin Button Interface**: Persistent reply keyboard for admins - "📊 Statistika", "✅ Tasdiqlangan to'lovlar", and "⏳ Kutilayotgan to'lovlar" buttons always visible (no need to press /start)
- **Tasdiqlangan to'lovlar Pagination**: When admin clicks "Tasdiqlangan to'lovlar" button, shows options: "Oxirgi 3 tasi" (last 3) or "Hammasi" (all approved payments) with multi-group support
- **Kutilayotgan to'lovlar**: Shows all pending payments with approval buttons, or "Kutilayotgan to'lovlar mavjud emas" if empty
- **Multi-group Display**: Approved payments now show all assigned groups for each user (comma-separated list)
- **Auto-Delete Final Summary**: Final summary message with receipt photo automatically deletes after 10 seconds to keep admin chat clean
- **Auto Payment Notification**: When user sends payment receipt, admins receive it immediately (no button press needed)
- **Invite Link Messages**: Updated to show "3 kun amal qiladi" instead of "72 soat" for better UX (auto-calculated from INVITE_LINK_EXPIRE_HOURS)
- **Complete Message Cleanup**: All admin messages (group selection, date input, approval messages) auto-delete after payment approval, leaving only receipt and final summary
- **Admin Message Tracking**: Extended ADMIN_MESSAGES to include date input and single group selection messages
- **Admin Message Cleanup**: All payment-related admin messages are automatically deleted after approval, keeping admin chat clean
- **Final Summary with Receipt**: After approval, admin receives a clean summary message with payment receipt photo showing user details (name, username, phone, groups, expiry date)
- **Statistics Filtering**: `/stats` command now shows only active users who are assigned to groups (filters out unassigned users)
- **Invite Link Configuration**: Confirmed 1-time use links (member_limit=1) with 72-hour validity (INVITE_LINK_EXPIRE_HOURS=72)
- **PostgreSQL Migration**: Successfully migrated from SQLite to PostgreSQL with asyncpg for Railway deployment stability
- **Multi-group Support**: Enhanced checkbox-based group selection with message cleanup workflow

# Previous Updates (October 6, 2025)

- Fixed critical handler ordering issue - moved Command handlers before F.text handler to ensure commands are processed correctly
- Removed fullname input step - phone number input now directly generates PDF contracts with auto-filled user info from Telegram
- Fixed PDF contract generation - switched from FSInputFile to BufferedInputFile for proper document sending
- Enhanced statistics commands with detailed group member information
- Added `/myid` command for users to check their Telegram ID
- Improved `/gstats` command to show comprehensive details: username, ID, phone, subscription dates for each member
- Fixed invite link generation to be truly one-time use with `member_limit=1`
- Streamlined user registration flow for better UX

# User Preferences

Preferred communication style: Simple, everyday language (Uzbek/English).

# System Architecture

## Bot Framework
- **Technology**: aiogram 3.x (async Telegram Bot API wrapper)
- **Rationale**: Modern, fully asynchronous Python framework that provides type-safe interactions with Telegram's Bot API
- **Key Components**:
  - Bot instance for API communication
  - Dispatcher for handling updates and routing messages
  - Filters for command and callback query handling
  - State management for multi-step workflows (date input, contact collection, fullname entry)

## Data Storage
- **Database**: PostgreSQL with asyncpg (async driver)
- **Rationale**: Production-ready relational database with ACID compliance, perfect for Railway deployment with persistent volumes
- **Design**: Connection pooling (2-10 connections) for optimal performance and fully asynchronous operations
- **Tables**:
  - `users`: Core user information with subscription details
  - `payments`: Payment records with approval status
  - `user_groups`: Many-to-many relationship for multi-group access
- **Migration**: Migrated from SQLite to PostgreSQL (October 13, 2025) for Railway deployment stability

## Configuration Management
- **Approach**: Environment variables loaded via python-dotenv
- **Key Settings**:
  - `BOT_TOKEN`: Telegram bot authentication token (required)
  - `DATABASE_URL`: PostgreSQL connection string (required)
  - `ADMIN_IDS`: Comma-separated list of Telegram user IDs with admin privileges
  - `PRIVATE_GROUP_ID`: Comma-separated list of private group IDs for invite link generation
  - `SUBSCRIPTION_DAYS`: Default subscription duration (default: 30 days)
  - `INVITE_LINK_EXPIRE_HOURS`: Invite link expiration time (default: 72 hours)
  - `REMIND_DAYS`: Days before expiry to send reminder (default: 3 days)
- **Validation**: Startup checks ensure critical configuration is present, with warnings for optional settings

## Access Control
- **Admin System**: Role-based access using user ID whitelist
- **Group Management**: Multiple private groups supported through ID configuration
- **Design Philosophy**: Simple ID-based authorization suitable for small-scale bot operations
- **Contract System**: Users must accept terms before proceeding with registration

## Message Handling
- **Pattern**: Handler-based routing using decorators
- **Handler Priority**: **CRITICAL** - Commands must come before F.text handler:
  1. Command handlers (`/start`, `/stats`, `/gstats`, `/groups`, `/myid`)
  2. Admin date input handler (for custom subscription start dates)
  3. Contact handler (for phone number collection via Contact button)
  4. Phone text handler (for phone number as text input)
  5. General F.text handler (catches all remaining text messages)
- **Message Types**: Support for text messages, callbacks, file attachments (payment receipts), and contact sharing
- **Keyboards**: Both inline and reply keyboard markup for user interaction
- **Note**: Handler order is crucial - incorrect ordering causes commands to be ignored

## Error Handling & Logging
- **Logging**: Structured logging with timestamps, severity levels, and context information
- **Error Recovery**: Try-catch blocks throughout to prevent bot crashes
- **User Feedback**: Informative error messages for users when operations fail
- **Configuration Validation**: Runtime checks for required environment variables with descriptive error messages

## Bot Features

### User Flow
1. `/start` command displays contract
2. User accepts contract terms
3. User shares phone number (Contact button or TEXT)
4. Contract documents (TXT and PDF) automatically generated and sent (name auto-filled from Telegram profile)
5. User selects payment method and uploads receipt photo
6. Admin approves payment and assigns group(s)
7. User receives one-time invite link(s) with expiration

### Admin Commands
- `/myid` - Shows user's Telegram ID
- `/groups` - List of configured groups with names and IDs
- `/stats` - Quick statistics: total users, active subscriptions, expired, and summary per group
- `/gstats` - **Detailed statistics**: Full member list for each group showing username, ID, phone number, and subscription expiry dates
- Payment approval with immediate or custom start date
- Single or multi-group assignment per user
- Subscription renewal and management
- Automatic expiry warnings with action buttons

### Automation
- Auto-kick loop runs every 60 seconds
- Checks for soon-expiring subscriptions (configurable days)
- Checks for expired subscriptions
- Sends warnings to users and admins with action buttons
- Prevents duplicate warnings using cache (1 hour cooldown)

# External Dependencies

## Telegram Bot API
- **Service**: Telegram's Bot API (via aiogram)
- **Purpose**: Core bot functionality, message delivery, user interaction
- **Integration**: Long-polling based for reliability

## Python Libraries
- **aiogram**: Telegram Bot API framework (async)
- **asyncpg**: Asynchronous PostgreSQL database driver with connection pooling
- **python-dotenv**: Environment variable management
- **reportlab**: PDF generation for contracts
- **Standard library**: asyncio, logging, datetime, typing, io, re for core functionality

## Database
- **PostgreSQL**: Production-grade relational database with ACID compliance
- **Access Pattern**: Connection pool (2-10 connections) with async operations and proper indexing
- **Schema**: Supports user management, payment tracking, and multi-group memberships
- **Deployment**: Persistent PostgreSQL volumes on Railway ensure data survives redeploys and republishes
