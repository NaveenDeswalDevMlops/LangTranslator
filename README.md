# Multilingual File Review System (Streamlit Demo)

A Python + Streamlit demo app that:
- Uploads PDF/DOCX/TXT files
- Extracts text
- Translates content with Groq API
- Shows original + translated text side-by-side
- Accepts comments and stores translated versions
- Persists data in `session_data.json`

## Setup

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set Groq API key:

```bash
export GROQ_API_KEY="your_api_key_here"
```

Optional model override:

```bash
export GROQ_MODEL="llama-3.3-70b-versatile"
```

4. Run app:

```bash
streamlit run app.py
```

## Files

- `app.py` – Streamlit UI and flow orchestration
- `parser.py` – File extraction logic (PDF/DOCX/TXT)
- `translator.py` – Groq translation integration and chunking
- `storage.py` – Local JSON-backed storage (`session_data.json`)
