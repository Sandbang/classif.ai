# Web app for grading proofs

This small Flask app provides an upload form to send an image to the existing grading pipeline
(`classif.ai/find_text_lines.py` and `classif.ai/grade_proof.py`) and displays the annotated image
and the AI's JSON grading result.

Quick start (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = 'your_key_here' # or put it in a .env file in repo root
cd webapp
python app.py
# Open http://127.0.0.1:5000 in your browser
```

Notes:
- The grading uses the Anthropic client inside `grade_proof.py`. Ensure the API key is available.
- The annotated image will be saved into `webapp/static/annotated/annotated_<name>.jpg`.
