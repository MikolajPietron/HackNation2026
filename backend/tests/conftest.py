"""Tests never talk to Supabase: whatever `backend/.env` says, sessions and parameter versions
stay in memory. An environment variable wins over the `.env` file, and it is set before the app
(and its cached settings) is imported."""

import os

os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
