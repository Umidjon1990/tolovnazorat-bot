# Overview

This is a Telegram bot application built using the aiogram framework (Python). The bot manages user interactions, admin functionality, and private group access through invite links for an online course subscription system. The application uses SQLite (via aiosqlite) for data persistence and is configured through environment variables for deployment flexibility.

# Recent Changes (October 2025)

- Improved code structure with better organization and error handling
- Enhanced logging throughout the application with detailed timestamps
- Fixed handler ordering issue for admin date input functionality
- Added comprehensive try-catch blocks to prevent crashes
- Created proper .gitignore and .env.example files for better project management

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
- **Database**: SQLite with aiosqlite (async wrapper)
- **Rationale**: Lightweight, serverless database suitable for small to medium-scale bot applications with minimal infrastructure requirements
- **Design**: Fully asynchronous database operations to prevent blocking the event loop
- **Tables**:
  - `users`: Core user information with subscription details
  - `payments`: Payment records with approval status
  - `user_groups`: Many-to-many relationship for multi-group access

## Configuration Management
- **Approach**: Environment variables loaded via python-dotenv
- **Key Settings**:
  - `BOT_TOKEN`: Telegram bot authentication token (required)
  - `ADMIN_IDS`: Comma-separated list of Telegram user IDs with admin privileges
  - `PRIVATE_GROUP_ID`: Comma-separated list of private group IDs for invite link generation
  - `SUBSCRIPTION_DAYS`: Default subscription duration (default: 30 days)
  - `INVITE_LINK_EXPIRE_HOURS`: Invite link expiration time (default: 1 hour)
  - `REMIND_DAYS`: Days before expiry to send reminder (default: 3 days)
  - `DB_PATH`: Database file location (default: ./subs.db)
- **Validation**: Startup checks ensure critical configuration is present, with warnings for optional settings

## Access Control
- **Admin System**: Role-based access using user ID whitelist
- **Group Management**: Multiple private groups supported through ID configuration
- **Design Philosophy**: Simple ID-based authorization suitable for small-scale bot operations
- **Contract System**: Users must accept terms before proceeding with registration

## Message Handling
- **Pattern**: Handler-based routing using decorators
- **Handler Priority**: Critical order for proper functionality:
  1. Admin date input handler (for custom subscription start dates)
  2. Contact handler (for phone number collection)
  3. Fullname text handler (for user name collection)
- **Message Types**: Support for text messages, callbacks, file attachments (payment receipts), and contact sharing
- **Keyboards**: Both inline and reply keyboard markup for user interaction

## Error Handling & Logging
- **Logging**: Structured logging with timestamps, severity levels, and context information
- **Error Recovery**: Try-catch blocks throughout to prevent bot crashes
- **User Feedback**: Informative error messages for users when operations fail
- **Configuration Validation**: Runtime checks for required environment variables with descriptive error messages

## Bot Features

### User Flow
1. `/start` command displays contract
2. User accepts contract terms
3. User shares phone number
4. User provides full name (if not available from contact)
5. Contract documents (TXT and PDF) generated and sent
6. User selects payment method and uploads receipt photo
7. Admin approves payment and assigns group(s)
8. User receives invite link(s) with expiration

### Admin Features
- `/stats` - Detailed statistics for all groups and users
- `/groups` - List of configured groups
- Payment approval with immediate or custom start date
- Single or multi-group assignment
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
- **aiosqlite**: Asynchronous SQLite database adapter
- **python-dotenv**: Environment variable management
- **reportlab**: PDF generation for contracts
- **Standard library**: asyncio, logging, datetime, typing, io, re for core functionality

## Database
- **SQLite**: Local file-based relational database
- **Access Pattern**: Single-connection async operations with proper indexing
- **Schema**: Supports user management, payment tracking, and multi-group memberships
- **Note**: Suitable for current scale; may migrate to PostgreSQL for larger deployments
