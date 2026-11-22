// A leave request filled from the plan (FUNKCJE F22; the brief: "symulacji wypełnienia wniosków
// o urlopy … i ewentualnie przesłanie ich do pracodawcy/ZUS (wnioski o urlopy wymagają
// zaprojektowania)"). The letter takes only what the engine says: the period and its dates, who
// files it and when (Document.rule), and the legal basis only where the engine cites an article.
// The parent types their own details; nothing typed here is saved or sent anywhere. Sending is a
// simulation, confirmed explicitly first (FUNKCJE: no undo for sending, a clear confirmation).
import { useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check, Printer, Send } from 'lucide-react'
import { SimBadge } from '@/components/mocks/MockModal'
import { PrimaryButton } from '@/components/onboarding/ChoiceCard'
import { Emphasis } from '@/components/ui/emphasis'
import { formatLongDate, todayIso } from '@/lib/dates'
import { EASE_OUT, SPRING_PRESS } from '@/lib/ease'
import { length } from '@/lib/plan'
import { sourceLabel } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Document, Segment, Timeline } from '@/types'

/** "urlopu macierzyńskiego": the leave in the genitive, for "proszę o udzielenie …". */
const GENITIVE: Record<string, string> = {
  'maternity-prenatal': 'urlopu macierzyńskiego',
  maternity: 'urlopu macierzyńskiego',
  parental: 'urlopu rodzicielskiego',
  'parental-father': 'urlopu rodzicielskiego',
  paternity: 'urlopu ojcowskiego',
  supplementary: 'uzupełniającego urlopu macierzyńskiego',
}

interface Period {
  name: string
  start: string
  end: string
  days: number
}

/** The leave the request is for: the period, joined with the next one of the same leave
 *  (before and after the birth are one maternity leave). */
function periodOf(timeline: Timeline, segment: Segment): Period {
  const name = GENITIVE[segment.id] ?? segment.title.toLowerCase()
  const same = timeline.segments
    .filter((s) => s.lane === segment.lane && (GENITIVE[s.id] ?? '') === name)
    .sort((a, b) => a.start.localeCompare(b.start))
  const from = same.findIndex((s) => s.id === segment.id)
  const chain = [same[from]]
  for (const next of same.slice(from + 1)) {
    const last = chain[chain.length - 1]
    if (new Date(next.start).getTime() - new Date(last.end).getTime() === 86_400_000) chain.push(next)
  }
  return {
    name,
    start: chain[0].start,
    end: chain[chain.length - 1].end,
    days: chain.reduce((sum, s) => sum + s.days, 0),
  }
}

const sentence = (p: Period) =>
  `${p.name} w wymiarze ${length(p.days).replace('tyg.', 'tygodni')}, od ${formatLongDate(p.start)} r. do ${formatLongDate(p.end)} r.`

type Step = 'fill' | 'send' | 'sent'

export function ApplicationForm({ timeline, document }: { timeline: Timeline; document: Document }) {
  const segment = timeline.segments.find((s) => s.id === document.segment_id)
  const period = segment ? periodOf(timeline, segment) : null
  // The guide: a mother may ask for maternity and parental leave in one request.
  const parental =
    segment && document.id === 'maternity-request'
      ? timeline.segments.find((s) => s.id === 'parental')
      : undefined
  const parentalPeriod = parental ? periodOf(timeline, parental) : null
  // Said only where the engine cites it (the Labour Code for parental and paternity leave).
  const obliged = document.sources.find((s) => s.quote.includes('obowiązany uwzględnić'))
  const articles = [...new Set(document.sources.filter((s) => s.doc === 'kp' && s.article).map((s) => s.article!))]

  const [step, setStep] = useState<Step>('fill')
  const [withParental, setWithParental] = useState(false)
  const [fields, setFields] = useState({ name: '', employer: '', place: '', email: '' })
  const set = (key: keyof typeof fields) => (value: string) => setFields({ ...fields, [key]: value })
  const [confirming, setConfirming] = useState(false)

  if (!period) return null
  const body =
    `Proszę o udzielenie mi ${sentence(period)}` +
    (withParental && parentalPeriod ? ` oraz, bezpośrednio po nim, ${sentence(parentalPeriod)}` : '')
  const basis = articles.length ? `Podstawa prawna: Kodeks pracy, ${articles.join(', ')}.` : ''

  const print = () => {
    const win = window.open('', '_blank', 'noopener=no')
    if (!win) return
    const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    win.document.write(`<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>${esc(document.title)}</title>
<style>body{font-family:Georgia,serif;max-width:640px;margin:48px auto;line-height:1.6;color:#111}
.r{text-align:right}h1{font-size:20px;text-align:center;margin:40px 0 24px}.s{margin-top:64px;text-align:right}</style></head><body>
<p class="r">${esc(fields.place || '……………')}, ${esc(formatLongDate(todayIso()))} r.</p>
<p>${esc(fields.name || '……………………………')}</p>
<p class="r">${esc(fields.employer || '……………………………')}</p>
<h1>${esc(document.title)}</h1><p>${esc(body)}</p>${basis ? `<p>${esc(basis)}</p>` : ''}
<p class="s">……………………………<br>podpis</p></body></html>`)
    win.document.close()
    win.focus()
    win.print()
  }

  return (
    <div className="text-navy-700">
      <header className="pr-10">
        <SimBadge>symulacja · nic nie jest wysyłane</SimBadge>
        <h2 className="mt-3 text-2xl leading-tight font-bold tracking-tight text-navy-900">{document.title}</h2>
        <p className="mt-2 text-sm leading-relaxed">
          <Emphasis text={document.rule} className="text-navy-900" />
        </p>
      </header>

      <AnimatePresence mode="wait" initial={false}>
        {step === 'fill' && (
          <motion.div key="fill" {...fade}>
            {/* The letter, as it will look. */}
            <div className="mt-5 rounded-2xl border border-line bg-white p-5 shadow-[0_18px_40px_-28px_rgb(26_36_56/0.45)] sm:p-7">
              <div className="flex justify-end">
                <Field value={fields.place} onChange={set('place')} placeholder="miejscowość" className="w-36 text-right" />
                <span className="ml-1 text-sm">, {formatLongDate(todayIso())} r.</span>
              </div>
              <Field value={fields.name} onChange={set('name')} placeholder="imię i nazwisko" className="mt-4 w-56" />
              <div className="mt-4 flex justify-end">
                <Field value={fields.employer} onChange={set('employer')} placeholder="pracodawca" className="w-56 text-right" />
              </div>
              <p className="mt-8 text-center text-lg font-bold text-navy-900">{document.title}</p>
              <p className="mt-4 leading-relaxed text-navy-900">{body}</p>
              {basis && <p className="mt-2 text-sm text-navy-500">{basis}</p>}
              <p className="mt-12 text-right text-sm text-navy-400">……………………………<br />podpis</p>
            </div>

            {parentalPeriod && (
              <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-line px-4 py-3">
                <input
                  type="checkbox"
                  checked={withParental}
                  onChange={(e) => setWithParental(e.target.checked)}
                  className="mt-1 size-4 accent-[var(--color-zus-600)]"
                />
                <span className="text-sm">
                  <b className="text-navy-900">Jeden wniosek o oba urlopy.</b> Dołącz urlop rodzicielski, który
                  zaczyna się zaraz po macierzyńskim ({formatLongDate(parentalPeriod.start)}).
                </span>
              </label>
            )}
            <p className="mt-3 text-xs text-navy-400">
              Dane wpisane w polach zostają tylko na tej stronie: nie zapisujemy ich i nigdzie nie wysyłamy.
            </p>

            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Secondary onClick={print}>
                <Printer className="size-4" /> Drukuj albo zapisz PDF
              </Secondary>
              <PrimaryButton onClick={() => setStep('send')} className="h-12 px-6 text-base">
                <Send className="size-4" /> Wyślij do pracodawcy
              </PrimaryButton>
            </div>
          </motion.div>
        )}

        {step === 'send' && (
          <motion.div key="send" {...fade} className="mt-5">
            <p className="font-bold text-navy-900">Wyślij e-mailem do pracodawcy</p>
            <label className="mt-3 block text-sm font-bold text-navy-500" htmlFor="hr-email">
              Adres działu kadr
            </label>
            <input
              id="hr-email"
              type="email"
              value={fields.email}
              onChange={(e) => set('email')(e.target.value)}
              placeholder="kadry@firma.pl"
              className="mt-1 h-11 w-full rounded-2xl border border-line px-4 text-navy-900 outline-none focus:border-zus-400 focus:ring-4 focus:ring-zus-600/10"
            />
            <div className="mt-3 rounded-2xl bg-navy-50/60 px-4 py-3 text-sm">
              <p>
                <b className="text-navy-900">Temat:</b> {document.title}
              </p>
              <p className="mt-1 line-clamp-3">{body}</p>
            </div>
            <AnimatePresence initial={false}>
              {confirming && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, transition: { duration: 0.12 } }}
                  transition={{ duration: 0.2, ease: EASE_OUT }}
                  className="mt-4 rounded-2xl border border-sun-300 bg-sun-100 px-4 py-3 text-sm text-sun-700"
                  role="alertdialog"
                  aria-label="Potwierdź wysłanie"
                >
                  <p className="font-bold text-navy-900">Wysłać wniosek do {fields.email || 'pracodawcy'}?</p>
                  <p className="mt-0.5">To symulacja: nic nie wyjdzie z aplikacji.</p>
                  <div className="mt-3 flex gap-2">
                    <PrimaryButton onClick={() => setStep('sent')} className="h-10 px-4 text-sm">
                      Tak, wyślij
                    </PrimaryButton>
                    <Secondary onClick={() => setConfirming(false)}>Anuluj</Secondary>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            {!confirming && (
              <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Secondary onClick={() => setStep('fill')}>Wróć do wniosku</Secondary>
                <PrimaryButton onClick={() => setConfirming(true)} disabled={!fields.email.includes('@')} className="h-12 px-6 text-base">
                  <Send className="size-4" /> Wyślij
                </PrimaryButton>
              </div>
            )}
          </motion.div>
        )}

        {step === 'sent' && (
          <motion.div key="sent" {...fade} className="mt-8 flex flex-col items-center pb-2 text-center">
            <motion.span
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 380, damping: 22 }}
              className="grid size-16 place-items-center rounded-full bg-zus-600 text-white"
            >
              <Check className="size-8" strokeWidth={3} />
            </motion.span>
            <p className="mt-4 text-xl font-bold text-navy-900">Wniosek wysłany</p>
            <p className="mt-1 text-sm text-navy-500">
              Do {fields.email} · {formatLongDate(todayIso())} · symulacja, nic nie zostało wysłane
            </p>
            <p className="mt-4 max-w-sm text-sm text-pretty">Zachowaj kopię wniosku.</p>
            {obliged && (
              <p className="mt-2 max-w-sm text-sm text-pretty text-navy-500">
                „{obliged.quote}” <span className="font-bold text-zus-700">{sourceLabel(obliged)}</span>
              </p>
            )}
            <div className="mt-5">
              <Secondary onClick={print}>
                <Printer className="size-4" /> Zachowaj kopię (PDF)
              </Secondary>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const fade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6, transition: { duration: 0.12 } },
  transition: { duration: 0.22, ease: EASE_OUT },
}

/** A blank on the letter: an underlined field to type into. */
function Field({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  className?: string
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={placeholder}
      className={cn(
        'h-8 border-0 border-b border-dashed border-navy-200 bg-transparent px-1 text-sm text-navy-900 outline-none placeholder:text-navy-300 focus:border-zus-400',
        className,
      )}
    />
  )
}

function Secondary({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
      className="flex h-12 items-center justify-center gap-2 rounded-full border border-line px-5 font-bold text-navy-700 transition-[border-color,background-color] duration-150 hover:border-navy-200 hover:bg-navy-50"
    >
      {children}
    </motion.button>
  )
}
