# embedding geenrator - CHunks resume ,embeds sections ,uplaods to azure ai search

# how
# first fetch all candidates withoutembeddingd vector id in null
# chunks each resume into sections (summary,experince,skills,etc)
# generate openai embedingd ini batches of 100
# upload search documents to azure ai sarch in batches of 1000
# update vector id in supabase to mark a processed


from pydantic.v1.utils import generate_model_signature
import structlog
import asyncio
import json
import sys
import uuid
from pathlib import Path

from openai import OpenAI
from tenacity import retry,wait_exponential,stop_after_attempt,retry_if_exception_type
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tqdm import tqdm

# ── Setup Python path ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings
from app.core.logging import setup_logging
from app.services.chunker import chunk_resume
import structlog

setup_logging(debug=True)
logger=structlog.get_logger()

# configuration
EMBEDDING_BATCH_SIZE=100
SEARCH_UPLOAD_BATCH_SIZE=1000
CANDIDATE_PROCESS_BATCH=200

# step 1 fetching candidates that need embeddding

async def fetch_candidates_without_vectors(engine) -> list[dict]:
    # null means not yet processed
    async with engine.connect() as conn:
        result= await conn.execute(text("""
        SELECT id, full_name, resume_text, skills, 
                   location_country, location_city,
                   years_of_experience, education_level,
                   current_title
            FROM candidates 
            WHERE vector_id IS NULL 
              AND resume_text IS NOT NULL
              AND LENGTH(resume_text) > 50
            ORDER BY created_at
        """))

        rows=result.fetchall()

    candidates=[]
    for row in rows:
        candidates.append({
            "id": str(row[0]),
            "full_name": row[1],
            "resume_text": row[2],
            "skills": row[3] if row[3] else [],
            "location_country": row[4] or "",
            "location_city": row[5] or "",
            "years_of_experience": row[6] or 0,
            "education_level": row[7] or "",
            "current_title": row[8] or "",
        })
        return candidates


# Gebnerate embedding via openai with retry
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((Exception,)),
    before_sleep=lambda retry_state: logger.warning(
        "embedding_retry",
        attempt=retry_state.attempt_number,
        wait=retry_state.next_action.sleep,
    ),
)
def generate_embeddings_batch(texts: list[str],client: OpenAI) ->
list[list[float]]:
# embed a batch of text using OpenAI text-embedding-3-small
# args texts- List of section texts (max 100 per call)
# client: openai client instance
# returns list of embedding vectors 1536 floats

    response=client.embeddings.create(
    model=settings.OPENAI_EMBEDDING_MODEL,
    input=texts,
)
    return [item.embeddding for item in response.data]


def upload_to_search_index(documents: list[dict],search_client:SearchClient)-> int:
    """
    Upload search documents to Azure AI Search
    args: list of dicts matching index schema
    search client- azure search client instance
    returns number of sucessfully uplaoded documents
    if document id already exists -> updates it
    if it doesnt exist creates it
    
    """
    try:
        result= search_client.merge_or_upload_documents(documents)
        succeeded=sum(1 for r in result if r.succeeded)
        failed=sum(1 for r in result if r.succeeded)
        if failed > 0:
            logger.warning("Search uplaod partial failure",succeeded=succeeded,failed=failed)
            return succeeded
    except Exception as e:
        logger.error("search upload failed",error=str(e)[:200])
        return 0


# Step 4 update vector id in POstGresql
async def update_vector_ids(candidate_ids:  list[str],engine)-> None:
    # mark candidates as embedded
    if not candidate_ids:
        return
    async with engine.begin() as conn:
        for cid in candidate_ids:
            await conn.execute(
                text("UPDATE candidates SET vector_id= 'emnbedded' WHERE id=:cid"),
                {"cid":cid},
            )


# main orchestrator

async def main() -> None:
    logger.info("embedding pipeline started")

    # initialise clients
    openai_client=OpenAI(api_key=settings.OPENAI_API_KEY)
    search_client=SearchClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        index_name=settings.AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(settings.AZURE_SEARCH_API_KEY)

    )
    engine=create_async_engine(settings.DATABASE_URL,echo=False)

    # Fetch candidates
    candidates= await fetch_candidates_without_vectors(engine)
    logger.info("Candidates to process", count=len(candidates))

    if not candidates:
        print("\n all candidates already have embeddings.Nothing to do")
        await engine.dispose()
        return

    # process candidates
    total_sections=0
    total_uploaded=0
    search_docs_buffer: list[dict]=[]
    processed_candidate_ids: list[str]=[]

    for candidate in tqdm(candidates,desc="Processing Candidates"):
        # chunking the resumes into sections
        sections=chunk_resume(candidate["resume_text"])

        if not sections:
            logger.debug("no sections",candidate_id=candidate["id"])
            continue

        # prepare section text for embeddingd
        section_texts=[s.text for s in sections]

        # generate embeddings for all sections of this candidate
        # we batch at candidate level
        # fits in one api call
        try:
            embeddings=generate_embeddings_batch(section_texts,openai_client)
        except Exception as e:
            logger.error("Embedding failed",candidate_id=candidate["id"])
            continue

        # buulding dearch documents
        skills_str = ", ".join(candidate["skills"]) if candidate["skills"] else ""


        for section, embedding in zip(sections, embeddings):
            # Document ID format: {candidate_uuid}_{section_type}
            # This ensures uniqueness and lets us find all sections for a candidate
            doc_id = f"{candidate['id']}_{section.section_type}"
            # Azure AI Search IDs must be URL-safe, replace special chars
            doc_id = doc_id.replace(" ", "_").replace("/", "_")
            
            search_doc = {
                "id": doc_id,
                "candidate_postgres_id": candidate["id"],
                "section_type": section.section_type,
                "section_text": section.text[:32000],  # Azure limit
                "skills_str": skills_str,
                "location_country": candidate["location_country"],
                "location_city": candidate["location_city"],
                "years_of_experience": candidate["years_of_experience"],
                "education_level": candidate["education_level"],
                "resume_embedding": embedding,
            }
            search_docs_buffer.append(search_doc)
            total_sections += 1
        
        processed_candidate_ids.append(candidate["id"])
        
        # 5. Upload when buffer reaches batch size
        if len(search_docs_buffer) >= SEARCH_UPLOAD_BATCH_SIZE:
            uploaded = upload_to_search_index(search_docs_buffer, search_client)
            total_uploaded += uploaded
            search_docs_buffer = []
            
            # Update vector_ids for processed candidates
            await update_vector_ids(processed_candidate_ids, engine)
            processed_candidate_ids = []
            
            logger.info("batch_uploaded", total_sections=total_sections, total_uploaded=total_uploaded)
    
    # ── Upload remaining documents ──────────────────────────────
    if search_docs_buffer:
        uploaded = upload_to_search_index(search_docs_buffer, search_client)
        total_uploaded += uploaded
    
    if processed_candidate_ids:
        await update_vector_ids(processed_candidate_ids, engine)
    
    await engine.dispose()
    
    # ── Summary ─────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  EMBEDDING PIPELINE — SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Candidates processed: {len(candidates)}")
    print(f"  Sections generated:   {total_sections}")
    print(f"  Documents uploaded:   {total_uploaded}")
    print(f"  Avg sections/resume:  {total_sections / max(len(candidates), 1):.1f}")
    print(f"{'=' * 60}")
if __name__ == "__main__":
    asyncio.run(main())
