# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DropboxAutomation is a Python application that processes PDF files using Claude AI. It extracts metadata (date, title, summary, TODOs, schedules), renames files, generates HTML summaries, and optionally publishes results to RabbitMQ. It supports two execution modes: Dropbox webhook monitoring and local file processing. The application is optimized for Japanese-language PDF documents.

## Commands

```bash
# Install dependencies
uv sync

# Run in local file mode (single PDF)
uv run src/main.py /path/to/file.pdf
# or if you prefer using the installed script:
# PYTHONPATH=src uv run dropbox-automation /path/to/file.pdf

# Run in webhook mode (Dropbox monitoring, starts FastAPI on port 3003)
uv run src/main.py
# or:
# PYTHONPATH=src uv run dropbox-automation

# Tests
pytest tests/

# Formatting and linting
black .
isort .
flake8 .
```

Black and isort are configured with `line-length = 100`.

## Architecture

### Execution Modes

`main.py` is the entry point. It routes to one of two processors based on whether a file path argument is provided:

- **Local mode** (`processer_local.py`): Processes a single PDF from the filesystem. Outputs a renamed PDF + HTML summary in the same directory.
- **Webhook mode** (`processor_dropbox.py`): Runs a FastAPI server with `GET /webhook` (Dropbox challenge verification) and `POST /webhook` (file change processing). Downloads PDFs from Dropbox, processes them, and uploads results back.

### Processing Pipeline

```
PDF file → ai.py (analyze_with_claude) → LlmProcessor (Claude Sonnet) → JSON result
                                                                            ↓
                                              ┌─────────────────────────────┤
                                              ↓                             ↓
                                    PDF rename + HTML summary     RabbitMQ publish (optional)
```

### Key Modules

- **`ai.py`**: Orchestrates PDF analysis using `claude-sonnet-4-6` via LangChain. Returns JSON with `date`, `title`, `summary`, `todo`, `schedule`, `target_individuals`.
- **`prompts.py`**: Defines `PdfSummaryPrompt` with detailed extraction rules (date formats, title constraints, summary formatting, schedule/TODO structure).
- **`utils/llm_processor.py`**: Wraps Claude API via `ChatAnthropic`. Key classes: `LlmProcessor`, `LlmResult` (generic response wrapper), `PromptDescribe` (abstract), `LocalFilePromptDescribe` (Base64 file encoding), `PlainPromptDescribe`.
- **`utils/rabbitmq_publisher.py`**: Uses factory pattern (`create_publisher()`) returning either `RabbitMQPublisher` or `NullPublisher` (no-op when `RABBITMQ_PUBLISH_EXCHANGE` is unset). Publishers are context managers.
- **`utils/summarizer.py`**: Converts analysis JSON to styled HTML with tables for TODOs and schedules.
- **`utils/pdf.py`**: PDF annotation using PyMuPDF.
- **`utils/dbx.py`**: Dropbox OAuth client initialization.
- **`settings.py`**: Loads all configuration from environment variables (via `.env`).

### Environment Variables

- `CLAUDE_API_KEY` — required always
- `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` — required for webhook mode
- `DROPBOX_FOLDER_PATH` — Dropbox folder to monitor
- `PORT` — webhook server port (default: 3003)
- `FILE_PREFIX` — file prefix filter (default: "BR")
- `TARGET_INDIVIDUALS` — YAML list of names to match in documents
- `RABBITMQ_PUBLISH_EXCHANGE` — RabbitMQ exchange URI (optional)

## Conventions

- Python 3.11+ required (`.python-version`: 3.11.4)
- Package management via **uv** (not pip/poetry)
- Build backend: hatchling
- All user-facing text (prompts, summaries, logs) is in Japanese
- Note the typo in `processer_local.py` filename (one 's') — this is intentional/existing
