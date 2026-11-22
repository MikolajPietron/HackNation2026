"""F24 "Przetłumacz pismo z ZUS": a photo or PDF of a letter from ZUS in plain Polish. The model
(Claude or Gemini) only reads the letter and copies its dates; everything after that is
deterministic (`explain.py`): personal data removed, dates checked against the quoted text, the
forms named and the timeline elements the letter is about. Nothing is stored or logged."""
