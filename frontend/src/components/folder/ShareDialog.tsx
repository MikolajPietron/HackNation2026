// "Udostępnij plan": a read-only link for the partner (FUNKCJE F17, the light version). The
// backend keeps a copy of the plan under a new id: the partner sees the timeline, the money and
// the deadlines, cannot change anything, and gets no personal data (it never leaves this browser).
import { useEffect, useState } from 'react'
import { Check, Copy, LoaderCircle, Share2 } from 'lucide-react'
import { shareSession } from '@/api'
import { copyText } from '@/lib/clipboard'
import { currentSessionId } from '@/lib/session'

export function ShareDialog() {
  const [link, setLink] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let alive = true
    shareSession(currentSessionId())
      .then(({ token }) => alive && setLink(`${window.location.origin}/plan/${token}`))
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : 'Nie udało się utworzyć linku.'))
    return () => {
      alive = false
    }
  }, [])

  const native = typeof navigator.share === 'function'

  return (
    <div className="space-y-4 text-navy-700">
      <h2 className="pr-10 text-2xl font-bold tracking-tight text-navy-900">Udostępnij plan</h2>
      <p>
        Wyślij link partnerowi albo partnerce: zobaczy Wasz plan — urlopy, pieniądze i terminy — bez logowania. Tylko
        do odczytu: niczego nie zmieni. Dane osobowe z wniosków zostają w Twojej przeglądarce.
      </p>
      {error && <p className="rounded-2xl bg-alert-50 px-4 py-3 text-sm text-alert-600">{error}</p>}
      {!error && (
        <div className="flex flex-col gap-2 rounded-2xl border border-line p-1.5 sm:flex-row sm:items-center">
          {link ? (
            <span className="min-w-0 flex-1 px-2.5 py-1.5 text-sm break-all text-navy-900 select-all">{link}</span>
          ) : (
            <span className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-1.5 text-sm text-navy-400">
              <LoaderCircle className="size-4 animate-spin" /> Tworzę link…
            </span>
          )}
          <button
            type="button"
            disabled={!link}
            onClick={async () => link && setCopied(await copyText(link))}
            className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-full bg-zus-600 px-4 text-sm font-bold text-white transition-colors hover:bg-zus-700 disabled:opacity-50"
          >
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            {copied ? 'Skopiowano' : 'Kopiuj link'}
          </button>
        </div>
      )}
      {link && native && (
        <button
          type="button"
          onClick={() => void navigator.share({ title: 'Nasz plan rodzicielski', url: link }).catch(() => undefined)}
          className="flex h-11 items-center gap-2 rounded-full border border-line px-4 font-bold text-navy-700 hover:bg-navy-50"
        >
          <Share2 className="size-4" /> Wyślij
        </button>
      )}
      <p className="text-xs text-navy-400">
        Link pokazuje plan z chwili udostępnienia. Gdy coś zmienisz, udostępnij go ponownie.
      </p>
    </div>
  )
}
