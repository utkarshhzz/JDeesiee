"""
Application configuration via Pydantic Settings.

WHY THIS FILE EXISTS:
    Every external service (PostgreSQL, Redis, Azure OpenAI, Azure AI Search)
    needs credentials and connection details. Instead of scattering os.getenv()
    calls throughout the codebase, we centralise ALL configuration here.

HOW IT WORKS:
    1. Pydantic Settings automatically reads from environment variables.
    2. You can also place values in a .env file for local development.
    3. On Azure, secrets come from Key Vault → App Service env vars → here.
    4. If a required variable is missing, the app crashes at startup with a
       clear error message — NOT at midnight when a user happens to trigger
       the code path that needs it.

USAGE:
    from app.config import settings
    print(settings.DATABASE_URL)  # Ready to use, type-safe, validated
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Candidate Discovery Engine.

    Every field maps to an environment variable of the same name.
    For example, the field `DATABASE_URL` reads from the env var `DATABASE_URL`.

    Fields with default values are optional in the .env file.
    Fields without defaults are REQUIRED — the app won't start without them.
    """

    # ──────────────────────────────────────────────────────────────────────
    # APPLICATION
    # ──────────────────────────────────────────────────────────────────────
    APP_NAME: str = "Candidate Discovery Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False  # Set True in dev for verbose logging; never in prod
    ENVIRONMENT: str = "development"  # "development", "staging", "production"

    # Comma-separated list of allowed CORS origins.
    # In production, this should be your frontend domain only.
    # Example: "https://recruit.example.com,https://staging.recruit.example.com"
    CORS_ORIGINS: str = "http://localhost:5173"  # Vite dev server default

    # ──────────────────────────────────────────────────────────────────────
    # POSTGRESQL DATABASE
    # ──────────────────────────────────────────────────────────────────────
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    # We use asyncpg (async driver) NOT psycopg2 (sync driver).
    # Why asyncpg? Because FastAPI is async, and mixing sync DB calls inside
    # async route handlers blocks the event loop → kills throughput.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/candidate_engine"

    # Connection pool settings.
    # pool_size=20: Keep 20 persistent connections to PostgreSQL.
    # max_overflow=10: Allow 10 extra connections during traffic spikes.
    # Why these numbers? Azure PostgreSQL Burstable B1ms allows max ~50
    # connections. We reserve 30 (20+10) for the app, leaving room for
    # Alembic migrations, monitoring, and manual debugging.
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


# ──────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE
# ──────────────────────────────────────────────────────────────────────────
# We create a single instance at module level. Every file that does
# `from app.config import settings` gets the SAME instance.
# This avoids re-parsing env vars on every import.
settings = Settings()
