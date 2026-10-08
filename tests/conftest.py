import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ia_test_"))
os.environ["IA_DATA_DIR"] = str(_TMP / "data")
os.environ["IA_OUTPUT_DIR"] = str(_TMP / "outputs")
os.environ["IA_RESUME_DIR"] = str(_TMP / "resumes")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

SWE_RESUME = """ALEX STUDENT
alex@example.com
EDUCATION
University of Louisiana at Monroe  B.S. Computer Science, expected May 2028
TECHNICAL SKILLS
Languages: Python, Java, JavaScript, SQL, C++
Frameworks: Flask, React, Node.js; Tools: Git, Docker, Linux, REST APIs, unit testing
PROJECTS
EnergyIQ | Python, Flask, SQLite
- Built a Flask web app that predicts household energy use from user inputs and stores results in SQLite.
- Wrote REST API endpoints and unit tests for the prediction service.
Campus Events Board | React, Node.js
- Created a React and Node.js site where students post and RSVP to campus events.
"""

AI_RESUME = """ALEX STUDENT
TECHNICAL SKILLS
Python, PyTorch, scikit-learn, Pandas, NumPy, machine learning, NLP, LLMs, RAG, LangChain, Git, SQL
PROJECTS
Course Notes Assistant | Python, LangChain
- Built a RAG chatbot with LangChain and a vector database that answers questions about course notes using LLMs.
Spam Classifier | scikit-learn
- Trained a scikit-learn NLP model on 5,000 emails and compared logistic regression with naive Bayes.
"""


def _make_pdf(path: Path, text: str) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in text.splitlines():
        c.drawString(50, y, line.replace("•", "-"))
        y -= 14
    c.save()


@pytest.fixture(scope="session")
def resume_info():

    pytest.importorskip("reportlab")
    import config
    from matcher import load_resume_info
    config.ensure_dirs()
    _make_pdf(config.RESUMES["swe"], SWE_RESUME)
    _make_pdf(config.RESUMES["ai"], AI_RESUME)
    return load_resume_info(force=True)


@pytest.fixture
def profile():
    import config
    p = config.load_profile()
    p.update(first_name="Alex", last_name="Student", email="alex@example.com", phone="318-555-0100",
             linkedin="https://linkedin.com/in/alex", github="https://github.com/alex")
    p["university"] = "University of Louisiana at Monroe"
    p["demographics"].update(race="Asian", hispanic_latino="No", veteran="I am not a protected veteran",
                             disability="No, I do not have a disability")
    p["work_authorization"].update(status_note="F-1 student", current_authorization_preference="Yes",
                                  future_sponsorship_preference="No")
    return p


@pytest.fixture
def settings():
    import config
    s = config.load_settings()
    s["use_ollama"] = False
    s["request_delay_seconds"] = 0
    return s


@pytest.fixture
def conn(tmp_path):
    import tracker
    c = tracker.connect(tmp_path / "t.db")
    yield c
    c.close()
