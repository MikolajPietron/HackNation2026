// "Przetłumacz pismo z ZUS" (FUNKCJE F24): a photo or PDF of a letter from ZUS in plain Polish.
// AI reads it (Claude or Gemini, the model of the cases) and the whole result is marked as AI.
// Every point carries the letter's own words (a quote with its page) behind a toggle; a deadline
// is shown only as the letter writes it, never computed. Nothing is stored, and personal data is
// left out by the reader. With a session, the points the letter is about link to the timeline.
import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, ChevronRight, Lock, TriangleAlert } from 'lucide-react'
import { explainLetter } from '@/api'
import { Reading, UploadZone } from '@/components/cases/CasesDialog'
import { MockModal } from '@/components/mocks/MockModal'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { ICONS } from '@/lib/icons'
import { currentSessionId } from '@/lib/session'
import { cn } from '@/lib/utils'
import type { LetterAction, LetterBenefit, LetterExplanation, LetterOutcome, LetterQuote, Timeline } from '@/types'

const BENEFIT: Record<LetterBenefit, string> = {
  maternity: 'Zasiłek macierzyński',
  parental: 'Zasiłek za urlop rodzicielski',
  paternity: 'Zasiłek za urlop ojcowski',
  supplementary: 'Zasiłek za urlop uzupełniający',
  sickness: 'Zasiłek chorobowy',
  rehabilitation: 'Świadczenie rehabilitacyjne',
  job_loss: 'Zasiłek w wysokości zasiłku macierzyńskiego',
  rate_815: 'Zasiłek 81,5%',
  other: 'Świadczenie',
}

const OUTCOME_TONE: Record<LetterOutcome, string> = {
  granted: 'bg-zus-50 text-zus-700',
  refused: 'bg-sun-100 text-sun-700',
  partial: 'bg-sun-100 text-sun-700',
  changed: 'bg-navy-50 text-navy-700',
  none: 'bg-navy-50 text-navy-700',
}

type View =
  | { kind: 'pick'; error?: string }
  | { kind: 'reading'; started: number }
  | { kind: 'result'; letter: LetterExplanation }

export function LetterDialog({
  open,
  onClose,
  timeline,
  onSelect,
}: {
  open: boolean
  onClose: () => void
  timeline: Timeline | null
  /** Show an element of the timeline the letter is about. */
  onSelect: (id: string) => void
}) {
  const [view, setView] = useState<View>({ kind: 'pick' })
  const request = useRef<AbortController | null>(null)

  const close = () => {
    request.current?.abort()
    onClose()
  }
  const read = async (file: File) => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setView({ kind: 'reading', started: Date.now() })
    try {
      const letter = await explainLetter(file, timeline ? currentSessionId() : null, controller.signal)
      setView({ kind: 'result', letter })
    } catch (error) {
      if (controller.signal.aborted) return
      setView({ kind: 'pick', error: error instanceof Error ? error.message : 'Nie udało się odczytać pisma.' })
    }
  }

  return (
    <MockModal open={open} label="Pismo z ZUS" onClose={close} className="max-w-2xl">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={view.kind}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
        >
          {view.kind === 'pick' && (
            <div>
              <header className="pr-10">
                <h2 className="text-2xl leading-tight font-bold tracking-tight text-navy-900">
                  Przetłumacz pismo z ZUS
                </h2>
                <p className="mt-2 text-navy-500">
                  Decyzja, wezwanie albo zawiadomienie niejasne? Wgraj zdjęcie albo PDF, a powiemy prostym językiem,
                  co w nim jest i co trzeba zrobić.
                </p>
              </header>
              <UploadZone
                onFile={(file) => void read(file)}
                title="Wgraj pismo (PDF albo zdjęcie)"
                hint="Przeciągnij plik albo kliknij. Wszystkie strony naraz."
                icon={ICONS.koperta}
              />
              {view.error && (
                <p role="alert" className="mt-4 rounded-2xl bg-alert-50 px-4 py-3 text-sm font-bold text-alert-600">
                  {view.error}
                </p>
              )}
              <p className="mt-4 flex items-start gap-2 text-xs text-navy-400">
                <Lock className="mt-px size-3.5 shrink-0" />
                Pismo czyta AI (Claude albo Gemini). Nie zapisujemy go, a imion, nazwisk, numeru PESEL i adresów AI
                nie przepisuje. Daty i terminy podajemy tylko tak, jak są w piśmie.
              </p>
            </div>
          )}
          {view.kind === 'reading' && (
            <Reading
              label="Czytam pismo"
              pages={null}
              started={view.started}
              onCancel={() => {
                request.current?.abort()
                setView({ kind: 'pick' })
              }}
              what="AI czyta pismo i tłumaczy je prostym językiem"
              note="Zwykle trwa to kilkanaście sekund."
              icon={ICONS.koperta}
            />
          )}
          {view.kind === 'result' && (
            <LetterView
              letter={view.letter}
              timeline={timeline}
              onAnother={() => setView({ kind: 'pick' })}
              onSelect={(id) => {
                close()
                onSelect(id)
              }}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </MockModal>
  )
}

function LetterView({
  letter,
  timeline,
  onAnother,
  onSelect,
}: {
  letter: LetterExplanation
  timeline: Timeline | null
  onAnother: () => void
  onSelect: (id: string) => void
}) {
  const elements = (timeline ? letter.timeline_elements : [])
    .map((id) => {
      const s = timeline?.segments.find((x) => x.id === id)
      const m = timeline?.markers.find((x) => x.id === id)
      const d = timeline?.documents.find((x) => x.id === id)
      return { id, title: s?.title ?? m?.title ?? d?.title }
    })
    .filter((e): e is { id: string; title: string } => Boolean(e.title))

  return (
    <div className="text-navy-700">
      <header className="pr-10">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-zus-600 px-2 py-0.5 text-[10px] font-black tracking-wide text-white">AI</span>
          <span className="text-xs font-bold text-navy-400">{letter.ai_label}</span>
        </div>
        {/* The kind of letter as the title; the letter's own heading only when it says more. */}
        <h2 className="mt-3 text-2xl leading-tight font-bold tracking-tight text-navy-900">{letter.kind_label}</h2>
        {letter.heading && letter.heading.toLowerCase() !== letter.kind_label.toLowerCase() && (
          <p className="mt-1 font-bold text-navy-700">{letter.heading}</p>
        )}
        {letter.subject && <p className="mt-1 text-navy-500">{letter.subject}</p>}
        {letter.outcome_label && (
          <span className={cn('mt-3 inline-block rounded-full px-3 py-1 text-sm font-bold', OUTCOME_TONE[letter.outcome])}>
            {letter.outcome_label}
          </span>
        )}
      </header>

      {!letter.is_zus_letter && (
        <p className="mt-4 flex gap-2 rounded-2xl bg-sun-100 px-4 py-3 text-sm text-sun-700">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          To nie wygląda na pismo z ZUS. Sprawdź, czy wgrany został właściwy plik.
        </p>
      )}

      <p className="mt-5 text-lg leading-relaxed text-navy-900">{letter.summary}</p>

      {letter.actions.length > 0 && (
        <Block title="Co trzeba zrobić" tone="sun">
          <ul className="space-y-3">
            {letter.actions.map((action) => (
              <Action key={action.what} action={action} />
            ))}
          </ul>
        </Block>
      )}

      {letter.reason && (
        <Block title="Dlaczego">
          <p className="text-navy-900">{letter.reason.text}</p>
          <Quote quote={letter.reason.quote} />
        </Block>
      )}

      {letter.periods.length > 0 && (
        <Block title="Za jaki okres">
          <ul className="space-y-2">
            {letter.periods.map((period) => (
              <li key={`${period.benefit}-${period.start}`}>
                <p className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-bold text-navy-900">{BENEFIT[period.benefit]}</span>
                  <span className="text-sm text-navy-700 tabular-nums">
                    {period.start ? formatShortDate(period.start) : '…'} – {period.end ? formatShortDate(period.end) : '…'}
                  </span>
                </p>
                <Quote quote={period.quote} />
              </li>
            ))}
          </ul>
        </Block>
      )}

      {letter.prepare.length > 0 && (
        <Block title="Co przygotować">
          <ul className="space-y-2">
            {letter.prepare.map((item) => (
              <li key={item.text}>
                <p className="text-navy-900">{item.text}</p>
                <Quote quote={item.quote} />
              </li>
            ))}
          </ul>
        </Block>
      )}

      {letter.appeal && (
        <Block title="Jeśli się nie zgadzasz">
          <p className="text-sm text-navy-500">Możesz się odwołać. To Twoje prawo, nie obowiązek.</p>
          <ul className="mt-2">
            <Action action={letter.appeal} />
          </ul>
        </Block>
      )}

      {(letter.forms.length > 0 || letter.other_forms.length > 0) && (
        <Block title="Formularze w piśmie">
          <ul className="space-y-1.5 text-sm">
            {letter.forms.map((form) => (
              <li key={form.code}>
                <b className="text-navy-900">{form.code}</b> · {form.name}
                {form.abolished && (
                  <span className="ml-1 font-bold text-sun-700">
                    · od 24.10.2026 nie ma tego formularza{form.merged_into ? `: zastąpił go ${form.merged_into}` : ''}
                  </span>
                )}
              </li>
            ))}
            {letter.other_forms.map((code) => (
              <li key={code}>
                <b className="text-navy-900">{code}</b> · tego formularza Przewodnik ZUS nie opisuje
              </li>
            ))}
          </ul>
        </Block>
      )}

      {elements.length > 0 && (
        <Block title="Na Waszej osi">
          <ul className="flex flex-wrap gap-2">
            {elements.map((element) => (
              <li key={element.id}>
                <button
                  type="button"
                  onClick={() => onSelect(element.id)}
                  className="flex h-9 items-center gap-1 rounded-full border border-line pr-2.5 pl-3.5 text-sm font-bold text-navy-900 transition-colors hover:border-zus-300 hover:bg-zus-50"
                >
                  {element.title}
                  <ChevronRight className="size-4 text-navy-400" />
                </button>
              </li>
            ))}
          </ul>
        </Block>
      )}

      {(letter.warnings.length > 0 || letter.unreadable.length > 0) && (
        <div className="mt-5 space-y-1.5 text-sm text-sun-700">
          {[...letter.warnings, ...letter.unreadable.map((u) => `Nieczytelne: ${u}`)].map((w) => (
            <p key={w} className="flex gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              {w}
            </p>
          ))}
        </div>
      )}

      <footer className="mt-6 flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-navy-400">
          Odczytano {letter.pages_read} z {letter.pages} stron · {letter.model} · nic nie zapisujemy.
          {letter.personal_data_removed && ' Dane osobowe pominięte.'}
        </p>
        <button
          type="button"
          onClick={onAnother}
          className="h-10 shrink-0 rounded-full border border-line px-4 text-sm font-bold text-navy-700 transition-colors hover:bg-navy-50"
        >
          Inne pismo
        </button>
      </footer>
    </div>
  )
}

function Block({ title, tone, children }: { title: string; tone?: 'sun'; children: ReactNode }) {
  return (
    <section
      className={cn(
        'mt-5 rounded-3xl px-4 py-4',
        tone === 'sun' ? 'border border-sun-300 bg-sun-100/50' : 'border border-line',
      )}
    >
      <h3 className="mb-2 text-sm font-black tracking-wide text-navy-500 uppercase">{title}</h3>
      {children}
    </section>
  )
}

function Action({ action }: { action: LetterAction }) {
  return (
    <li>
      <p className="font-bold text-navy-900">{action.what}</p>
      {(action.deadline_text || action.deadline_date) && (
        <p className="mt-0.5 text-sm text-sun-700">
          {action.deadline_date && <b>do {formatShortDate(action.deadline_date)}</b>}
          {action.deadline_date && action.deadline_text && ' · '}
          {action.deadline_text}
        </p>
      )}
      <Quote quote={action.quote} />
    </li>
  )
}

/** The letter's own words, behind a toggle. */
function Quote({ quote }: { quote: LetterQuote }) {
  const [open, setOpen] = useState(false)
  if (!quote.text) return null
  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1 text-xs font-bold text-zus-700"
      >
        Jak to brzmi w piśmie
        <ChevronDown className={cn('size-3.5 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.blockquote
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <p className="mt-1.5 border-l-2 border-navy-200 pl-3 text-sm text-navy-700">
              „{quote.text}” <span className="text-navy-400">s. {quote.page}</span>
            </p>
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  )
}

