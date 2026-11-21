import { useEffect, useState } from 'react'
import { API_URL } from './api'

type ApiStatus = 'checking' | 'ok' | 'error'

const STATUS_LABEL: Record<ApiStatus, string> = {
  checking: 'sprawdzam…',
  ok: 'działa',
  error: 'brak połączenia (uruchom backend)',
}

// Ekran-zaślepka: potwierdza tylko, że frontend widzi backend.
function App() {
  const [api, setApi] = useState<ApiStatus>('checking')

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((res) => setApi(res.ok ? 'ok' : 'error'))
      .catch(() => setApi('error'))
  }, [])

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-4 p-6">
      <h1 className="text-3xl font-semibold">Zasiłkowy Przewodnik Przyszłego Rodzica</h1>
      <p className="text-slate-600">Szkielet aplikacji. Tu powstanie oś czasu rodzica.</p>
      <p className="text-sm">API: {STATUS_LABEL[api]}</p>
    </main>
  )
}

export default App
