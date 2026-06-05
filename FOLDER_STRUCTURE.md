# Project Folder Structure

```
ai-sales-simulation-pipline/
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── FOLDER_STRUCTURE.md
├── README.md
├── docker-compose.yml
│
├── sample-data/                    # Demo product specs for upload testing
│   └── product-spec.txt
│
├── docs/                           # Additional documentation
│   └── .gitkeep
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI entry + lifespan
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── auth_utils.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py
│       │   ├── auth.py
│       │   ├── admin.py
│       │   ├── sessions.py
│       │   └── export.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── embeddings.py     # Google embedding-001
│       │   ├── rag.py            # ChromaDB + text splitting
│       │   ├── gemini_chain.py   # System prompt + chat
│       │   └── session_manager.py
│       └── websocket/
│           ├── __init__.py
│           └── chat.py
│   └── tests/
│       └── .gitkeep
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.mjs
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── tsconfig.json
    ├── public/
    │   └── .gitkeep
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx
        │   └── globals.css
        ├── components/
        │   ├── AuthPanel.tsx
        │   ├── AdminDashboard.tsx
        │   ├── StudentChat.tsx
        │   └── ui/
        │       └── .gitkeep
        └── lib/
            ├── api.ts
            └── websocket.ts
```

## Runtime directories (created automatically, not in git)

| Path | Purpose |
|------|---------|
| `data/chroma/` | ChromaDB vector persistence (local dev) |
| `data/uploads/` | Uploaded PDF/TXT files (local dev) |
| `/data/chroma`, `/data/uploads` | Docker volumes for backend |
