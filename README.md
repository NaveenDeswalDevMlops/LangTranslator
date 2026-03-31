# Multilingual File Review System (Streamlit Demo)

A Python + Streamlit demo app that:
- Uploads PDF/DOCX/TXT files and extracts text
- Translates content with Groq API
- Shows uploaded PDF on the left and converted (translated) PDF on the right
- Displays differences between source and converted content
- Supports reviewer feedback and multilingual comments
- Supports assignment to teams and criticality tracking
- Persists review state in `session_data.json`

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY="your_api_key_here"
# optional:
export GROQ_MODEL="llama-3.3-70b-versatile"
streamlit run app.py
```

## Files
- `app.py` – Streamlit UI and orchestration
- `parser.py` – file extraction (PDF/DOCX/TXT)
- `translator.py` – Groq translation integration and chunking
- `storage.py` – local JSON-backed persistence
