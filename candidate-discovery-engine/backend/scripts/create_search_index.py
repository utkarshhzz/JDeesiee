"""
Azure AI Search Index Creator — Section-Level Chunked Schema.

WHAT THIS CREATES:
    An index named 'candidates-index' optimized for HYBRID search:
    - Vector search: HNSW over 1536-dim section embeddings
    - Keyword search: BM25 over section_text + skills_str
    - Semantic reranking: Microsoft's cross-encoder on top

SCHEMA:
    Each DOCUMENT in the index = one SECTION of one resume.
    A candidate with 5 sections = 5 documents in the index.
    
    Document structure:
    {
        "id": "abc123_experience",          # unique per section
        "candidate_postgres_id": "abc123",   # links back to DB
        "section_type": "experience",        # what kind of section
        "section_text": "Senior dev at...",  # full section text (BM25 + display)
        "skills_str": "Python, AWS, ...",    # comma-joined (BM25 boost)
        "location_country": "India",         # filterable
        "location_city": "Bengaluru",        # filterable
        "years_of_experience": 8,            # filterable + sortable
        "education_level": "Masters",        # filterable
        "resume_embedding": [0.01, -0.03, ...],  # 1536 floats
    }

USAGE:
    cd backend
    python -m scripts.create_search_index
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
)


def create_index() -> None:
    """Create the candidates-index with hybrid search schema."""

    credential = AzureKeyCredential(settings.AZURE_SEARCH_API_KEY)
    client = SearchIndexClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        credential=credential,
    )

    fields = [
        # ── Identity ─────────────────────────────────────────────
        # Format: "{candidate_uuid}_{section_type}"
        # e.g., "abc123_experience", "abc123_skills"
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        # Links back to candidates table in PostgreSQL
        SimpleField(
            name="candidate_postgres_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # ── Section Fields (NEW) ─────────────────────────────────
        # What type of section this is: summary, experience, skills, etc.
        SimpleField(
            name="section_type",
            type=SearchFieldDataType.String,
            filterable=True,  # Filter: "only match against experience sections"
        ),
        # The actual section text — SEARCHABLE for BM25 keyword matching
        # This is the KEY field for hybrid search:
        #   Vector search finds semantically similar sections
        #   BM25 search finds sections containing exact keywords
        SearchableField(
            name="section_text",
            type=SearchFieldDataType.String,
        ),

        # ── Metadata (same as before) ───────────────────────────
        SimpleField(
            name="location_country",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="location_city",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="years_of_experience",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="education_level",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Skills as searchable text for BM25 keyword matching
        SearchableField(
            name="skills_str",
            type=SearchFieldDataType.String,
        ),

        # ── The Vector ──────────────────────────────────────────
        # 1536 floats from OpenAI text-embedding-3-small
        # Now represents ONE SECTION, not the whole resume
        SearchField(
            name="resume_embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=settings.EMBEDDING_DIMENSIONS,
            vector_search_profile_name="hnsw-profile",
        ),
    ]

    # ── HNSW Vector Search Config ────────────────────────────────
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                parameters={
                    "m": 16,
                    "efConstruction": 400,
                    "efSearch": 128,
                    "metric": "cosine",
                },
            ),
        ],
        profiles=[
            VectorSearchProfile(
                name="hnsw-profile",
                algorithm_configuration_name="hnsw-config",
            ),
        ],
    )

    # ── Semantic Search Config (reranking) ───────────────────────
    # Semantic search uses Microsoft's cross-encoder model to RERANK
    # results. It reads section_text + skills_str and understands
    # that "ML Engineer" ≈ "Machine Learning Developer".
    semantic_config = SemanticConfiguration(
        name="semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            content_fields=[
                SemanticField(field_name="section_text"),
            ],
            keywords_fields=[
                SemanticField(field_name="skills_str"),
            ],
        ),
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # ── Build and Create Index ───────────────────────────────────
    index = SearchIndex(
        name=settings.AZURE_SEARCH_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    # Delete existing index (makes script idempotent)
    try:
        client.delete_index(settings.AZURE_SEARCH_INDEX_NAME)
        print(f"  Deleted existing index: {settings.AZURE_SEARCH_INDEX_NAME}")
    except Exception:
        pass

    result = client.create_index(index)
    print(f"\n{'=' * 60}")
    print(f"  INDEX CREATED SUCCESSFULLY (Hybrid Search Ready)")
    print(f"{'=' * 60}")
    print(f"  Name:          {result.name}")
    print(f"  Fields:        {len(result.fields)}")
    print(f"  Vector dim:    {settings.EMBEDDING_DIMENSIONS}")
    print(f"  Algorithm:     HNSW (m=16, efConstruction=400)")
    print(f"  Metric:        Cosine similarity")
    print(f"  BM25 fields:   section_text, skills_str")
    print(f"  Semantic:      section_text (content), skills_str (keywords)")
    print(f"  Endpoint:      {settings.AZURE_SEARCH_ENDPOINT}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    create_index()
