# bot/qa_generator.py  –  חילוץ טקסט, GPT עם חיתוך, Cache, מאגר קבוע
import os, re, json, textwrap, hashlib
from pathlib import Path
from typing import List, Dict

# ─────────────  OpenAI (רשות)  ─────────────
try:
    import openai
    openai.api_key = os.environ["OPENAI_API_KEY"]
    _HAS_OPENAI = True
except KeyError:
    _HAS_OPENAI = False

# ─────────────  הגבלות טוקנים/תווים  ─────────────
MAX_CHARS      = 6_000                 # חותך טקסט ארוך
MAX_PAGES_PDF  = 20
MAX_SLIDES_PPT = 20

# ─────────────  מאגר קבוע (bank.json)  ─────────────
def load_bank() -> List[Dict]:
    fp = Path("data/bank.json")
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    # fallback למקרה שהתיקייה לא קיימת
    return []

def pick_from_bank(k=6):
    import random
    bank = load_bank()
    return random.sample(bank, k=min(k, len(bank))) if bank else _qa_via_placeholder("", k)

# ─────────────  חילוץ טקסט מקובץ  ─────────────
def extract_text(filepath: str) -> str:
    fp = Path(filepath)
    suf = fp.suffix.lower()

    if suf == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(fp)
        pages = reader.pages[:MAX_PAGES_PDF]
        return "\n".join(p.extract_text() or "" for p in pages)

    elif suf in {".docx", ".doc"}:
        import docx
        doc = docx.Document(fp)
        return "\n".join(p.text for p in doc.paragraphs)

    elif suf == ".pptx":
        from pptx import Presentation
        prs = Presentation(fp)
        slides = prs.slides[:MAX_SLIDES_PPT]
        return "\n".join(
            shape.text for s in slides for shape in s.shapes if hasattr(shape, "text")
        )

    return ""

# ─────────────  Cache לפי hash  ─────────────
CACHE_DIR = "/tmp/qa_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cached(key: str):
    fp = Path(CACHE_DIR) / f"{key}.json"
    return json.loads(fp.read_text()) if fp.exists() else None

def _save_cache(key: str, data):
    Path(CACHE_DIR, f"{key}.json").write_text(json.dumps(data, ensure_ascii=False))

# ─────────────  יצירת שאלות  ─────────────
def build_qa_from_text(txt: str, n: int = 6) -> List[Dict]:
    txt = txt[:MAX_CHARS]
    key = hashlib.md5(txt.encode()).hexdigest() + f"_{n}"
    if (cached := _cached(key)):
        return cached

    qa = _qa_via_gpt(txt, n) if _HAS_OPENAI else _qa_via_placeholder(txt, n)
    _save_cache(key, qa)
    return qa

# --- GPT ---
def _qa_via_gpt(txt: str, n: int):
    prompt = textwrap.dedent(f"""
    צור {n} שאלות בעברית על בסיס הטקסט הבא.
    - חצי מהשאלות מסוג multiple עם 5 אפשרויות (אותיות א.-ה.).
    - חצי True/False.
    החזר JSON בלבד, ללא הסברים.
    """) + txt

    rsp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        temperature=0.2,
    )
    raw = re.search(r"\{.*\}", rsp.choices[0].message.content, re.S).group()
    return json.loads(raw)

# --- Placeholder ---
def _qa_via_placeholder(txt: str, n: int):
    return [
        {
            "type": "true_false",
            "question": "זהו משפט דוגמה – OpenAI לא פעיל.",
            "options": ["נכון", "לא נכון"],
            "correct": "נכון",
        }
    ] * n
