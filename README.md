# Decision Making AI

Streamlit decision-support prototype using OpenRouter `respan/span-01-lite:free`.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` in the same folder as `app.py`:

```dotenv
OPENROUTER_API_KEY=your_actual_openrouter_api_key
```

Get a key at https://openrouter.ai/keys. Never commit `.env` or share your key.

Run:

```powershell
streamlit run app.py
```

## API

This project uses `https://openrouter.ai/api/alpha/decisions` with a Bearer Authorization header. If that endpoint still reports “Missing Authentication header,” first test whether the key works on OpenRouter's standard API endpoint and check the current official documentation for the Decisions API; do not expose the key in logs or chat.

Official model page: https://openrouter.ai/respan/span-01-lite:free

## Database migration

On startup, the app checks the existing `decisions` table and adds missing columns without deleting old rows. Back up `decision_history.db` before making manual database changes.

## Limitations

Model scores are estimates, not verified facts. Validate recommendations independently. Free-model availability, rate limits, and API schemas may change.
