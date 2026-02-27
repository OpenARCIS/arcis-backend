<p align="center">
  <h1 align="center">ARCIS</h1>
  <p align="center"><b>Autonomous Reasoning and Contextual Intelligence System</b></p>
  <p align="center">
    A multi-agent AI backend powered by LangGraph that autonomously manages emails, schedules, bookings, and conversations — with voice synthesis, long-term memory, and human-in-the-loop oversight.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/framework-FastAPI-009688?style=flat-square" />
  <img src="https://img.shields.io/badge/orchestration-LangGraph-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/database-MongoDB-47A248?style=flat-square" />
  <img src="https://img.shields.io/badge/memory-Qdrant-DC382D?style=flat-square" />
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
  - [To Do](#to-do)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Docker Installation](#docker-installation)
  - [Environment Variables](#environment-variables)
  - [Google OAuth Setup](#google-oauth-setup)
  - [Pocket TTS Setup](#pocket-tts-setup)
  - [Running the Server](#running-the-server)
- [System Architecture](#system-architecture)
  - [High-Level Architecture](#high-level-architecture)
  - [Project Structure](#project-structure)
  - [Core Components](#core-components)
  - [Agent System](#agent-system)
  - [Memory System](#memory-system)
  - [LLM Provider System](#llm-provider-system)
- [Workflows](#workflows)
  - [Manual Workflow (Chat)](#manual-workflow-chat)
  - [Autonomous Workflow (Email Processing)](#autonomous-workflow-email-processing)
  - [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl)
- [API Reference](#api-reference)
  - [Chat](#chat)
  - [Gmail Authentication](#gmail-authentication)
  - [Calendar](#calendar)
  - [Autonomous Flow](#autonomous-flow)
  - [Onboarding](#onboarding)
  - [Settings](#settings)

---

## Overview

**ARCIS** is an AI-powered personal assistant backend built on **FastAPI** and **LangGraph**. It uses a multi-agent architecture where specialized agents collaborate to handle complex tasks — from drafting emails and managing your calendar to searching the web and making bookings.



---

## Features

- 🤖 **Multi-Agent Orchestration** — Planner → Supervisor → Specialized Agents → Replanner loop
- 📧 **Gmail Integration** — Read, compose, and send emails via Google OAuth 2.0
- 📅 **Calendar Management** — Events, todos, and reminders via built in Calendar
- 🧠 **Dual Memory System** — Short-term (LangGraph checkpoints) + Long-term (Qdrant semantic search)
- 🗣️ **Text-to-Speech** — Real-time voice synthesis via Pocket TTS with custom voice cloning
- 🔄 **Human-in-the-Loop** — Agents can pause and ask for user input on sensitive actions
- 🎯 **User Onboarding** — LLM-powered conversational interview that learns user preferences
- ⚙️ **Dynamic LLM Config** — Switch models/providers per agent at runtime via the settings API
- 🔌 **Multi-Provider LLM** — Supports Gemini, Groq, Cerebras, Mistral, OpenRouter or any OpenAI compatible API
- 📊 **Token Tracking** — Per-agent token usage monitoring

### To Do

- [ ] Add MCP agent
- [ ] Add specialized coding agent
- [ ] Refactor all codes
- [ ] Add Telegram as a message channel
- [ ] Add login page
- [ ] Add speech to text
- [ ] Add files to chat (also add VLM)
- [ ] Change system prompts to include agent skills
- [ ] Optimize checkpointing memory
- [ ] Add cron jobs

---

## Getting Started

### Prerequisites

| Dependency | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **MongoDB** | 6.0+ | Primary database, checkpointer, chat history |
| **Qdrant** | 1.7+ | Vector database for long-term semantic memory |

### Installation

```bash
# Clone the repository
git clone https://github.com/OpenARCIS/arcis-backend.git
cd arcis-backend

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Docker Installation

You can also run ARCIS using Docker. A minimal Dockerfile is provided.

```bash
# Build the Docker image
docker build -t arcis-backend .

# Run the container (make sure to pass the .env file if needed)
docker run -p 8501:8501 --env-file .env arcis-backend
```

### Environment Variables

Create a `.env` file in the project root. The server loads it automatically in non-production environments.

#### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | MongoDB connection string | `mongodb://user:pass@host:27017/` |
| `DATABASE_NAME` | MongoDB database name | `arcis_db` |

#### LLM API Keys

You need **at least one** LLM provider key. The system uses a factory pattern, so only the providers you configure for your agents need keys.

| Variable | Provider | Used For |
|----------|----------|----------|
| `GEMINI_API` | Google Gemini | LLM inference + online embeddings |
| `GROQ_API_KEY` | Groq | Fast inference (Llama, Qwen, etc.) |
| `CEREBRAS_API_KEY` | Cerebras | Llama inference |
| `MISTRAL_API_KEY` | Mistral AI | Mistral/Ministral models |
| `OPENROUTER_API_KEY` | OpenRouter | Access to 100+ models via unified API |

#### Google OAuth (Gmail & Calendar)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLIENT_SECRETS_FILE` | Path to Google OAuth credentials JSON | `google_credentials.json` |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/` |
| `OAUTHLIB_INSECURE_TRANSPORT` | Allow HTTP for local testing (set `1`) | `1` |

#### Qdrant (Long-Term Memory)

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API key (if using Qdrant Cloud) | `None` |
| `EMBEDDING_MODE` | `offline` (FastEmbed/CPU) or `online` (Gemini API) | `offline` |

#### TTS (Pocket TTS)

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_DEFAULT_VOICE` | Default voice preset name for Pocket TTS | `alba` |

#### Example `.env`

```env
# Database
DATABASE_URL=mongodb://user:password@localhost:27017/
DATABASE_NAME=arcis_db

# LLM Providers (add keys for providers you use)
GEMINI_API=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
MISTRAL_API_KEY=your_mistral_api_key
CEREBRAS_API_KEY=your_cerebras_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Google OAuth
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/auth/callback

# Qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_MODE=offline

# TTS (check Pocket TTS docs for more info on available voices)
TTS_DEFAULT_VOICE=alba
```

### Google OAuth Setup

ARCIS uses **Google OAuth 2.0** to access Gmail and Google Calendar on behalf of the user.

1. **Create a Google Cloud project** at [console.cloud.google.com](https://console.cloud.google.com/).
2. **Enable APIs**: Gmail API, Google Calendar API.
3. **Create OAuth 2.0 credentials** (Web application type).
4. **Add redirect URI**: Set it to match your `GOOGLE_REDIRECT_URI` env var (e.g., `http://localhost:8000/gmail/auth/callback`).
5. **Download** the credentials JSON and save it as `google_credentials.json` in the project root.

The JSON file should have this structure (generated by Google Cloud Console):
```json
{
  "web": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "client_secret": "your-client-secret",
    "redirect_uris": ["http://localhost:8000/gmail/auth/callback"],
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

**OAuth Scopes requested:**
- `gmail.send` — Send emails
- `gmail.readonly` — Read emails
- `gmail.compose` — Draft and compose emails

Once the server is running, authenticate by visiting `/gmail/auth/login`. The user's credentials are stored in MongoDB and refreshed automatically.

### Pocket TTS Setup

ARCIS uses [**Pocket TTS**](https://github.com/kyutai-labs/pocket-tts) for real-time text-to-speech with voice cloning.

- TTS model is loaded **on server startup** (runs in a thread executor to avoid blocking).
- The default voice is set via `TTS_DEFAULT_VOICE` (e.g., `alba`, a built-in preset).
- **Custom voices** can be uploaded at runtime via the `/chat/voice-upload` endpoint (accepts `.wav` files).
- Audio is streamed sentence-by-sentence as **Base64-encoded WAV** over Server-Sent Events (SSE).

> NOTE: TTS initialization can take a few seconds on first startup as the model loads into memory. If TTS fails to initialize, the server will still start — TTS endpoints will return error messages gracefully.

### Running the Server

```bash
# Run the server (default: port 8501)
python -m arcis

# Or with uvicorn directly
uvicorn arcis.__main__:api_server --host 0.0.0.0 --port 8501 --reload
```

The API documentation is available at:
- **Swagger UI**: `http://localhost:8501/docs`
- **ReDoc**: `http://localhost:8501/redoc`

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ARCIS Backend                              │
│                                                                     │
│  ┌───────────┐    ┌─────────────────────────────────────────────┐   │
│  │ FastAPI   │    │              Core Engine                    │   │
│  │ Routers   │──> │                                             │   │
│  │           │    │  ┌───────────────────────────────────────┐  │   │
│  │ • Chat    │    │  │         LangGraph Workflows           │  │   │
│  │ • Gmail   │    │  │                                       │  │   │
│  │ • Calendar│    │  │  ┌────────────────────────────────┐   │  │   │
│  │ • AutoFlow│    │  │  │            Inputs              │   │  │   │
│  │ • Settings│    │  │  │                                │   │  │   │
│  │ • Onboard │    │  │  └───────────────┬────────────────┘   │  │   │
│  └───────────┘    │  │                  │                    │  │   │
│                   │  │                  ▼                    │  │   │
│                   │  │  ┌───────────────────────────────┐    │  │   │
│                   │  │  │      Agent Pipeline           │    │  │   │
│                   │  │  │ Planner → Supervisor → Agents │    │  │   │
│                   │  │  │           → Replanner         │    │  │   │
│                   │  │  └───────────────────────────────┘    │  │   │
│                   │  └───────────────────────────────────────┘  │   │
│                   │                                             │   │
│                   │  ┌────────┐  ┌─────────┐  ┌──────────────┐  │   │
│                   │  │  TTS   │  │  Gmail/ │  │ LLM Factory  │  │   │
│                   │  │Manager │  │ Calendar│  │(5+ providers)│  │   │
│                   │  └────────┘  └─────────┘  └──────────────┘  │   │
│                   └─────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────┐  ┌────────────────────┐                     │
│  │ MongoDB            │  │ Qdrant             │                     │
│  │ • User data        │  │ • Long-term memory │                     │
│  │ • Chat history     │  │ • Semantic search  │                     │
│  │ • Checkpoints      │  │ • User profile     │                     │
│  │ • Settings         │  │                    │                     │
│  └────────────────────┘  └────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
arcis-backend/
├── config.py                    # Environment variable loading & Config class
├── google_credentials.json      # Google OAuth client credentials
├── requirements.txt             # Python dependencies
│
└── arcis/                       # Main application package
    ├── __init__.py               # Exports Config
    ├── __main__.py               # FastAPI app, lifespan, middleware, router registration
    │
    ├── core/                     # Business logic
    │   ├── external_api/         # Third-party API wrappers
    │   │   ├── google.py         # Base Google API (OAuth credential loading)
    │   │   ├── gmail.py          # Gmail API wrapper (read/send/draft)
    │   │   └── calendar.py       # Google Calendar wrapper
    │   │
    │   ├── llm/                  # LLM infrastructure
    │   │   ├── factory.py        # LLMFactory — multi-provider client creation
    │   │   ├── providers.py      # LLMProvider enum (Gemini, Groq, etc.)
    │   │   ├── config_manager.py # Dynamic per-agent model configuration
    │   │   ├── llm_list.py       # Available models per provider
    │   │   ├── prompts.py        # System prompts for all agents
    │   │   ├── long_memory.py    # Qdrant-backed semantic memory (singleton)
    │   │   ├── short_memory.py   # MongoDB checkpointer for LangGraph
    │   │   ├── chat_history.py   # Decoupled chat history storage
    │   │   ├── memory_extractor.py # LLM-based fact extraction from conversations
    │   │   └── pending_interrupt.py # Pending HITL interrupt storage
    │   │
    │   ├── onboarding/           # User onboarding system
    │   │   └── interviewer.py    # Multi-turn LLM interview → Qdrant storage
    │   │
    │   ├── tts/                  # Text-to-Speech
    │   │   └── tts_manager.py    # Pocket TTS model management & streaming
    │   │
    │   ├── utils/                # Utility modules
    │   │   ├── token_tracker.py  # Per-agent token usage tracking
    │   │   └── emotion_tracker.py # User emotion analysis
    │   │
    │   ├── workflow_manual/      # Manual (chat) workflow
    │   │   ├── manual_flow.py    # LangGraph graph definition & runner
    │   │   ├── agents/           # Agent node implementations
    │   │   │   ├── planner.py    # Decomposes requests into step-by-step plans
    │   │   │   ├── supervisor.py # Routes steps to the correct agent
    │   │   │   ├── email_agent.py    # Handles email-related tasks
    │   │   │   ├── booking_agent.py  # Handles booking/travel tasks
    │   │   │   ├── utility_agent.py  # Handles general tasks (search, calendar, etc.)
    │   │   │   └── replanner.py      # Evaluates progress, re-plans if needed
    │   │   └── tools/            # LangChain tools available to agents
    │   │       ├── email.py      # Send/draft email tool
    │   │       ├── calendar.py   # Calendar read/write tool
    │   │       ├── booking.py    # Booking/reservation tool
    │   │       ├── web_search.py # DuckDuckGo web search tool
    │   │       └── memory_search.py # Long-term memory search tool
    │   │
    │   └── workflow_auto/        # Autonomous (email processing) workflow
    │       ├── auto_flow.py      # Auto-flow graph, batch processor, interrupt resolver
    │       └── nodes/
    │           └── analyzer.py   # Email analysis node (replaces planner for auto)
    │
    ├── database/
    │   └── mongo/
    │       └── connection.py     # Motor async MongoDB client & collection registry
    │
    ├── models/                   # Pydantic & TypedDict models
    │   ├── agents/
    │   │   └── state.py          # AgentState & PlanStep (LangGraph state schema)
    │   ├── llm.py                # LLMProvider enum
    │   └── errors.py             # Custom exceptions
    │
    ├── router/                   # FastAPI route handlers
    │   ├── routes.py             # Root/test routes
    │   ├── chat.py               # Chat endpoints (text + TTS streaming)
    │   ├── gmail.py              # Google OAuth login/callback/status/logout
    │   ├── calendar.py           # Calendar events/todos/reminders
    │   ├── auto_flow.py          # Pending interrupts management
    │   ├── settings.py           # Agent LLM configuration CRUD
    │   ├── onboarding.py         # Onboarding interview endpoints
    │   ├── user_status.py        # User status tracking
    │   └── token_tracker.py      # Token usage reporting
    │
    └── utils/
        └── text.py               # Text formatting utilities
```

### Core Components

#### LLM Factory (`core/llm/factory.py`)

The LLM Factory uses a **provider-agnostic pattern** to create LangChain chat model clients. Each agent can be configured to use a different provider and model.

**Supported Providers:**

| Provider | SDK | Models |
|----------|-----|--------|
| **Gemini** | `langchain-google-genai` | gemini-1.5-flash, gemini-2.0-flash, etc. |
| **Groq** | `langchain-openai` (compatible) | llama-3.1-8b-instant, qwen3-32b, etc. |
| **Cerebras** | `langchain-openai` (compatible) | llama3.1-8b |
| **Mistral AI** | `langchain-mistralai` | ministral-8b, mistral-small, etc. |
| **OpenRouter** | `langchain-openai` (compatible) | 100+ models via unified API |

#### Config Manager (`core/llm/config_manager.py`)

A **singleton** that manages per-agent LLM configurations. Configs are loaded from MongoDB on startup and fall back to built-in defaults. Agents can be reconfigured at runtime through the `/settings/agents` API without restarting the server.

#### TTS Manager (`core/tts/tts_manager.py`)

Manages the Pocket TTS model lifecycle:
- Loads the TTS model on startup in a background thread
- Maintains a registry of voice states (default + user-uploaded)
- Streams audio sentence-by-sentence as Base64-encoded WAV via SSE
- Custom voice cloning from uploaded `.wav` reference files

### Agent System

The agent pipeline is the heart of ARCIS. Each agent is a **LangGraph node** that receives the shared `AgentState` and performs its specialized role.

| Agent | Role | Tools |
|-------|------|-------|
| **Planner** | Decomposes user requests into a step-by-step plan with agent assignments | — |
| **Supervisor** | Routes the current pending step to the correct specialist agent | — |
| **EmailAgent** | Drafts, sends, and manages emails | `send_email`, `draft_email` |
| **BookingAgent** | Handles travel, reservations, and booking searches | `search_bookings`, `book_reservation` |
| **UtilityAgent** | General-purpose tasks: web search, calendar ops, memory queries | `web_search`, `calendar_tool`, `memory_search` |
| **Replanner** | Evaluates execution results and decides whether to continue, retry, or finish | — |
| **Analyzer** | *(Auto flow only)* Analyzes incoming emails and generates action plans | — |

#### Agent State

```python
class AgentState(TypedDict):
    thread_id: Optional[str]       # Conversation thread identifier
    input: str                     # Original user request
    plan: List[PlanStep]           # Decomposed task plan
    messages: Annotated[list, add_messages]  # Auto-accumulated conversation history
    context: Dict[str, Any]        # Accumulated context between agents
    last_tool_output: str          # Output from the last tool execution
    final_response: str            # Final user-facing response
    current_step_index: int        # Current step being executed
    next_node: Optional[str]       # Next agent to route to
    workflow_status: Optional[str] # CONTINUE | FINISHED | FAILED
```

### Memory System

ARCIS uses a **dual memory architecture**:

#### Short-Term Memory (MongoDB)
- **LangGraph Checkpointer** — Stores graph state between turns, enabling multi-turn conversations and workflow resumption.
- **Chat History** — Decoupled message log for frontend display (separate from LangGraph's internal state).

#### Long-Term Memory (Qdrant)
- **Semantic Vector Store** — Stores facts, preferences, and learned information as embeddings.
- **Categories**: `user_profile`, `preference`, `key_detail`, `learned_fact`
- **Embedding Modes**:
  - `offline` — FastEmbed (`BAAI/bge-small-en-v1.5`, 384-dim) — runs on CPU, no API calls
  - `online` — Gemini Embedding API (768-dim) — higher quality, requires API key
- **Memory Extraction** — After each conversation, an LLM analyzes the dialogue and extracts key facts, deduplicating against existing memories (cosine similarity threshold: 0.85).

### LLM Provider System

The system uses a **factory + config manager** pattern:

```
User Request
    ↓
Config Manager (get agent config from MongoDB / defaults)
    ↓
LLM Factory (create client for the configured provider)
    ↓
LangChain Chat Model (Gemini / Groq / Cerebras / Mistral / OpenRouter)
```

Default agent configurations can be viewed and updated via the `/settings` API, persisted to MongoDB.

---

## Workflows

### Manual Workflow (Chat)

The manual workflow is triggered when a user sends a message through the `/chat` endpoint.

**Flow:**
1. **Planner** receives the user message and conversation history. For simple queries (greetings, questions), it responds directly and ends. For complex tasks, it generates a structured plan with steps assigned to specific agents.
2. **Supervisor** examines the plan, finds the next pending step, and routes to the assigned agent.
3. **Specialist Agent** (Email/Booking/Utility) executes the step using its tools, updates the context with results.
4. **Replanner** evaluates the outcome. If the step succeeded, it marks it complete and checks for remaining steps. If it failed, it can generate corrective steps. Routes back to Supervisor if more work remains, or ends the workflow.
5. After completion, the **Memory Extractor** analyzes the conversation and stores key facts in long-term memory.

**Conversation Persistence:** Each conversation has a `thread_id`. The LangGraph checkpointer (MongoDB) preserves the full graph state, enabling:
- Multi-turn conversations within the same thread
- Resuming interrupted workflows
- Maintaining context across messages

### Autonomous Workflow (Email Processing)

The autonomous flow runs as a background task, processing unread emails without user interaction.

**Flow:**
1. Fetches the latest unread emails from Gmail.
2. **Analyzer** (replaces Planner) examines each email and decides if action is needed. Newsletters, spam, and FYI emails are ignored.
3. Actionable emails are routed through the same **Supervisor → Agent → Replanner** pipeline as the manual flow.
4. If an agent needs user confirmation (e.g., sending a reply, making a booking), it triggers an **interrupt** — the workflow pauses and a pending item is saved to MongoDB.
5. Users can review pending items via the `/auto_flow/pending` API and either **resolve** (provide an answer) or **dismiss** them.

### Human-in-the-Loop (HITL)

Agents can pause workflow execution when they need user input by using LangGraph's `interrupt()` mechanism:

- In the **Manual Flow**: The API returns an `interrupt` response type. The frontend displays the question and the user's reply resumes the graph.
- In the **Autonomous Flow**: Interrupts are saved as **pending items** in MongoDB. Users review them through the pending items API.

---

## API Reference

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send a message to the manual workflow. Returns JSON with the AI response. |
| `POST` | `/chat/stream` | Send a message and receive TTS audio streamed via SSE. |
| `POST` | `/chat/voice-upload` | Upload a `.wav` file as a custom voice for TTS. |
| `GET` | `/chat/all_chats` | List all conversation threads (for sidebar). |
| `GET` | `/chat/{thread_id}` | Get full message history for a thread. |

**Chat Request Body:**
```json
{
  "message": "Send an email to John about the meeting",
  "thread_id": "optional-uuid-for-existing-thread"
}
```

### Gmail Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/gmail/auth/login` | Get Google OAuth login URL. |
| `GET` | `/gmail/auth/callback` | OAuth callback — exchanges code for credentials. |
| `GET` | `/gmail/auth/status` | Check if user is authenticated. |
| `GET` | `/gmail/auth/logout` | Remove stored Gmail credentials. |

### Calendar

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/calendar/events` | Fetch calendar events in a time range. |
| `GET` | `/calendar/todos` | Fetch todos in a time range. |
| `GET` | `/calendar/reminders` | Fetch reminders in a time range. |

Query parameters: `start_time` and `end_time` (ISO 8601 format).

### Autonomous Flow

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/auto_flow/pending` | List all pending interrupt items. |
| `POST` | `/auto_flow/resolve` | Resolve a pending item with user answer. |
| `POST` | `/auto_flow/dismiss` | Dismiss a pending item. |

### Onboarding

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/onboarding/start` | Start a new onboarding interview session. |
| `POST` | `/onboarding/respond` | Send answer, receive next question. |
| `GET` | `/onboarding/status` | Check if user has completed onboarding. |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/models` | Get available LLM models grouped by provider. |
| `GET` | `/settings/agents` | Get current LLM config for all agents. |
| `PUT` | `/settings/agents` | Update LLM config for agents (provider, model, temperature). |

---

<p align="center">
  Built with ❤️ using FastAPI, LangGraph, and a whole lot of LLMs.
</p>