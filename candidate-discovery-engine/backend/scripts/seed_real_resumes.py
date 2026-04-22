"""
Seed Script 1 — Load REAL Resumes into PostgreSQL.

WHAT THIS DOES:
    1. Scans F:\JDEesiee\Resumes\ for all PDF and DOCX files
    2. Extracts text from each using PyMuPDF / python-docx
    3. Parses basic info (name, email, phone, skills) via regex
    4. Inserts each as a Candidate row in PostgreSQL

USAGE:
    cd f:\JDEesiee\candidate-discovery-engine\backend
    f:\JDEesiee\venv\Scripts\python.exe -m scripts.seed_real_resumes
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tqdm import tqdm

# ── Setup Python path so 'from app.xxx' imports work ────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.core.logging import setup_logging
from app.services.extractor import extract_text_from_file

import structlog

setup_logging(debug=True)
logger = structlog.get_logger()

# ── Where your real resumes live ─────────────────────────────────────
RESUME_DIR = Path(r"F:\JDEesiee\Resumes")


# =====================================================================
# SKILL KEYWORDS — we check if these appear in the resume text
# =====================================================================
SKILL_KEYWORDS = [
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "Go", "Rust",
    "Ruby", "PHP", "Scala", "R", "MATLAB", "Shell", "Bash", "PowerShell",
    "Perl", "Haskell", "Elixir", "Dart", "Groovy", "Lua",

    # Frontend
    "React", "Angular", "Vue", "Next.js", "Nuxt.js", "Svelte", "Redux",
    "Tailwind CSS", "Bootstrap", "Webpack", "Vite", "HTML", "CSS",
    "SASS", "SCSS", "jQuery",

    # Backend / Frameworks
    "Node.js", "FastAPI", "Django", "Flask", "Spring", "Express.js",
    "NestJS", "Gin", "Echo", "Laravel", "Rails", "Symfony",
    "Celery", "Gunicorn", "Uvicorn",

    # Cloud & DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "Ansible", "Puppet", "Chef", "Helm", "Prometheus", "Grafana",
    "Datadog", "New Relic", "CloudFormation", "CDK", "Pulumi",
    "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD",
    "ECS", "EKS", "Lambda", "S3", "EC2", "CloudFront",

    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "CouchDB", "InfluxDB", "TimescaleDB",
    "BigQuery", "Snowflake", "Redshift", "Oracle", "MSSQL", "SQLite",

    # AI/ML
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-learn", "LangChain",
    "Hugging Face", "OpenAI", "RAG", "Vector DB", "Pinecone", "Weaviate",
    "ChromaDB", "FAISS", "MLflow", "Kubeflow", "Vertex AI", "SageMaker",
    "AutoML", "ONNX", "Transformers", "XGBoost", "LightGBM", "CatBoost",

    # Data Engineering
    "SQL", "NoSQL", "GraphQL", "REST", "gRPC", "Microservices",
    "Kafka", "RabbitMQ", "Spark", "Hadoop", "Databricks",
    "Data Engineering", "ETL", "Data Pipeline",
    "dbt", "Airflow", "Prefect", "Luigi", "Fivetran",
    "Power BI", "Tableau", "Excel", "Looker", "Metabase", "Superset",

    # Security
    "Cybersecurity", "OWASP", "Penetration Testing", "IAM", "OAuth",
    "JWT", "SSL/TLS", "SIEM", "SOC", "Zero Trust",

    # Mobile
    "Swift", "Kotlin", "Flutter", "React Native", "iOS", "Android",
    "Xamarin", "Ionic", "Expo",

    # DevOps & Tools
    "Agile", "Scrum", "JIRA", "Git", "CI/CD", "DevOps",
    "Linux", "Windows Server", "Networking",
    ".NET", "ASP.NET", "Entity Framework", "LINQ",
    "Selenium", "Cypress", "JUnit", "Pytest", "Postman",
    "Figma", "Photoshop", "UI/UX", "Salesforce", "SAP",
    "GitHub", "GitLab", "Bitbucket", "Vault",

    # Methodologies
    "TDD", "BDD", "DDD", "Event-Driven", "SOLID", "Design Patterns",
    "Kanban", "Lean", "Six Sigma", "ITIL",

    # Soft / Domain Skills
    "Project Management", "Business Analysis", "Technical Writing",
    "Communication", "Leadership", "Mentoring", "Team Management",
    "Financial Modeling", "Risk Analysis", "Supply Chain",
    "Healthcare IT", "EdTech", "FinTech",
]

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")


# =====================================================================
# PARSER — extracts structured fields from raw resume text
# =====================================================================
def parse_resume_text(text: str, file_path: str) -> dict:
    """
    Best-effort regex parser. Won't be perfect for every format.
    That's OK — the LLM reads the full resume_text during scoring.
    
    Args:
        text: extracted resume text
        file_path: FULL path to the file (used for unique external_id)
    """
    # Strip null bytes — PostgreSQL rejects 0x00 in UTF-8 text
    text = text.replace("\x00", "")

    # Email
    email_match = EMAIL_PATTERN.search(text)
    email = email_match.group(0) if email_match else None

    # Phone (usually near the top)
    phone_match = PHONE_PATTERN.search(text[:500])
    phone = phone_match.group(0).strip() if phone_match else None

    # Name extraction — improved strategy:
    # 1. Try the first line that looks like a name (2-4 words, no special chars)
    # 2. Fallback: extract from email (john.doe@gmail.com → John Doe)
    # 3. Last resort: use filename
    NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{2,50}$")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    full_name = None

    for line in lines[:8]:
        # Skip lines that look like headers, contact info, or URLs
        if (
            EMAIL_PATTERN.search(line)
            or line.startswith(("http", "www", "+", "("))
            or any(kw in line.lower() for kw in [
                "resume", "curriculum", "profile", "objective",
                "phone", "address", "email", "linkedin", "github",
                "summary", "experience", "education", "skill",
            ])
            or len(line) > 60
            or len(line.split()) > 5  # Names rarely have more than 5 words
        ):
            continue
        # Check if it looks like a name (alphabetic words)
        if NAME_PATTERN.match(line):
            full_name = line.title() if line.isupper() else line
            break

    # Fallback: parse name from email (john.doe@gmail → John Doe)
    if not full_name and email:
        local_part = email.split("@")[0]
        name_parts = re.split(r"[._-]+", local_part)
        name_parts = [p for p in name_parts if not p.isdigit() and len(p) > 1]
        if name_parts:
            full_name = " ".join(p.title() for p in name_parts)

    # Last fallback: use filename
    if not full_name:
        full_name = Path(file_path).stem.replace("_", " ").replace("-", " ").title()

    if not full_name or full_name.strip() == "":
        full_name = "Unknown Candidate"

    # Skills — check which keywords appear in text
    text_lower = text.lower()
    skills = [s for s in SKILL_KEYWORDS if s.lower() in text_lower]

    # Years of experience — take the MAX found, not just the first
    # e.g. "2 years in React, 5 years in Python" → 5
    exp_matches = re.findall(r"(\d{1,2})\+?\s*(?:years?|yrs?)", text_lower)
    years_exp = max(int(x) for x in exp_matches) if exp_matches else None

    # Current title
    title = None
    title_pattern = r"((?:senior|junior|lead|principal|staff)?\s*(?:software|data|ml|ai|cloud|devops|full.?stack|front.?end|back.?end|qa|test|project|product)\s*(?:engineer|developer|architect|analyst|scientist|manager))"
    match = re.search(title_pattern, text_lower)
    if match:
        title = match.group(1).strip().title()[:256]

    # Location — country
    location_country = None
    for country in ["India", "United States", "USA", "UK", "Canada", "Australia", "Germany"]:
        if country.lower() in text_lower:
            location_country = country.replace("USA", "United States")
            break

    # Location — city
    location_city = None
    for city in ["Bengaluru", "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune",
                 "Noida", "Gurgaon", "Gurugram", "Kolkata", "Ahmedabad", "Jaipur",
                 "New York", "San Francisco", "Seattle", "London", "Toronto", "Singapore"]:
        if city.lower() in text_lower:
            location_city = city
            break

    # Education level
    education_level = None
    if any(t in text_lower for t in ["ph.d", "phd", "doctorate"]):
        education_level = "PhD"
    elif any(t in text_lower for t in ["master", "m.s.", "m.tech", "mba"]):
        education_level = "Masters"
    elif any(t in text_lower for t in ["bachelor", "b.tech", "b.e.", "b.s.", "bca"]):
        education_level = "Bachelors"

    return {
        "id": uuid.uuid4(),
        # Hash FULL PATH, not just filename — avoids collisions for
        # resume.pdf in different folders
        "external_id": f"resume-{hashlib.md5(file_path.encode()).hexdigest()[:16]}",
        "full_name": full_name[:256],
        "email": email,
        "phone": phone[:32] if phone else None,
        "location_city": location_city,
        "location_country": location_country,
        "years_of_experience": years_exp,
        "current_title": title,
        "current_company": None,
        "education_level": education_level,
        "skills": skills if skills else ["General"],
        "resume_text": text,
        "resume_blob_url": None,
        "vector_id": None,
        "is_active": True,
    }


# =====================================================================
# DATABASE INSERT — batch insert in chunks for cloud performance
# =====================================================================
BATCH_SIZE = 50  # Insert 50 rows per round-trip


async def insert_candidates(candidates: list[dict]) -> int:
    """
    Batch insert candidates into Supabase/PostgreSQL.

    WHY BATCHES?
        Over the internet to Supabase, 1 insert per round-trip = 1971 round-trips
        = 15+ minutes. Batching 50 rows per INSERT = ~40 round-trips = ~30 seconds.

    WHY NOT ALL AT ONCE?
        If one row has bad data, we'd lose all 1971. With batches of 50,
        we lose at most 50 rows per bad batch.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    insert_sql = text("""
        INSERT INTO candidates (
            id, external_id, full_name, email, phone,
            location_city, location_country, years_of_experience,
            current_title, current_company, education_level,
            skills, resume_text, resume_blob_url, vector_id, is_active
        ) VALUES (
            :id, :external_id, :full_name, :email, :phone,
            :location_city, :location_country, :years_of_experience,
            :current_title, :current_company, :education_level,
            CAST(:skills AS jsonb), :resume_text, :resume_blob_url, :vector_id, :is_active
        )
        ON CONFLICT (external_id) DO NOTHING
    """)

    inserted = 0
    failed_batches = 0

    # Process in batches
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i + BATCH_SIZE]
        try:
            async with engine.begin() as conn:
                for candidate in batch:
                    params = {**candidate, "skills": json.dumps(candidate["skills"])}
                    await conn.execute(insert_sql, params)
                inserted += len(batch)
        except Exception as e:
            failed_batches += 1
            if failed_batches <= 3:
                logger.warning("batch_failed", batch_start=i, error=str(e)[:200])

        # Progress feedback every 200 rows
        if (i + BATCH_SIZE) % 200 == 0:
            logger.info("insert_progress", done=min(i + BATCH_SIZE, len(candidates)),
                        total=len(candidates))

    if failed_batches > 0:
        logger.info("insert_summary", inserted=inserted,
                    failed_batches=failed_batches)

    await engine.dispose()
    return inserted


# =====================================================================
# MAIN — Scan → Extract → Parse → Insert
# =====================================================================
async def main() -> None:
    logger.info("seed_started", resume_dir=str(RESUME_DIR))

    # Find all PDF and DOCX files
    resume_files = []
    for ext in ("*.pdf", "*.docx"):
        resume_files.extend(RESUME_DIR.rglob(ext))

    logger.info("files_found", count=len(resume_files))
    if not resume_files:
        logger.error("no_files_found")
        return

    # Extract text from each file
    candidates = []
    failed = 0

    for file_path in tqdm(resume_files, desc="Extracting resumes", unit="file"):
        try:
            text = extract_text_from_file(file_path)
            candidate = parse_resume_text(text, str(file_path))
            candidates.append(candidate)
        except Exception as e:
            failed += 1
            logger.debug("extraction_failed", file=file_path.name, error=str(e))

    logger.info("extraction_done", ok=len(candidates), failed=failed)

    # Insert into PostgreSQL
    inserted = 0
    if candidates:
        inserted = await insert_candidates(candidates)

    # Summary
    print("\n" + "=" * 60)
    print("  SEED REAL RESUMES — SUMMARY")
    print("=" * 60)
    print(f"  Files scanned:     {len(resume_files)}")
    print(f"  Text extracted:    {len(candidates)}")
    print(f"  Extraction failed: {failed}")
    print(f"  Inserted to DB:    {inserted}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())