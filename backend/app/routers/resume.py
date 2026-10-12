"""Resume endpoints: one parser for every page that accepts a resume."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.resume.parser import ResumeParseError, extract_text

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    """Extract plain text from a PDF, DOCX or TXT resume."""
    content = await file.read()
    try:
        text = extract_text(file.filename or "", content)
    except ResumeParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"text": text, "characters": len(text)}
