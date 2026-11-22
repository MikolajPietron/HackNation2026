// "Wnioski i dokumenty": everything to file, filled in from the plan, in one place on the plan
// screen. Tick what is filed or gathered (kept in this browser), download a request as a real
// letter (PDF made here, with the personal data typed once), the whole folder in one PDF, or the
// plan on one A4 page. Dates are the engine's: a deadline only where the law gives one.
import { useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check, ChevronDown, Download, FolderDown, LoaderCircle, PenLine, Printer, UserRound } from 'lucide-react'
import { CopyValue } from '@/components/ui/copy-value'
import { Illustration } from '@/components/ui/illustration'
import { documentsToFile, useDone } from '@/lib/checklist'
import { formatShortDate } from '@/lib/dates'
import { EASE_OUT } from '@/lib/ease'
import { documentIcon, ICONS } from '@/lib/icons'
import { profileProgress, useProfile } from '@/lib/personal'
import { daysLeftLabel, COUNTDOWN_DAYS } from '@/lib/plan'
import { cn } from '@/lib/utils'
import type { Document, Role, Scenario, Timeline } from '@/types'

const dayCount = (from: string, to: string) =>
  Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)
const dotted = (iso: string) => iso.split('-').reverse().join('.')


export function DocumentsCard({
  timeline,
  scenario,
  onFill,
  onSelect,
  onPersonal,
}: {
  timeline: Timeline
  scenario: Scenario | null
  onFill: (documentId: string) => void
  onSelect: (id: string) => void
  onPersonal: () => void
}) {
  const [done, toggle] = useDone()
  const [profile] = useProfile()
  const [busy, setBusy] = useState<string | null>(null)
  const documents = documentsToFile(timeline)
  if (documents.length === 0) return null

  const isDone = (d: Document) => d.done || done.has(d.id)
  const ready = documents.filter(isDone).length
  const applicants = [...new Set(documents.map((d) => d.form?.applicant).filter(Boolean))] as Role[]
  const personal = profileProgress(profile, applicants.length ? applicants : ['mother'])

  const run = async (key: string, work: () => Promise<void>) => {
    setBusy(key)
    try {
      await work()
    } finally {
      setBusy(null)
    }
  }
  const pdf = () => import('@/lib/pdf/documents')

  return (
    <section aria-labelledby="documents" className="rounded-4xl border border-line px-4 pt-5 pb-3 sm:px-5">
      <header className="flex flex-wrap items-start gap-3">
        <Illustration src={ICONS.koperta} size="event" className="bg-zus-50" />
        <div className="min-w-0 flex-1">
          <h2 id="documents" className="text-lg leading-tight font-bold text-navy-900">
            Wnioski i dokumenty
          </h2>
          <p className="mt-0.5 text-sm text-navy-500">Wypełnione z Waszego planu. Pobierz, podpisz, złóż.</p>
        </div>
        <Progress ready={ready} total={documents.length} />
      </header>

      <div className="mt-4 flex flex-wrap gap-2">
        <Action
          primary
          busy={busy === 'folder'}
          onClick={() =>
            run('folder', async () => (await pdf()).downloadFolder(timeline, scenario, profile, done))
          }
          icon={<FolderDown className="size-4" />}
        >
          Pobierz teczkę (PDF)
        </Action>
        <Action onClick={onPersonal} icon={<UserRound className="size-4" />}>
          Twoje dane do wniosków
          <span
            className={cn(
              'rounded-full px-1.5 py-0.5 text-[11px] font-black',
              personal.filled === personal.total ? 'bg-zus-50 text-zus-700' : 'bg-sun-100 text-sun-700',
            )}
          >
            {personal.filled}/{personal.total}
          </span>
        </Action>
        <Action
          busy={busy === 'plan'}
          onClick={() => run('plan', async () => (await pdf()).downloadPlan(timeline, scenario))}
          icon={<Printer className="size-4" />}
        >
          Plan na kartce A4
        </Action>
      </div>

      <ul className="mt-3 divide-y divide-line">
        {documents.map((d, index) => (
          <Row
            key={d.id}
            document={d}
            index={index}
            today={timeline.today}
            done={isDone(d)}
            locked={d.done}
            ticked={done}
            busy={busy === d.id}
            onToggle={toggle}
            onFill={onFill}
            onSelect={onSelect}
            onDownload={() =>
              run(d.id, async () => {
                if (!d.form) return
                const lib = await pdf()
                const attached = new Set(d.form.attachments.filter((a) => done.has(`${d.id}/${a.id}`)).map((a) => a.id))
                await lib.downloadRequest(d, lib.defaultValues(d.form, profile), profile, attached)
              })
            }
          />
        ))}
      </ul>
    </section>
  )
}

function Progress({ ready, total }: { ready: number; total: number }) {
  return (
    <div className="flex items-center gap-2.5" aria-label={`Gotowe ${ready} z ${total}`}>
      <span className="text-sm font-bold text-navy-700 tabular-nums">
        {ready} z {total} gotowe
      </span>
      <span className="h-2 w-20 overflow-hidden rounded-full bg-navy-50">
        <motion.span
          className="block h-full rounded-full bg-zus-600"
          initial={false}
          animate={{ width: `${total ? (ready / total) * 100 : 0}%` }}
          transition={{ duration: 0.4, ease: EASE_OUT }}
        />
      </span>
    </div>
  )
}

function Action({
  children,
  icon,
  onClick,
  primary,
  busy,
}: {
  children: ReactNode
  icon: ReactNode
  onClick: () => void
  primary?: boolean
  busy?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={cn(
        'flex h-10 items-center gap-2 rounded-full px-4 text-sm font-bold transition-[background-color,border-color,transform] duration-150 active:scale-[0.97] disabled:opacity-70',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2 focus-visible:outline-none',
        primary ? 'bg-zus-600 text-white hover:bg-zus-700' : 'border border-line text-navy-700 hover:bg-navy-50',
      )}
    >
      {busy ? <LoaderCircle className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

function Row({
  document: d,
  index,
  today,
  done,
  locked,
  ticked,
  busy,
  onToggle,
  onFill,
  onSelect,
  onDownload,
}: {
  document: Document
  index: number
  today: string
  done: boolean
  locked: boolean
  ticked: Set<string>
  busy: boolean
  onToggle: (id: string) => void
  onFill: (id: string) => void
  onSelect: (id: string) => void
  onDownload: () => void
}) {
  const [open, setOpen] = useState(false)
  const attachments = d.form?.attachments ?? []
  const gathered = attachments.filter((a) => ticked.has(`${d.id}/${a.id}`)).length
  const day = d.deadline ?? d.needed_by
  const left = dayCount(today, day)
  const when = d.deadline
    ? left >= 0 && left <= COUNTDOWN_DAYS
      ? `najpóźniej ${formatShortDate(d.deadline)} · ${daysLeftLabel(left)}`
      : left < 0
        ? `termin minął ${formatShortDate(d.deadline)}`
        : `najpóźniej ${formatShortDate(d.deadline)}`
    : `na ${formatShortDate(d.needed_by)} · bez terminu w materiałach`

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04, ease: EASE_OUT }}
      className="py-3"
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={done}
          aria-label={done ? `Oznacz jako niezłożony: ${d.title}` : `Oznacz jako złożony: ${d.title}`}
          disabled={locked}
          onClick={() => onToggle(d.id)}
          className={cn(
            'mt-1 flex size-6 shrink-0 items-center justify-center rounded-lg border-2 transition-colors duration-150',
            'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
            done ? 'border-zus-600 bg-zus-600 text-white' : 'border-navy-200 hover:border-zus-500',
          )}
        >
          {done && <Check className="size-4" strokeWidth={3} />}
        </button>
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => onSelect(d.id)}
            className={cn('text-left font-bold text-navy-900 hover:text-zus-700', done && 'text-navy-400 line-through')}
          >
            {d.title}
          </button>
          <p
            className={cn(
              'mt-0.5 flex flex-wrap items-center gap-x-1 text-sm',
              d.deadline && left >= 0 && left <= 14 ? 'font-bold text-sun-700' : 'text-navy-500',
              d.deadline && left < 0 && 'text-red-700',
            )}
          >
            {when}
            <CopyValue value={dotted(day)} label="datę" className="-my-1" />
          </p>
          {d.form && (
            <p className="text-xs text-navy-400">
              {d.form.official_form ? `Formularz ${d.form.official_form} · ` : ''}
              Składasz: {d.form.addressee_label}
            </p>
          )}
          {attachments.length > 0 && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="mt-1.5 flex items-center gap-1 text-xs font-bold text-navy-500 hover:text-navy-900"
            >
              <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
              Załączniki: {gathered} z {attachments.length}
            </button>
          )}
          <AnimatePresence initial={false}>
            {open && (
              <motion.ul
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.22, ease: EASE_OUT }}
                className="overflow-hidden"
              >
                {attachments.map((a) => {
                  const id = `${d.id}/${a.id}`
                  const on = ticked.has(id)
                  return (
                    <li key={a.id} className="mt-2 flex items-start gap-2.5">
                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={on}
                        aria-label={a.label}
                        onClick={() => onToggle(id)}
                        className={cn(
                          'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border-2 transition-colors',
                          on ? 'border-zus-600 bg-zus-600 text-white' : 'border-navy-200 hover:border-zus-500',
                        )}
                      >
                        {on && <Check className="size-3" strokeWidth={3} />}
                      </button>
                      <span className={cn('text-sm text-navy-700', on && 'text-navy-400 line-through')}>
                        {a.label}
                        {!a.required && <span className="text-navy-400"> (jeśli dotyczy)</span>}
                        {a.hint && <span className="block text-xs text-navy-400">{a.hint}</span>}
                      </span>
                    </li>
                  )
                })}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {d.form ? (
            <>
              <IconButton label={`Wypełnij: ${d.title}`} onClick={() => onFill(d.id)}>
                <PenLine className="size-4" />
                <span className="hidden sm:inline">Wypełnij</span>
              </IconButton>
              <IconButton label={`Pobierz PDF: ${d.title}`} onClick={onDownload} busy={busy}>
                {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
                <span className="hidden sm:inline">PDF</span>
              </IconButton>
            </>
          ) : (
            <img src={documentIcon(d)} alt="" className="size-8 object-contain opacity-80" draggable={false} />
          )}
        </div>
      </div>
    </motion.li>
  )
}

function IconButton({
  label,
  onClick,
  busy,
  children,
}: {
  label: string
  onClick: () => void
  busy?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={busy}
      className="flex h-9 items-center gap-1.5 rounded-full border border-line px-3 text-sm font-bold text-navy-700 transition-[background-color,transform] duration-150 hover:bg-navy-50 active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none disabled:opacity-60"
    >
      {children}
    </button>
  )
}

