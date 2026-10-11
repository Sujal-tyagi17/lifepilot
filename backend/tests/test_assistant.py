"""The assistant never shows its own prompt, and answers point to point."""
from app.knowledge.rag import rag_answer
from app.llm.provider import MockProvider, clean_reply

M = [
    {"title": "AICTE Pragati Scholarship for Girls", "amount": "₹50,000 / year", "deadline": "2099-10-15",
     "status": "eligible", "eligible": True, "url": "https://scholarships.gov.in/", "documents": ["Aadhaar"]},
    {"title": "Startup India Seed Fund Scheme", "amount": "Up to ₹20 lakh", "deadline": "2099-12-31",
     "status": "eligible", "eligible": True},
    {"title": "Post-Matric Scholarship for OBC Students", "status": "partial", "eligible": False, "unmet": ["Income above limit"]},
]


def test_mock_never_echoes_the_prompt():
    assert MockProvider().generate("## Instructions: secret prompt") == ""


def test_qualify_question_lists_only_eligible_schemes():
    out = rag_answer("Which schemes do I qualify for?", M, {"name": "Aisha"})
    assert "Instructions" not in out and "Context" not in out
    assert "AICTE Pragati" in out and "Startup India" in out and "Post-Matric" not in out
    assert out.index("AICTE Pragati") < out.index("Startup India")  # nearest deadline first
    assert "Next step" in out


def test_reasoning_tags_are_removed():
    assert clean_reply("<think>long reasoning</think>\nYou qualify for 2 schemes.") == "You qualify for 2 schemes."
