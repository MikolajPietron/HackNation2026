// A4 documents made in the browser (jsPDF, loaded only when a document is downloaded): the
// requests, the one-page plan and the parents' folder. Everything is generated here, so the
// personal data typed into the requests never leaves this browser. Font: Lato (SIL OFL 1.1,
// public/fonts/OFL.txt), subset to Latin with Polish letters and the superscripts of article
// numbers ("art. 182¹ᵃ").
import type { jsPDF as JsPdf } from 'jspdf'

export const INK = '#1b2433'
export const MUTED = '#5b6678'
export const LINE = '#d7dde5'
export const GREEN = '#007834'
export const NAVY = '#283754'

const PT = 0.3528 // mm per point

let fonts: Promise<{ regular: string; bold: string }> | null = null

async function base64(url: string): Promise<string> {
  const bytes = new Uint8Array(await (await fetch(url)).arrayBuffer())
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

function loadFonts() {
  const base = import.meta.env.BASE_URL
  fonts ??= Promise.all([base64(`${base}fonts/Lato-Regular.ttf`), base64(`${base}fonts/Lato-Bold.ttf`)]).then(
    ([regular, bold]) => ({ regular, bold }),
  )
  return fonts
}

export interface TextStyle {
  size?: number
  bold?: boolean
  color?: string
  align?: 'left' | 'right' | 'center'
  indent?: number
  /** Extra space after the block, in mm. */
  after?: number
  lineHeight?: number
}

/** Writes top to bottom on A4 pages, wrapping text and starting new pages as needed. */
export class Writer {
  readonly doc: JsPdf
  readonly left = 20
  readonly right = 20
  readonly top = 20
  readonly bottom = 20
  y = 20

  constructor(doc: JsPdf) {
    this.doc = doc
  }

  get pageWidth() {
    return this.doc.internal.pageSize.getWidth()
  }

  get pageHeight() {
    return this.doc.internal.pageSize.getHeight()
  }

  get width() {
    return this.pageWidth - this.left - this.right
  }

  newPage() {
    this.doc.addPage()
    this.y = this.top
  }

  /** Starts a new page unless the cursor is at its top already. */
  freshPage() {
    if (this.y > this.top + 1) this.newPage()
  }

  ensure(height: number) {
    if (this.y + height > this.pageHeight - this.bottom) this.newPage()
  }

  space(mm: number) {
    this.y += mm
  }

  private style({ size = 10, bold = false, color = INK }: TextStyle) {
    this.doc.setFont('Lato', bold ? 'bold' : 'normal')
    this.doc.setFontSize(size)
    this.doc.setTextColor(color)
  }

  /** Wrapped text; returns the height used. */
  text(content: string, style: TextStyle = {}): number {
    const { size = 10, align = 'left', indent = 0, after = 1.5, lineHeight = 1.4 } = style
    this.style(style)
    const width = this.width - indent
    const lines = this.doc.splitTextToSize(content, width) as string[]
    const step = size * PT * lineHeight
    for (const line of lines) {
      this.ensure(step)
      const x =
        align === 'right'
          ? this.pageWidth - this.right
          : align === 'center'
            ? this.pageWidth / 2
            : this.left + indent
      this.doc.text(line, x, this.y + size * PT, { align })
      this.y += step
    }
    this.y += after
    return lines.length * step + after
  }

  heading(content: string, size = 14) {
    this.ensure(size * PT * 3)
    this.text(content, { size, bold: true, color: NAVY, after: 2 })
  }

  rule(color = LINE) {
    this.doc.setDrawColor(color)
    this.doc.setLineWidth(0.25)
    this.doc.line(this.left, this.y, this.pageWidth - this.right, this.y)
    this.y += 2
  }

  /** Two columns: a muted label and its value, wrapped, with a thin line under the row. */
  row(label: string, value: string, labelWidth = 62) {
    const size = 10
    const step = size * PT * 1.4
    this.style({ size, color: MUTED })
    const labels = this.doc.splitTextToSize(label, labelWidth - 4) as string[]
    this.style({ size })
    const values = this.doc.splitTextToSize(value || '……………………………………', this.width - labelWidth) as string[]
    const height = Math.max(labels.length, values.length) * step + 2.5
    this.ensure(height)
    const top = this.y
    this.style({ size, color: MUTED })
    labels.forEach((line, i) => this.doc.text(line, this.left, top + size * PT + i * step))
    this.style({ size })
    values.forEach((line, i) => this.doc.text(line, this.left + labelWidth, top + size * PT + i * step))
    this.y = top + height - 1
    this.doc.setDrawColor(LINE)
    this.doc.setLineWidth(0.2)
    this.doc.line(this.left, this.y, this.pageWidth - this.right, this.y)
    this.y += 1.5
  }

  /** A box to tick by hand (or ticked), with its label wrapped beside it. */
  checkbox(label: string, checked: boolean, style: TextStyle = {}) {
    const size = style.size ?? 10
    const box = 3.4
    this.ensure(size * PT * 1.5)
    this.doc.setDrawColor(NAVY)
    this.doc.setLineWidth(0.3)
    this.doc.rect(this.left + (style.indent ?? 0), this.y + 0.6, box, box)
    if (checked) {
      const x = this.left + (style.indent ?? 0)
      this.doc.setLineWidth(0.5)
      this.doc.line(x + 0.7, this.y + 2.4, x + 1.5, this.y + 3.3)
      this.doc.line(x + 1.5, this.y + 3.3, x + 2.9, this.y + 1.1)
    }
    this.text(label, { ...style, indent: (style.indent ?? 0) + box + 2.5 })
  }

  /** Page numbers and the app's line at the bottom of every page. */
  footer(label: string) {
    const pages = this.doc.getNumberOfPages()
    for (let page = 1; page <= pages; page++) {
      this.doc.setPage(page)
      this.style({ size: 7.5, color: MUTED })
      const y = this.pageHeight - 10
      this.doc.text(label, this.left, y)
      this.doc.text(`${page} / ${pages}`, this.pageWidth - this.right, y, { align: 'right' })
    }
  }
}

/** A new A4 document with Lato, ready to write. */
export async function newWriter(title: string): Promise<Writer> {
  const [{ jsPDF }, { regular, bold }] = await Promise.all([import('jspdf'), loadFonts()])
  const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true })
  doc.addFileToVFS('Lato-Regular.ttf', regular)
  doc.addFont('Lato-Regular.ttf', 'Lato', 'normal')
  doc.addFileToVFS('Lato-Bold.ttf', bold)
  doc.addFont('Lato-Bold.ttf', 'Lato', 'bold')
  doc.setFont('Lato', 'normal')
  doc.setProperties({ title, creator: 'Zasiłkowy Przewodnik Przyszłego Rodzica' })
  return new Writer(doc)
}

/** "Wniosek o urlop rodzicielski" -> "wniosek-o-urlop-rodzicielski.pdf" */
export function fileName(title: string): string {
  const plain = title
    .toLowerCase()
    .replace(/ł/g, 'l')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${plain.slice(0, 80) || 'dokument'}.pdf`
}
