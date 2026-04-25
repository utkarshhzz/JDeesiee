# resume section chunker - splits resume into typed sections
"""
if one embedding per resume= semantic dilution
so one embedding per section = each sections meaning is preserved
The "Experience" section embedding will be very close to a JD asking
    for Python experience, because there's no noise from education/certs.
    section types:
    summary professional summary
    experince-work experince/employment history
    skills-technical skills/competencies
    education:Education/academic background
    cwrtifications- Certificaions/licences/coursees
    other:project and eveything else

"""


from __future__ import annotations

import re
from dataclasses import dataclass
import structlog
logger=structlog.get_logger()

# maximum chars -er section
MAX_SECTION_CHARS= 4000
MIN_SECTION_CHARS=50

@dataclass
class ResumeSection:
    """A single section of resume with type and label"""
    section_type:str
    text:str


# we use section header patterns
# these regex pattern detect common resume sectionheaders
# we look for these at the start of a line

SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "summary",
        re.compile(
            r"^(?:"
            r"(?:professional\s+)?(?:summary|profile|objective|about\s+me|overview|career\s+summary|career\s+objective|personal\s+summary|professional\s+profile|resume\s+summary|executive\s+summary|candidate\s+profile|self\s+summary)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "experience",
        re.compile(
            r"^(?:"
            r"(?:(?:work|professional|employment|career|job)\s+)?(?:experience|history|background)"
            r"|(?:professional\s+experience|work\s+experience|employment\s+history|work\s+history|career\s+history|relevant\s+experience|industry\s+experience|internship\s+experience|internships|internship)"
            r"|(?:positions?|roles?|employment|jobs?)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "skills",
        re.compile(
            r"^(?:"
            r"(?:(?:technical|core|key|professional|relevant|additional)\s+)?(?:skills|competencies|technologies|tech\s*stack|expertise)"
            r"|(?:technical\s+skills|core\s+skills|key\s+skills|professional\s+skills|soft\s+skills|hard\s+skills|computer\s+skills|it\s+skills)"
            r"|(?:areas?\s+of\s+expertise|areas?\s+of\s+specialization|specialties|specializations|capabilities|proficiencies|strengths)"
            r"|(?:tools|languages|frameworks|libraries|platforms|technologies\s+used)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "education",
        re.compile(
            r"^(?:"
            r"(?:education|academic|qualifications|degrees?)"
            r"|(?:educational\s+background|academic\s+background|academic\s+qualification|academic\s+qualifications)"
            r"|(?:studies|study|schooling|formal\s+education|higher\s+education|undergraduate\s+education|postgraduate\s+education)"
            r"|(?:coursework|courses|major|minor|syllabus)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "certifications",
        re.compile(
            r"^(?:"
            r"(?:certifications?|licenses?|courses?|training|professional\s+development)"
            r"|(?:certificates?|credential(s)?|accreditation|accreditations|licensure)"
            r"|(?:online\s+courses?|workshops?|seminars?|bootcamps?|workshop\s+training)"
            r"|(?:training\s+and\s+certifications?|certification\s+and\s+training)"
            r"|(?:awards?\s+and\s+certifications?)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "projects",
        re.compile(
            r"^(?:"
            r"(?:projects?|portfolio|personal\s+projects?|side\s+projects?|open\s+source)"
            r"|(?:selected\s+projects?|academic\s+projects?|major\s+projects?|mini\s+projects?|capstone\s+projects?)"
            r"|(?:project\s+work|project\s+experience|research\s+projects?|application\s+projects?)"
            r"|(?:built\s+projects?|development\s+projects?|software\s+projects?|engineering\s+projects?)"
            r"|(?:open-source\s+projects?|contributions)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "publications",
        re.compile(
            r"^(?:"
            r"(?:publications?|papers?|research|patents?)"
            r"|(?:published\s+work|publication\s+list|selected\s+publications|journal\s+articles?|conference\s+papers?|technical\s+papers?)"
            r"|(?:articles?|book\s+chapters?|theses?|dissertations?|reports?)"
            r"|(?:presentations?|talks?|poster\s+presentations?)"
            r"|(?:preprints?|manuscripts?)"
            r")\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
]

def find_section_boundaries(text:str) -> list[tuple[str,int]]:
        """
        Scan text for section headers and return their positions
        returns list of section type and start_posiiton
        """
        boundaries: list[tuple[str,int]]=[]
        for section_type,pattern in SECTION_PATTERNS:
            for match in pattern.finditer(text):
                boundaries.append((section_type,match.start()))

        # Sort by position in the text (top of resume first)
        boundaries.sort(key=lambda x: x[1])
        return boundaries


def _split_long_section(section: ResumeSection) -> list[ResumeSection]:
    """
    If a section exceeds MAX_SECTION_CHARS, split it into sub-sections.
    WHY?
        The "Experience" section for a 15-year veteran could be 8000+ chars.
        text-embedding-3-small handles 8191 tokens, but embedding quality
        degrades for very long inputs. Splitting keeps each chunk focused.
    HOW?
        We split on double-newlines (paragraph boundaries) first.
        If paragraphs are still too long, we split on single newlines.
        This preserves sentence integrity.
    """
    if len(section.text) <= MAX_SECTION_CHARS:
        return [section]
    chunks: list[ResumeSection] = []
    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r"\n\s*\n", section.text)
    current_chunk = ""
    chunk_index = 0
    for para in paragraphs:
        # If adding this paragraph would exceed the limit, save current and start new
        if current_chunk and len(current_chunk) + len(para) + 2 > MAX_SECTION_CHARS:
            chunks.append(ResumeSection(
                section_type=f"{section.section_type}_{chunk_index}",
                text=current_chunk.strip(),
            ))
            current_chunk = para
            chunk_index += 1
        else:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
    # Don't forget the last chunk
    if current_chunk.strip():
        suffix = f"_{chunk_index}" if chunk_index > 0 else ""
        chunks.append(ResumeSection(
            section_type=f"{section.section_type}{suffix}",
            text=current_chunk.strip(),
        ))
    return chunks


def chunk_resume(text:str) -> list[ResumeSection]:
    """
    split resume text into typed sections for per-section embedding
    1-> scan for section headers using regex patterns
    2-> extract text between conseccutive headers
    3->if no headers found ,treat entire text as summary(fallback)
    4-> merge tiny sections into previous section
    5->split oversized sections at paragraph boundaries

    returns list of resumesection objects each with type and text
    typically 3-6 sections per resume
    """

    if not text or not text.strip():
        return []

    boundaries=find_section_boundaries(text)
    # if no section headers detected then trat entire as summary
    if not boundaries:
        logger.debug("no section headers found",text_length=len(text))
        return [ResumeSection(section_type="summary",text=text.strip())]

    # If there's text BEFORE the first section header, it's usually
    # the candidate's name + contact info. Include it as "header".
    sections: list[ResumeSection]=[]
    first_boundary_pos=boundaries[0][1]
    if first_boundary_pos > MIN_SECTION_CHARS:
        sections.append(ResumeSection(
            section_type="header",
            text=text[:first_boundary_pos].strip(),
        ))
    for i, (section_type, start_pos) in enumerate(boundaries):
        # End position = start of next section, or end of text
        if i + 1 < len(boundaries):
            end_pos = boundaries[i + 1][1]
        else:
            end_pos = len(text)
        section_text = text[start_pos:end_pos].strip()
        if len(section_text) < MIN_SECTION_CHARS:
            # Too short — merge into previous section if exists
            if sections:
                sections[-1] = ResumeSection(
                    section_type=sections[-1].section_type,
                    text=f"{sections[-1].text}\n{section_text}",
                )
            continue
        sections.append(ResumeSection(
            section_type=section_type,
            text=section_text,
        ))
    # ── Split oversized sections ─────────────────────────────────────
    final_sections: list[ResumeSection] = []
    for section in sections:
        final_sections.extend(_split_long_section(section))
    logger.debug(
        "resume_chunked",
        total_sections=len(final_sections),
        types=[s.section_type for s in final_sections],
    )
    return final_sections
