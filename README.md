# AI Customer Simulation Platform

Portfolio-ready **sales training simulator**: administrators configure product knowledge and hidden customer personas; students practice live pitches against a **Gemini-powered AI customer** with **RAG** grounding and **WebSocket** real-time chat.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full file tree, data model, RAG pipeline, and WebSocket protocol.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, WebSockets, SQLAlchemy (async), PostgreSQL |
| LLM / Embeddings | Google Gemini (`gemini-1.5-flash`, `models/embedding-001`) |
| RAG | LangChain `RecursiveCharacterTextSplitter`, ChromaDB (persistent) |
| Frontend | Next.js 14, React, Tailwind CSS |
| Deploy | Docker Compose |

## Quick Start (Docker)

1. **Copy environment file** and add your Google API key:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `GOOGLE_API_KEY=...` and a strong `JWT_SECRET`.

2. **Start the stack**:

   ```bash
   docker compose up --build
   ```

3. Open **http://localhost:3000**

4. **Register** an **admin** account, then:
   - Upload `sample-data/product-spec.txt` (or a PDF)
   - Set selling scenario context and hidden persona
   - Save configuration

5. Register a **student** account (or use another browser), start a simulation, and chat.

6. As admin, use **Export JSON / CSV** to download timestamped transcripts.

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run PostgreSQL locally and set `DATABASE_URL` in `.env`, then:

```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` in `frontend/.env.local`.

## API Highlights

- `POST /api/auth/register` · `POST /api/auth/login`
- `GET/PUT /api/admin/config` · `POST /api/admin/upload`
- `POST /api/sessions` · `WS /ws/chat/{session_id}?token=JWT`
- `GET /api/export/logs?format=json|csv` (admin)

## Psychological Prompt Engine

The exact system prompt template from the project spec is implemented in:

`backend/app/services/gemini_chain.py`

Variables: `{sales_context}`, `{hidden_persona}`, `{context}` (RAG retrieval).

## Concurrency

`SessionManager` maintains isolated in-memory chat history per session, capped at **20** concurrent WebSocket scopes (LRU eviction).

## Security Notes

- JWT authentication on REST and WebSocket (`?token=`)
- Bcrypt password hashing
- Upload extension whitelist and size limits
- Never commit `.env` with real API keys

## License

MIT — suitable for portfolio demonstration.
