# Overview

This project is a **Multi-Tenant Telegram Bot System** designed for managing online course subscriptions with Super Admin and Admin role-based access control. Its primary active workflow is **Payment-First Registration**, ensuring payment verification before users gain group access.

**Key Capabilities:**
- **Payment-First Flow**: Users register, pay, submit receipts, receive admin approval, get a 24-hour invite link, and their 30-day subscription starts upon joining the group.
- **Subscription Management**: Includes renewal workflows, one-click renewal options, 3-day expiry reminders, and automated subscription activation/deactivation.
- **Multi-Admin Security**: Role-based access control where admins only view payments for their assigned groups (Super Admins see all).
- **Automated Features**: Auto-subscription on group join, automated expiry warnings with renewal options, and auto-kick for expired subscriptions.

The system supports a multi-tenant architecture with database-driven role management and group configuration. It utilizes PostgreSQL for data persistence and `aiogram 3.x` for the bot framework. A legacy React Mini App workflow is preserved for potential future use.

# User Preferences

Preferred communication style: Simple, everyday language (Uzbek/English).

# System Architecture

## System Design
The system employs a multi-tenant architecture, allowing multiple independent administrators (Super Admin and Admins) to manage groups and subscriptions. Core configuration is a hybrid approach, with critical secrets in environment variables and dynamic data (like group IDs and payment settings) stored in PostgreSQL. Admin roles are database-driven with expiration control and group assignments.

## UI/UX Decisions
- **Admin Panel**: Features a persistent reply keyboard with role-based buttons for Super Admins and Regular Admins, streamlining management tasks.
- **Message Clarity**: Uses smart chat links for clickable user profiles and automatic cleanup of bot messages in admin chats after actions to maintain tidiness.
- **Smart Group Name Resolution**: Prioritizes database names, then Telegram API, then group ID, automatically updating database with real group names for improved readability.

## Technical Implementations
- **Bot Framework**: Built with `aiogram 3.x` for asynchronous, type-safe Telegram Bot API interactions, featuring a Dispatcher for routing, Filters, and State management.
- **Data Storage**: PostgreSQL with `asyncpg` for production-ready, performant data persistence. Key tables include `users`, `payments`, `user_groups`, `groups`, `admins`, and `payment_settings` for dynamic configuration.
- **Access Control**: Multi-tier admin system (`ADMIN_IDS` for Super Admins, database-managed Regular Admins) with role-based permissions and auto-deactivation for expired admin accounts.
- **Subscription Renewal**: Supports renewal via `/renew` command or one-click inline buttons, processing payments, and extending existing subscriptions by 30 days. `payment_type` column differentiates initial payments from renewals.
- **Payment-First Registration**: Users register without prior group membership, submit payment receipts, and receive admin approval before getting a 24-hour invite link.
- **Dynamic Settings**: Admins can update payment information and contract templates dynamically via bot commands, stored in the database.
- **Automated Processes**: Includes auto-kick for expired members, 3-day expiry reminders to users and admins, and auto-deactivation of expired admin accounts.
- **Unauthorized Join Protection**: Bot notifies admins when unapproved users join a group, providing "Keep" or "Remove" options, requiring explicit admin action rather than automatic removal.
- **Comprehensive User Removal**: `/remove_user` command allows admins to completely remove a user from the system, including Telegram groups, database records, and state caches, while supporting re-registration.

# External Dependencies

- **Telegram Bot API**: Core service for bot communication.
- **Python Libraries**:
    - `aiogram`: Telegram Bot API framework.
    - `asyncpg`: Asynchronous PostgreSQL driver.
    - `python-dotenv`: Environment variable management.
    - `reportlab`: PDF generation.
- **Database**: PostgreSQL (Railway for production, Neon for development).
- **Telegram WebApp SDK**: Used by the React Mini App (legacy workflow).