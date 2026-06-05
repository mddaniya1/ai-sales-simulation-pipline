# AI Customer Simulation Platform — Implementation Schema

## Overview

Portfolio-grade sales training simulator: admins configure product knowledge and personas; students practice via real-time WebSocket chat with a Gemini-powered AI customer grounded in RAG.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         docker-compose (stack)                               │
├──────────────┬──────────────────────┬──────────────────┬────────────────────┤
│   Next.js    │      FastAPI         │   PostgreSQL     │  ChromaDB (local)  │
│   :3000      │      :8000           │   :5432          │  (embedded vol)    │
│   Admin+Chat │   REST + WebSocket   │   users/sessions │  product vectors   │
└──────┬───────┴──────────┬───────────┴────────┬─────────┴─────────┬──────────┘
       │                  │                    │                   │
       │  HTTP/WS         │  SQLAlchemy        │                   │
       └──────────────────┴────────────────────┴───────────────────┘
                                    │
                          Google Gemini API
                    (gemini-1.5-flash + embedding-001)
```

## Directory Structure

```
ai-sales-simulation-pipline/
├── ARCHITECTURE.md
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI app, CORS, lifespan
│       ├── config.py               # Pydantic settings
│       ├── database.py             # Async SQLAlchemy engine/session
│       ├── models.py               # ORM: User, Session, Message, Config
│       ├── schemas.py              # Request/response DTOs
│       ├── api/
│       │   ├── router.py           # Aggregates REST routes
│       │   ├── auth.py             # Register/login JWT
│       │   ├── admin.py            # Upload PDF, scenario, persona
│       │   ├── sessions.py         # Create/list simulation sessions
│       │   └── export.py           # JSON/CSV transcript export
│       ├── services/
│       │   ├── embeddings.py       # Google embedding-001 wrapper
│       │   ├── rag.py              # Split, ingest, retrieve (ChromaDB)
│       │   ├── gemini_chain.py     # System prompt + Gemini chat loop
│       │   └── session_manager.py  # In-memory scopes (max 20 concurrent)
│       └── websocket/
│           └── chat.py             # WS protocol + logging
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.mjs
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── tsconfig.json
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx            # Split Admin + Student UI
        │   └── globals.css
        ├── components/
        │   ├── AdminDashboard.tsx
        │   ├── StudentChat.tsx
        │   └── ui/                 # Shared primitives
        └── lib/
            ├── api.ts              # REST client
            └── websocket.ts        # WS client helper
```

## Data Model (PostgreSQL)

| Table | Purpose | Key fields |
|-------|---------|------------|
| `users` | Login | `id`, `email`, `hashed_password`, `role` (admin/student) |
| `simulation_configs` | Active training setup | `sales_context`, `hidden_persona`, `document_filename`, `chroma_collection` |
| `simulation_sessions` | Per-student run | `user_id`, `config_id`, `status`, `started_at`, `ended_at` |
| `message_logs` | Transcript | `session_id`, `timestamp`, `sender_role`, `content` |

## RAG Pipeline

1. Admin uploads PDF/TXT → saved under `uploads/`.
2. `RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)` splits text.
3. Each chunk embedded via `models/embedding-001` (Google GenAI).
4. Vectors stored in ChromaDB collection keyed by `config_id`.
5. On each student message: top-k similarity retrieve → inject into `{context}` in system prompt.

## Conversation Core

- Model: `gemini-1.5-flash`
- System prompt: exact template from requirements with `{sales_context}`, `{hidden_persona}`, `{context}`.
- Per-session `SessionMemory`: list of `(role, content)` for Gemini multi-turn; isolated by `session_id`.
- `SessionManager`: dict capped at 20 active WS connections; evicts LRU when full.

## WebSocket Protocol

**Client → Server**

```json
{ "type": "message", "content": "string" }
{ "type": "ping" }
```

**Server → Client**

```json
{ "type": "message", "role": "ai_customer", "content": "string", "timestamp": "ISO8601" }
{ "type": "error", "detail": "string" }
{ "type": "session_ready", "session_id": "uuid" }
```

## REST API Surface

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create user |
| POST | `/api/auth/login` | JWT token |
| GET | `/api/admin/config` | Current simulation config |
| PUT | `/api/admin/config` | Update scenario + persona |
| POST | `/api/admin/upload` | Multipart PDF/TXT ingest |
| POST | `/api/sessions` | Start session (student) |
| GET | `/api/sessions/{id}/messages` | History |
| GET | `/api/export/logs` | Query `format=json|csv` |

## Security

- JWT bearer on protected routes; WebSocket validates token query param.
- Passwords: bcrypt via `passlib`.
- CORS restricted to frontend origin.
- File upload: extension whitelist, size limit, sanitized filenames.
- Secrets only via environment variables.

## Environment Variables

See `.env.example` for `DATABASE_URL`, `GOOGLE_API_KEY`, `JWT_SECRET`, `CHROMA_PERSIST_DIR`, `MAX_CONCURRENT_SESSIONS`.
