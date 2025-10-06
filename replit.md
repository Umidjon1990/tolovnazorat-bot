# Overview

This is a Telegram bot application built using the aiogram framework (Python). The bot manages user interactions, admin functionality, and private group access through invite links. The application uses SQLite (via aiosqlite) for data persistence and is configured through environment variables for deployment flexibility.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Technology**: aiogram 3.x (async Telegram Bot API wrapper)
- **Rationale**: Modern, fully asynchronous Python framework that provides type-safe interactions with Telegram's Bot API
- **Key Components**:
  - Bot instance for API communication
  - Dispatcher for handling updates and routing messages
  - Filters for command and callback query handling

## Data Storage
- **Database**: SQLite with aiosqlite (async wrapper)
- **Rationale**: Lightweight, serverless database suitable for small to medium-scale bot applications with minimal infrastructure requirements
- **Design**: Fully asynchronous database operations to prevent blocking the event loop

## Configuration Management
- **Approach**: Environment variables loaded via python-dotenv
- **Key Settings**:
  - `BOT_TOKEN`: Telegram bot authentication token (required)
  - `ADMIN_IDS`: Comma-separated list of Telegram user IDs with admin privileges
  - `PRIVATE_GROUP_ID`: Comma-separated list of private group IDs for invite link generation
- **Validation**: Startup checks ensure critical configuration is present, with warnings for optional settings

## Access Control
- **Admin System**: Role-based access using user ID whitelist
- **Group Management**: Multiple private groups supported through ID configuration
- **Design Philosophy**: Simple ID-based authorization suitable for small-scale bot operations

## Message Handling
- **Pattern**: Handler-based routing using decorators
- **Message Types**: Support for text messages, callbacks, and file attachments
- **Keyboards**: Both inline and reply keyboard markup for user interaction

## Error Handling & Logging
- **Logging**: Structured logging with timestamps and severity levels
- **Configuration Validation**: Runtime checks for required environment variables with descriptive error messages

# External Dependencies

## Telegram Bot API
- **Service**: Telegram's Bot API (via aiogram)
- **Purpose**: Core bot functionality, message delivery, user interaction
- **Integration**: Webhook or long-polling based on deployment configuration

## Python Libraries
- **aiogram**: Telegram Bot API framework (async)
- **aiosqlite**: Asynchronous SQLite database adapter
- **python-dotenv**: Environment variable management
- **Standard library**: asyncio, logging, datetime, typing for core functionality

## Database
- **SQLite**: Local file-based relational database
- **Access Pattern**: Single-connection async operations
- **Note**: May be replaced with PostgreSQL for production scalability