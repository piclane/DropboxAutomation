# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`schedule_to_icloud` is a macOS-only daemon that consumes RabbitMQ messages from the parent DropboxAutomation project and registers TODOs and schedules into iCloud Reminders and Calendar via AppleScript (`osascript`).

## Commands

```bash
# Install dependencies
uv sync

# Run the consumer daemon
uv run src/main.py
# or via installed script:
# PYTHONPATH=src uv run s2ic

# Tests
pytest tests/

# Formatting and linting
black .
isort .
flake8 .
```

Black and isort are configured with `line-length = 100`. Python 3.13+ is required.

## Architecture

### Flow

```
RabbitMQ (fanout exchange) → RabbitMQConsumer → process_message() → AppleScript
                                                        ↓                  ↓
                                               iCloud Reminders    iCloud Calendar
```

`main.py` is the single entry point. It connects to RabbitMQ, subscribes to a fanout exchange via an exclusive temporary queue, and calls `process_message()` for each incoming message.

### Message Processing (`main.py`)

Incoming JSON messages (produced by the parent DropboxAutomation project) contain:
- `todo`: list of `{action, deadline}` → registered as iCloud Reminders
- `schedule`: list of `{title, description, location, start_datetime, end_datetime, is_all_day}` → registered as iCloud Calendar events
- `target_individuals`: list of names used for routing and title prefixing

**Routing logic** (`get_destination()`): `ICLOUD_REMINDER_LIST` and `ICLOUD_CALENDAR_NAME` accept either a plain string or a YAML list of `{regex, destination}` entries. The first regex matching any name in `target_individuals` determines the target list/calendar.

**Name replacement**: `TARGET_INDIVIDUAL_REPLACEMENTS` is a YAML list of `{regex, replacement}` applied to each name before routing and prefix generation.

### Key Modules

- **`utils/rabbitmq_consumer.py`**: `RabbitMQConsumer` — blocking pika consumer with auto-reconnect (5-second retry on AMQP errors, max 10 unexpected errors before raising). URI format: `amqp(s)://user:pass@host:port/vhost/exchange`. Subscribes to a durable fanout exchange with an exclusive auto-delete queue.
- **`settings.py`**: Loads all config from `.env` via `python-dotenv`.

### Environment Variables

- `RABBITMQ_PUBLISH_EXCAHNGE` — required; RabbitMQ URI (note: typo "EXCAHNGE" is intentional/shared with parent project)
- `ICLOUD_REMINDER_LIST` — reminder list name or YAML routing config (default: `"Reminders"`)
- `ICLOUD_CALENDAR_NAME` — calendar name or YAML routing config (default: `"Calendar"`)
- `TARGET_INDIVIDUAL_REPLACEMENTS` — YAML list of `{regex, replacement}` for name normalization (default: `"[]"`)

## Conventions

- macOS only — AppleScript via `subprocess`/`osascript` is required
- All user-facing text and logs are in Japanese
- Shares the `RABBITMQ_PUBLISH_EXCAHNGE` typo with the parent DropboxAutomation project intentionally
- ACK is always sent (even on error) to avoid infinite requeuing