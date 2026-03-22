import os
from dotenv import load_dotenv
load_dotenv()

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

# ── Twilio WhatsApp ────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# ── Resend Email ───────────────────────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# ── Feature flags — auto-disabled if credentials are placeholder/missing ───────
WHATSAPP_ENABLED = bool(
    TWILIO_ACCOUNT_SID
    and TWILIO_ACCOUNT_SID != "your_account_sid_here"
    and TWILIO_AUTH_TOKEN
    and TWILIO_AUTH_TOKEN != "your_auth_token_here"
)
EMAIL_ENABLED = bool(RESEND_API_KEY and RESEND_API_KEY != "re_your_api_key_here")