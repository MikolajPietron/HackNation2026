// The documents the parents download: a request (the letter an employee files, or for a ZUS form
// the data to copy into it), the plan on one A4 page, the checklist and the folder with all of
// them. The words and dates are the engine's; this file only lays them out.
import { formatLongDate, todayIso } from '@/lib/dates'
import { formatPln } from '@/lib/money'
import { applicantOf, personalValue, type Profile } from '@/lib/personal'
import { sourceLabel } from '@/lib/ui'
import type { Document, FormField, RequestForm, Scenario, Timeline } from '@/types'
import { fileName, GREEN, MUTED, NAVY, newWriter, type Writer } from './core'

const APP = 'Zasiłkowy Przewodnik Przyszłego Rodzica · symulacja, nie decyzja ZUS'

/** 2027-01-27 -> 27.01.2027 */
export const dotted = (iso: string | null | undefined) => (iso ? iso.split('-').reverse().join('.') : '')

/** What the parent typed into the form (ApplicationForm), by field id; period: "id:from"/"id:to". */
export type FormValues = Record<string, string>

/** The form's values as the app fills them, with the personal ones from the profile. */
export function defaultValues(form: RequestForm, profile: Profile): FormValues {
  const values: FormValues = {}
  for (const field of form.fields) {
    if (field.kind === 'period') {
      values[`${field.id}:from`] = dotted(field.start)
      values[`${field.id}:to`] = dotted(field.end)
    } else if (field.kind === 'date') {
      values[field.id] = dotted(field.start) || (field.value ?? '')
    } else {
      values[field.id] = field.personal ? personalValue(field, form, profile) : (field.value ?? '')
    }
  }
  return values
}

/** A field as the request writes it (a period: "od … do …"). */
export function written(field: FormField, values: FormValues): string {
  if (field.kind === 'period') {
    const from = values[`${field.id}:from`]?.trim()
    const to = values[`${field.id}:to`]?.trim()
    return from || to ? `od ${from || '…'} do ${to || '…'}` : ''
  }
  return values[field.id]?.trim() ?? ''
}

const BLANK = '……………………………………'

function header(w: Writer, form: RequestForm, profile: Profile) {
  const { me, job } = applicantOf(form, profile)
  w.text(`${profile.place || '……………………'}, ${formatLongDate(todayIso())} r.`, { align: 'right', after: 6 })
  w.text(me.name || BLANK, { bold: true, after: 0.5 })
  w.text(me.address || BLANK, { color: MUTED, after: 0.5 })
  w.text('(imię i nazwisko, adres)', { size: 7.5, color: MUTED, after: 6 })
  const to = form.addressee === 'zus' ? 'Zakład Ubezpieczeń Społecznych' : job.name || form.addressee_label
  w.text(to, { bold: true, align: 'right', after: 0.5 })
  if (form.addressee !== 'zus') w.text(job.address || BLANK, { align: 'right', color: MUTED, after: 0.5 })
  w.text(`(${form.addressee_label.toLowerCase()})`, { size: 7.5, color: MUTED, align: 'right', after: 10 })
}

function signature(w: Writer) {
  w.ensure(26)
  w.space(14)
  w.text('……………………………………', { align: 'right', after: 0.5 })
  w.text('(podpis)', { size: 7.5, color: MUTED, align: 'right', after: 4 })
}

function attachments(w: Writer, form: RequestForm, attached?: Set<string>) {
  if (form.attachments.length === 0) return
  w.space(2)
  w.text('Załączniki:', { bold: true, after: 1.5 })
  for (const a of form.attachments) {
    w.checkbox(a.label + (a.required ? '' : ' (jeśli dotyczy)'), attached?.has(a.id) ?? false, { size: 9.5 })
  }
}

function basis(w: Writer, form: RequestForm) {
  const labels = [...new Set(form.legal_basis.map(sourceLabel))]
  if (labels.length === 0) return
  w.space(3)
  w.text(`Podstawa prawna: ${labels.join('; ')}.`, { size: 7.5, color: MUTED })
}

/** One request on its own page(s): the letter for the employer, or the data for a ZUS form. */
export function writeRequest(
  w: Writer,
  document: Document,
  form: RequestForm,
  values: FormValues,
  profile: Profile,
  attached?: Set<string>,
) {
  if (form.official_form) {
    writeOfficial(w, document, form, values)
    return
  }
  header(w, form, profile)
  w.text(form.title, { size: 15, bold: true, align: 'center', color: NAVY, after: 6 })
  for (const field of form.fields) {
    if (field.personal && field.id.endsWith('-name') && field.id === firstNameField(form)) continue
    w.row(field.label, written(field, values))
  }
  for (const note of form.notes) w.text(note.text, { size: 8.5, color: MUTED, after: 1 })
  attachments(w, form, attached)
  signature(w)
  basis(w, form)
}

/** The applicant's own name field: already in the letter's header. */
function firstNameField(form: RequestForm): string | undefined {
  return form.fields.find((f) => f.personal && f.id.endsWith('-name'))?.id
}

/** A ZUS form (ZAM, ZAS-53): the official form is on zus.pl; this page lists what to write in. */
function writeOfficial(w: Writer, document: Document, form: RequestForm, values: FormValues) {
  w.text(`Dane do formularza ${form.official_form}`, { size: 15, bold: true, color: NAVY, after: 1 })
  w.text(document.title, { color: MUTED, after: 4 })
  w.text(
    `Oficjalny formularz ${form.official_form} pobierzesz ze strony www.zus.pl (zakładka Wzory formularzy, ` +
      'Zasiłki). Poniżej dane z Twojego planu, które do niego wpiszesz.',
    { size: 9.5, after: 4 },
  )
  w.text(`Składasz go: ${form.addressee_label}.`, { size: 9.5, bold: true, color: GREEN, after: 4 })
  for (const field of form.fields) w.row(field.label, written(field, values))
  for (const note of form.notes) w.text(note.text, { size: 8.5, color: MUTED, after: 1 })
  attachments(w, form)
  basis(w, form)
}

/** The plan on one A4 page: periods with amounts, deadlines, the money by month. */
export function writePlan(w: Writer, timeline: Timeline, scenario: Scenario | null) {
  w.text('Plan rodzicielski', { size: 18, bold: true, color: NAVY, after: 0.5 })
  const situation = timeline.notes.find((n) => n.kind === 'situation')
  const anchor = timeline.taken_in
    ? `Przyjęcie dziecka: ${dotted(timeline.birth_date)}`
    : timeline.child_born
      ? `Data urodzenia: ${dotted(timeline.birth_date)}`
      : `Przewidywana data porodu: ${dotted(timeline.birth_date)}`
  w.text(`${anchor}${situation ? ` · ${situation.title}` : ''}`, { color: MUTED, after: 1 })
  w.text(`Stan na ${formatLongDate(timeline.today)} r.`, { size: 8.5, color: MUTED, after: 4 })

  const periods = timeline.segments
    .filter((s) => s.lane === 'mother' || s.lane === 'father')
    .sort((a, b) => a.start.localeCompare(b.start))
  if (periods.length > 0) {
    w.heading('Urlopy i zasiłki', 12)
    for (const s of periods) {
      const pay = timeline.payments.find((p) => p.segment_id === s.id)
      const who = s.lane === 'father' ? 'Tata' : 'Mama'
      const name = s.title.replace(/\s+[—–-]\s+do wyboru$/i, '')
      const option = s.tone === 'option' ? ' (do wyboru)' : ''
      const money = pay ? ` · ${formatPln(pay.monthly)} mies. (${String(pay.rate).replace('.', ',')}%)` : ''
      w.row(`${who}: ${name}${option}`, `${dotted(s.start)} – ${dotted(s.end)} · ${s.days} dni${money}`, 78)
    }
    w.space(2)
  }

  const deadlines = [
    ...timeline.documents
      .filter((d) => !d.done && d.needed_by >= timeline.today)
      .map((d) => ({
        day: d.deadline ?? d.needed_by,
        text: d.deadline ? `${d.title} — najpóźniej` : `${d.title} — na dzień startu (bez terminu w materiałach)`,
      })),
    ...timeline.markers
      .filter((m) => m.irreversible && m.date >= timeline.today)
      .map((m) => ({ day: m.date, text: `${m.title} — punkt bez powrotu` })),
  ].sort((a, b) => a.day.localeCompare(b.day))
  if (deadlines.length > 0) {
    w.heading('Wnioski i terminy', 12)
    for (const d of deadlines) w.row(dotted(d.day), d.text, 26)
    w.space(2)
  }

  if (timeline.monthly.length > 0 && timeline.money_total) {
    w.heading('Pieniądze miesiąc po miesiącu', 12)
    const months = timeline.monthly.map(
      (m) => `${m.month.slice(5)}.${m.month.slice(0, 4)}: ${formatPln(m.total)}`,
    )
    const columns = 3
    const perColumn = Math.ceil(months.length / columns)
    const colWidth = w.width / columns
    const top = w.y
    w.doc.setFont('Lato', 'normal')
    w.doc.setFontSize(9)
    w.doc.setTextColor('#1b2433')
    months.forEach((line, i) => {
      const col = Math.floor(i / perColumn)
      const rowIndex = i % perColumn
      w.doc.text(line, w.left + col * colWidth, top + 3.2 + rowIndex * 4.6)
    })
    w.y = top + perColumn * 4.6 + 2
    const t = timeline.money_total
    w.text(
      `Razem: ${formatPln(t.total)}${t.father > 0 ? ` (mama ${formatPln(t.mother)}, tata ${formatPln(t.father)})` : ''}`,
      { bold: true, after: 2 },
    )
  }
  if (scenario === null) return
  w.space(2)
  w.text(
    'Daty i kwoty policzył kalkulator reguł na podstawie Przewodnika ZUS, Kodeksu pracy i ustawy zasiłkowej; ' +
      'każda reguła ma w aplikacji cytat ze źródła. To symulacja, nie decyzja ZUS.',
    { size: 7.5, color: MUTED },
  )
}

/** What to file and what to attach, with boxes to tick (ticked = done in the app). */
export function writeChecklist(w: Writer, timeline: Timeline, done: Set<string>) {
  w.heading('Co złożyć i co dołączyć', 14)
  const documents = timeline.documents.filter((d) => d.needed_by >= timeline.today || !d.done)
  for (const d of documents) {
    const when = d.deadline ? `najpóźniej ${dotted(d.deadline)}` : `na ${dotted(d.needed_by)}`
    w.checkbox(`${d.title} — ${when}`, d.done || done.has(d.id), { bold: true, size: 10 })
    for (const a of d.form?.attachments ?? []) {
      w.checkbox(a.label + (a.required ? '' : ' (jeśli dotyczy)'), done.has(`${d.id}/${a.id}`), {
        size: 9,
        indent: 6,
        color: MUTED,
      })
    }
    w.space(1)
  }
}

/** Download one request as a PDF. */
export async function downloadRequest(
  document: Document,
  values: FormValues,
  profile: Profile,
  attached?: Set<string>,
) {
  if (!document.form) return
  const w = await newWriter(document.form.title)
  writeRequest(w, document, document.form, values, profile, attached)
  w.footer(APP)
  w.doc.save(fileName(document.form.official_form ? `dane do ${document.form.official_form}` : document.form.title))
}

/** Download the plan on one A4 page. */
export async function downloadPlan(timeline: Timeline, scenario: Scenario | null) {
  const w = await newWriter('Plan rodzicielski')
  writePlan(w, timeline, scenario)
  w.footer(APP)
  w.doc.save('plan-rodzicielski.pdf')
}

/** The parents' folder: the plan, the checklist and every request, in one PDF. */
export async function downloadFolder(timeline: Timeline, scenario: Scenario | null, profile: Profile, done: Set<string>) {
  const w = await newWriter('Teczka rodzica')
  writePlan(w, timeline, scenario)
  w.freshPage()
  writeChecklist(w, timeline, done)
  for (const d of timeline.documents) {
    if (!d.form || d.done || d.needed_by < timeline.today) continue
    w.freshPage()
    const attached = new Set(d.form.attachments.filter((a) => done.has(`${d.id}/${a.id}`)).map((a) => a.id))
    writeRequest(w, d, d.form, defaultValues(d.form, profile), profile, attached)
  }
  w.footer(APP)
  w.doc.save('teczka-rodzica.pdf')
}
