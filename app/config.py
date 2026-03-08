import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH     = os.path.join(BASE_DIR, "memory_db")        # ChromaDB persistent store

# ── Embedding model ────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── ChromaDB collections (one per memory type) ─────────────────────────────────
COLLECTION_GENERAL     = "general_memory"
COLLECTION_PREFERENCES = "user_preferences"
COLLECTION_HABITS      = "user_habits"

# ── Retrieval settings ─────────────────────────────────────────────────────────
SIMILARITY_RESULTS    = 4
SIMILARITY_THRESHOLD  = 0.65