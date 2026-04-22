

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "JDEesiee"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False 
    ENVIRONMENT: str = "development"


    CORS_ORIGINS: str = "http://localhost:5173"  # Vite dev server default

    # ──────────────────────────────────────────────────────────────────────
    # POSTGRESQL DATABASE
    # ──────────────────────────────────────────────────────────────────────
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    # We use asyncpg (async driver) NOT psycopg2 (sync driver).
    # Why asyncpg? Because FastAPI is async, and mixing sync DB calls inside
    # async route handlers blocks the event loop → kills throughput.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/JDEesiee"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ──────────────────────────────────────────────────────────────────────
    # REDIS CACHE
    # ──────────────────────────────────────────────────────────────────────
    # Used for: JD embedding cache (TTL 24h), rate limiting counters,
    # and session data.
    REDIS_URL: str = "redis://localhost:6379/0"

    # TTL for cached JD embeddings in seconds (24 hours).
    # Why 24 hours? JDs don't change frequently, and embeddings are
    # deterministic (same text → same vector). 24h balances freshness
    # with cost savings (each embedding call costs ~$0.00002).
    EMBEDDING_CACHE_TTL: int = 86400

    # ──────────────────────────────────────────────────────────────────────
    # AZURE OPENAI
    # ──────────────────────────────────────────────────────────────────────
    # These come from your Azure OpenAI resource in the Azure Portal.
    # Navigate to: Azure Portal → Azure OpenAI → Keys and Endpoint
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""  # e.g. "https://myresource.openai.azure.com/"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"

    # Deployment names — you create these when you deploy models in Azure OpenAI Studio.
    # These are NOT the model names; they're YOUR chosen deployment names.
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "gpt-4o-mini"

    # ──────────────────────────────────────────────────────────────────────
    # AZURE AI SEARCH
    # ──────────────────────────────────────────────────────────────────────
    # Navigate to: Azure Portal → Azure AI Search → Keys
    AZURE_SEARCH_ENDPOINT: str = ""  # e.g. "https://mysearch.search.windows.net"
    AZURE_SEARCH_API_KEY: str = ""
    AZURE_SEARCH_INDEX_NAME: str = "candidates-index"

    # ──────────────────────────────────────────────────────────────────────
    # AZURE BLOB STORAGE (for raw JD file archive)
    # ──────────────────────────────────────────────────────────────────────
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "jd-uploads"

    # ──────────────────────────────────────────────────────────────────────
    # AZURE APPLICATION INSIGHTS (Enhancement H — OpenTelemetry)
    # ──────────────────────────────────────────────────────────────────────
    # Connection string for Azure Monitor/Application Insights.
    # Format: "InstrumentationKey=...;IngestionEndpoint=..."
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""

    # ──────────────────────────────────────────────────────────────────────
    # WEBHOOKS
    # ──────────────────────────────────────────────────────────────────────
    # Default webhook URL for n8n or Power Automate.
    # Triggered when a candidate scores > 90.
    WEBHOOK_DEFAULT_URL: str = ""

    # HMAC secret used to sign webhook payloads so the receiver
    # (n8n/Power Automate) can verify they came from us.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    WEBHOOK_HMAC_SECRET: str = "change-me-in-production"

    # ──────────────────────────────────────────────────────────────────────
    # SECURITY
    # ──────────────────────────────────────────────────────────────────────
    # Secret key for JWT token validation.
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # ──────────────────────────────────────────────────────────────────────
    # RATE LIMITING (Feature F)
    # ──────────────────────────────────────────────────────────────────────
    # Max searches per recruiter per hour.
    RATE_LIMIT_SEARCHES_PER_HOUR: int = 30

    # Monthly OpenAI spend budget in USD. When exceeded, LLM reasoning
    # is disabled and we fall back to vector-only scoring.
    MONTHLY_OPENAI_BUDGET_USD: float = 50.0

    # ──────────────────────────────────────────────────────────────────────
    # PROMPT A/B TESTING (Enhancement K)
    # ──────────────────────────────────────────────────────────────────────
    # Enable/disable the A/B testing framework.
    # When disabled, always uses the production prompt.
    ENABLE_PROMPT_AB_TESTING: bool = False

    # ──────────────────────────────────────────────────────────────────────
    # Pydantic Settings Configuration
    # ──────────────────────────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        # Look for a .env file in the backend/ directory
        env_file=".env",
        # If the .env file doesn't exist, don't crash — use defaults
        env_file_encoding="utf-8",
        # Allow extra fields (future-proofing for new env vars)
        extra="ignore",
        # Case-sensitive env var matching
        case_sensitive=True,
    )

settings = Settings()
