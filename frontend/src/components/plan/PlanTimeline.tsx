// The plan's timeline, built like a video editor's: a ruler with months and week ticks, tracks
// (Dziecko, Mama, Tata, Dokumenty) with clips for leave and keyframes for important days, and a
// playhead. Drag the playhead along the ruler to a day; ‹ › jump between events like keyframes. The tracks scroll sideways with momentum (drag
// them, or use the trackpad) and zoom on a spring (− / +, Ctrl/⌘ + wheel or pinch, anchored at
// the pointer). After a recalculation the old plan stays for a moment as a shadow (FUNKCJE F16).
//
// The scale is spent on the leave: deadlines years away (the end of parental leave in the year
// of the 6th birthday) sit behind a break in the scale, "⋯ 5 lat ⋯", so 20 weeks stay a clip you
// can read. A clip is always as long as its period. A period still to decide is a light dashed
// clip; one that can be taken any time up to a deadline (paternity leave) gets that window as a
// thin bracket under it, so the window never reads as a long period.
//
// Labels are measured in the real font: a name goes inside a clip in one line or two, else beside
// it, else the clip shows only its length; a run of pieces of one period (sick leave paid first
// by the employer, then by ZUS) is named once. Nothing is cut with "…": hovering any clip or
// amount shows a tooltip with its name, dates and money. The hovered element and the one whose
// details are open are outlined; what the last recalculation changed pulses amber.
//
// Motion follows Emil Kowalski's rules: springs for anything interruptible, no animation on what
// repeats constantly (scrubbing follows the pointer 1:1), reduced motion respected.
import { Fragment, useCallback, useEffect, useEffectEvent, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent, PointerEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { animate, AnimatePresence, motion, useReducedMotion } from 'motion/react'
import type { AnimationPlaybackControls } from 'motion/react'
import { Check, ChevronLeft, ChevronRight, Lock, Maximize2, Minimize2, Minus, Plus } from 'lucide-react'
import dziecko from '@/assets/onboarding/dziecko.webp'
import mama from '@/assets/onboarding/mama.webp'
import pieniadze from '@/assets/onboarding/pieniadze.webp'
import tata from '@/assets/onboarding/tata.webp'
import zaswiadczenie from '@/assets/onboarding/zaswiadczenie.webp'
import {
  dayNumber,
  formatDayMonthShort,
  formatShortDate,
  isoFromDay,
  monthCells,
} from '@/lib/dates'
import { SPRING_LAYOUT } from '@/lib/ease'
import { Pulse } from '@/components/timeline/Pulse'
import { Illustration } from '@/components/ui/illustration'
import { documentIcon, isKeyMarker, markerIcon, segmentIcon } from '@/lib/icons'
import { formatPlnShort, formatRate, paymentFor } from '@/lib/money'
import { clipName, deadlineOf, length, optionWindow, periodName } from '@/lib/plan'
import { remPx, textWidth, whenFontsReady } from '@/lib/textWidth'
import { LANE_ORDER } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Lane, Payment, Segment, Timeline } from '@/types'

/** Days of margin before the first and after the last element. */
const PAD_DAYS = 10
/** Pixels kept free at both ends of the track, so nothing slides under the track names. */
const EDGE = 28
/** The hatched break in the scale, and the whole far part after it (the break included). */
const BREAK_GAP = 64
const BREAK = 172
/** A day this long after the last period goes behind the break. */
const FAR_AFTER_DAYS = 120
const LABEL_WIDTH = 120
const RULER_HEIGHT = 44
/** The height of a track; a track whose flags need more rows grows by a row each. */
const ROW_HEIGHT = 84
/** A row of flags; an event chip (40 px) and a hint chip (30 px) are centred in it. */
const FLAG_EVENT_HEIGHT = 40
const FLAG_HINT_HEIGHT = 30
/** Space between two rows of flags, and above and below them in a grown track. */
const FLAG_GAP = 6
const FLAG_ROW = FLAG_EVENT_HEIGHT + FLAG_GAP
const TRACK_PAD = 10
/** Space kept between two flags in one row. */
const FLAG_SPACE = 8
/** A chip right of its day starts this far before it, so its round edge sits on the day. */
const FLAG_HANG = 6
const CLIP_HEIGHT = 46
const CLIP_TOP = (ROW_HEIGHT - CLIP_HEIGHT) / 2
/** A payment on the money track: two rows (mother, father) fit in one track. */
const MONEY_CLIP = 30
/** The bracket of a period's window, under its clip: the track grows by this much. */
const WINDOW_BAND = 22
/** Padding inside a clip (px-3) and inside a payment (px-2), and the room an icon takes. */
const CLIP_PAD = 24
const MONEY_PAD = 16
const ICON_ROOM = 34
/** Space between a clip and the label beside it (pl-2.5 / pr-2.5). */
const BESIDE = 12
/** Heights in the tracks follow the text size ("Większy tekst" scales rem), like the chips. */
const rem = (px: number) => `${px / 16}rem`
const MIN_ZOOM = 1
const MAX_ZOOM = 8
const ZOOM_STEP = 1.6
const ZOOM_SPRING = { type: 'spring', stiffness: 260, damping: 32, mass: 0.6 } as const
/** Momentum after a drag: share of the velocity kept per millisecond. */
const GLIDE_DECAY = 0.995

const LANES: Record<Lane, { label: string; image: string }> = {
  child: { label: 'Dziecko', image: dziecko },
  mother: { label: 'Mama', image: mama },
  father: { label: 'Tata', image: tata },
  documents: { label: 'Dokumenty', image: zaswiadczenie },
}

/** Tracks that hold periods (clips); the others hold only keyframes. */
const PARENTS: Lane[] = ['mother', 'father']

/** Green is the mother, navy the father; a dashed clip is still to decide. */
const CLIP: Record<'mother' | 'father', Record<Segment['tone'], string>> = {
  mother: {
    leave: 'bg-zus-600 text-white',
    option: 'border-2 border-dashed border-zus-300 bg-zus-50 text-zus-900',
    work: 'bg-navy-100 text-navy-700',
  },
  father: {
    leave: 'bg-navy-700 text-white',
    option: 'border-2 border-dashed border-navy-300 bg-navy-50 text-navy-900',
    work: 'bg-navy-100 text-navy-700',
  },
}

const parentOf = (segment: Segment) => (segment.lane === 'father' ? 'father' : 'mother')

interface Flag {
  id: string
  day: number
  text: string
  icon: string
  kind: 'marker' | 'document'
  done?: boolean
  /** An event (bigger, bold, amber) rather than a hint. */
  key: boolean
  /** A point of no return (FUNKCJE F10): a lock on the flag. */
  locked?: boolean
}

interface PlacedFlag extends Flag {
  row: number
  side: 'right' | 'left'
}

/** A guess at a chip's width, until it is on screen and measured. */
const estimatedWidth = (flag: Flag) =>
  flag.key ? flag.text.length * 7.6 + 64 : flag.text.length * 6.7 + 48

/**
 * Flags of one track without overlapping: each takes the first row where it fits, and a flag
 * that fits in none starts a new row, so the track grows instead of hiding a flag under another.
 */
function placeFlags(
  flags: Flag[],
  x: (day: number) => number,
  width: number,
  measured: Record<string, number>,
): PlacedFlag[] {
  const spans = flags.map((flag) => {
    const w = measured[flag.id] ?? estimatedWidth(flag)
    const px = (x(flag.day) / 100) * width
    // A chip hangs right of its day; near the end of the track it hangs left.
    const side: PlacedFlag['side'] = px + w > width ? 'left' : 'right'
    const start = side === 'right' ? px - FLAG_HANG : px - w
    return { flag, side, start, end: start + w }
  })
  // By where they start on screen, so the first row that fits is enough (interval packing).
  spans.sort((a, b) => a.start - b.start || a.flag.day - b.flag.day)
  const rowEnds: number[] = []
  return spans.map(({ flag, side, start, end }) => {
    let row = rowEnds.findIndex((rowEnd) => start >= rowEnd + FLAG_SPACE)
    if (row === -1) row = rowEnds.length
    rowEnds[row] = end
    return { ...flag, row, side }
  })
}

/** How a clip (or a run of pieces of one period) is labelled: inside if it fits, in one line or
 *  as the name over the length, else beside it, else just its length, else nothing (the
 *  tooltip names it). Never cut with "…". */
interface ClipLabel {
  /** One line, or two: the name over the length. */
  inside: string[] | null
  /** The inside text names the period (not just its length). */
  named: boolean
  icon: boolean
  dates: boolean
  outside: { text: string; side: 'right' | 'left'; width: number } | null
}

const NO_LABEL: ClipLabel = { inside: null, named: false, icon: false, dates: false, outside: null }

/** Widths of bold text as the clips draw it: text-sm names, text-xs lengths and amounts. */
interface Fit {
  sm: (text: string) => number
  xs: (text: string) => number
}

/** The shortest word for a kind of period, for a narrow clip. */
const TINY: [string, string][] = [
  ['sick', 'L4'],
  ['maternity', 'Macierzyński'],
  ['parental', 'Rodzicielski'],
  ['paternity', 'Ojcowski'],
  ['supplementary', 'Uzupełniający'],
]
const tinyName = (id: string, fallback: string) =>
  TINY.find(([prefix]) => id.startsWith(prefix))?.[1] ?? fallback.split(' ')[0]

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** "Zwolnienie lekarskie w ciąży: zasiłek chorobowy" → the period and this piece of it. */
function family(segment: Segment): { kind: string; part: string } | null {
  const name = clipName(segment)
  const at = name.indexOf(':')
  return at > 0 ? { kind: name.slice(0, at).trim(), part: capital(name.slice(at + 1).trim()) } : null
}

const shortName = (segment: Segment) => clipName(segment).replace(/\s+(po porodzie|przed porodem)$/, '')

/** The names a clip can go by, longest first. */
function clipNames(segment: Segment): string[] {
  const f = family(segment)
  const names = f
    ? [clipName(segment), f.part, f.kind.replace(/\s+w ciąży$/, '')]
    : [clipName(segment), shortName(segment)]
  return [...new Set([...names, tinyName(segment.id, shortName(segment))])]
}

/** The names of a run of pieces of one period. */
function runNames(first: Segment): string[] {
  const kind = family(first)?.kind ?? shortName(first)
  return [...new Set([kind, kind.replace(/\s+w ciąży$/, ''), tinyName(first.id, kind)])]
}

function labelClip(
  names: string[],
  days: number,
  option: boolean,
  px: number,
  roomBefore: number,
  roomAfter: number,
  fit: Fit,
  dates: string | null,
): ClipLabel {
  const weeks = length(days)
  const tail = option ? `${weeks} · do wyboru` : weeks
  const oneLine = (text: string) => fit.sm(text) + CLIP_PAD
  const twoLines = ([name, under]: string[]) => Math.max(fit.sm(name), fit.xs(under)) + CLIP_PAD
  for (const name of names) {
    const candidates: string[][] = [
      ...(option ? [[`${name} · ${weeks} · do wyboru`]] : []),
      [`${name} · ${weeks}`],
      [name, tail],
      ...(option ? [[name, weeks]] : []),
    ]
    for (const lines of candidates) {
      const need = lines.length === 1 ? oneLine(lines[0]) : twoLines(lines)
      if (need > px) continue
      const icon = px >= need + ICON_ROOM
      return {
        inside: lines,
        named: true,
        icon,
        dates: Boolean(dates) && lines.length === 1 && icon && px >= need + ICON_ROOM + fit.xs(dates ?? '') + 16,
        outside: null,
      }
    }
  }
  // Too narrow for a name: beside the clip, where the track has room.
  for (const name of names) {
    const text = `${name} · ${weeks}${option ? ' · do wyboru' : ''}`
    const width = fit.sm(text) + BESIDE
    const side = roomAfter >= width ? 'right' : roomBefore >= width ? 'left' : null
    if (side) return { ...NO_LABEL, outside: { text, side, width } }
  }
  return { ...NO_LABEL, inside: oneLine(weeks) <= px ? [weeks] : null }
}

/** One element of a track: a clip, or a run of pieces of one period joined end to end. */
interface Unit {
  members: Segment[]
  /** First day, and the day after the last. */
  start: number
  end: number
}

/** What the tooltip says about an element, and where it was hovered. */
interface Tip {
  id: string
  x: number
  top: number
  bottom: number
  title: string
  lines: string[]
}

const dayRange = (start: string, end: string) =>
  start === end ? formatShortDate(start) : `${formatDayMonthShort(start)} – ${formatShortDate(end)}`

const clampZoom = (zoom: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom))
/** 1970-01-01 was a Thursday, so Mondays are the days with (day + 3) % 7 === 0. */
const isMonday = (day: number) => (((day + 3) % 7) + 7) % 7 === 0

interface Props {
  timeline: Timeline
  changedIds: Set<string>
  changeVersion: number
  selectedId: string | null
  onSelect: (id: string) => void
  hoveredId: string | null
  onHover: (id: string | null) => void
  initialZoom?: number
  expanded?: boolean
  onToggleExpanded?: () => void
  /** Put first in the toolbar (the switch between the axis and the calendar). */
  toolbarStart?: ReactNode
  /** After a change of the plan: the playhead goes to this day (a new key moves it again). */
  focus?: { day: number; key: number } | null
}

export function PlanTimeline({
  timeline,
  changedIds,
  changeVersion,
  selectedId,
  onSelect,
  hoveredId,
  onHover,
  initialZoom = 1,
  expanded = false,
  onToggleExpanded,
  toolbarStart,
  focus = null,
}: Props) {
  const reduceMotion = useReducedMotion()
  const scroller = useRef<HTMLDivElement>(null)
  const [viewport, setViewport] = useState(0)
  const [zoom, setZoom] = useState(initialZoom)
  const zoomRef = useRef(initialZoom)
  const zoomAnimation = useRef<AnimationPlaybackControls | null>(null)
  const anchor = useRef<{ ratio: number; offset: number; keep: boolean } | null>(null)
  const drag = useRef<{ x: number; left: number; lastX: number; lastT: number; v: number } | null>(null)
  const glide = useRef(0)
  const [scrubbing, setScrubbing] = useState(false)
  const previous = useRef<Segment[] | null>(null)
  const [shadow, setShadow] = useState<{ segments: Segment[]; key: number } | null>(null)

  // The real width of every flag chip, so rows are packed by what is on screen (the text size
  // can change), not by a guess.
  const [chipWidths, setChipWidths] = useState<Record<string, number>>({})
  const [chipObserver] = useState(
    () =>
      new ResizeObserver((entries) =>
        setChipWidths((current) => {
          let next = current
          for (const entry of entries) {
            const element = entry.target as HTMLElement
            const id = element.dataset.flag
            const w = element.offsetWidth
            if (!id || w === 0 || current[id] === w) continue
            if (next === current) next = { ...current }
            next[id] = w
          }
          return next
        }),
      ),
  )
  useEffect(() => () => chipObserver.disconnect(), [chipObserver])
  const measureChip = useCallback(
    (element: HTMLElement | null) => {
      if (!element) return
      chipObserver.observe(element)
      return () => chipObserver.unobserve(element)
    },
    [chipObserver],
  )

  const today = dayNumber(timeline.today)
  const [playhead, setPlayhead] = useState(today)

  const width = Math.max(360, (viewport - LABEL_WIDTH) * zoom)

  // Labels are measured in Lato; once it has loaded, measure again.
  const [, setFontsLoaded] = useState(0)
  useEffect(() => whenFontsReady(() => setFontsLoaded((n) => n + 1)), [])
  const scale = remPx() / 16
  const fit: Fit = { sm: (text) => textWidth(text, 14 * scale), xs: (text) => textWidth(text, 12 * scale) }

  // The tooltip of the hovered clip, window or amount; it goes away as soon as anything scrolls.
  const [tip, setTip] = useState<Tip | null>(null)
  useEffect(() => {
    if (!tip) return
    const hide = () => setTip(null)
    window.addEventListener('scroll', hide, true)
    window.addEventListener('pointerdown', hide, true)
    return () => {
      window.removeEventListener('scroll', hide, true)
      window.removeEventListener('pointerdown', hide, true)
    }
  }, [tip])
  /** Hover in or out of an element: the shared highlight, and its tooltip. */
  const hoverWith =
    (id: string, title: string, lines: () => string[]) => (event: MouseEvent<HTMLElement> | null) => {
      onHover(event ? id : null)
      if (!event || drag.current || scrubbing) return setTip(null)
      const rect = event.currentTarget.getBoundingClientRect()
      setTip({ id, x: event.clientX, top: rect.top, bottom: rect.bottom, title, lines: lines() })
    }

  useEffect(() => {
    const element = scroller.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setViewport(entry.contentRect.width))
    observer.observe(element)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(glide.current)
      zoomAnimation.current?.stop()
    }
  }, [])

  /** Zoom keeping the point under `offset` (px from the scroller's left edge) in place. */
  const zoomTo = useCallback(
    (next: number, offset?: number, smooth = true) => {
      const element = scroller.current
      if (!element) return
      const target = clampZoom(next)
      if (Math.abs(target - zoomRef.current) < 0.001) return
      const at = offset ?? LABEL_WIDTH + (element.clientWidth - LABEL_WIDTH) / 2
      const track = Math.max(360, (element.clientWidth - LABEL_WIDTH) * zoomRef.current)
      zoomAnimation.current?.stop()
      const instant = !smooth || Boolean(reduceMotion)
      anchor.current = {
        ratio: (element.scrollLeft + at - LABEL_WIDTH) / track,
        offset: at,
        keep: !instant,
      }
      if (instant) {
        zoomRef.current = target
        setZoom(target)
        return
      }
      zoomAnimation.current = animate(zoomRef.current, target, {
        ...ZOOM_SPRING,
        onUpdate: (value) => {
          zoomRef.current = value
          setZoom(value)
        },
        onComplete: () => {
          anchor.current = null
        },
      })
    },
    [reduceMotion],
  )

  useLayoutEffect(() => {
    const element = scroller.current
    const pending = anchor.current
    if (!element || !pending) return
    if (!pending.keep) anchor.current = null
    element.scrollLeft = pending.ratio * width + LABEL_WIDTH - pending.offset
  }, [width])

  // Ctrl/⌘ + wheel (and trackpad pinch) zooms, following the fingers without a spring.
  useEffect(() => {
    const element = scroller.current
    if (!element) return
    const onWheel = (event: WheelEvent) => {
      cancelAnimationFrame(glide.current)
      if (!event.ctrlKey && !event.metaKey) return
      event.preventDefault()
      zoomTo(
        zoomRef.current * Math.exp(-event.deltaY * 0.01),
        event.clientX - element.getBoundingClientRect().left,
        false,
      )
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [zoomTo])

  // F16: keep the periods that moved, to draw them as a fading shadow of the old plan.
  useEffect(() => {
    const before = previous.current
    previous.current = timeline.segments
    if (!before) return
    const moved = before.filter(
      (old) =>
        PARENTS.includes(old.lane) &&
        !timeline.segments.some((s) => s.start === old.start && s.end === old.end && s.tone === old.tone),
    )
    if (moved.length > 0) setShadow({ segments: moved, key: Date.now() })
  }, [timeline])

  // The scale: the periods and what is near them get the width; far deadlines sit behind a break.
  const birth = dayNumber(timeline.birth_date)
  const laneSegments = (lane: Lane) => timeline.segments.filter((s) => s.lane === lane)
  const windows = timeline.segments
    .map((s) => ({ segment: s, deadline: optionWindow(timeline, s) }))
    .filter((w): w is { segment: Segment; deadline: NonNullable<typeof w.deadline> } => Boolean(w.deadline))
  const periodDays = timeline.segments.flatMap((s) => [dayNumber(s.start), dayNumber(s.end) + 1])
  const lastPeriod = Math.max(today, birth, ...periodDays)
  const datedDays = [
    ...timeline.markers.map((m) => dayNumber(m.date)),
    ...timeline.documents.map((d) => dayNumber(d.needed_by)),
  ]
  const isFar = (day: number) => day > lastPeriod + FAR_AFTER_DAYS
  const near = [today, birth, ...periodDays, ...datedDays.filter((day) => !isFar(day))]
  const farDays = datedDays.filter(isFar)
  const from = Math.min(...near) - PAD_DAYS
  const to = Math.max(...near) + PAD_DAYS
  const farTo = farDays.length ? Math.max(...farDays) : to
  const breakPx = farDays.length ? BREAK : 0
  const mainPx = width - 2 * EDGE - breakPx
  const xPx = (day: number) =>
    day <= to
      ? EDGE + ((day - from) / (to - from)) * mainPx
      : EDGE + mainPx + BREAK_GAP + (farTo > to ? (day - to) / (farTo - to) : 1) * (breakPx - BREAK_GAP - 8)
  const x = (day: number) => (xPx(day) / width) * 100
  const pxPerDay = mainPx / (to - from)
  const last = farDays.length ? farTo : to
  const head = Math.min(Math.max(playhead, from), last)
  const months = monthCells(from, to)
  const breakYears = Math.round((farTo - to) / 365.25)

  // A zoomed-in axis (the expanded view) opens at today, not at the start.
  const startAtToday = useRef(initialZoom > 1)
  useLayoutEffect(() => {
    const element = scroller.current
    if (!element || !startAtToday.current || viewport === 0) return
    startAtToday.current = false
    const visible = element.clientWidth - LABEL_WIDTH
    element.scrollLeft = Math.max(0, xPx(today) - visible * 0.2)
  })

  /** Days a jump can land on: today and every start, end and dated element. */
  const stops = useMemo(() => {
    const all = new Set<number>([today])
    for (const s of timeline.segments) {
      all.add(dayNumber(s.start))
      all.add(dayNumber(s.end))
    }
    for (const m of timeline.markers) all.add(dayNumber(m.date))
    for (const d of timeline.documents) all.add(dayNumber(d.needed_by))
    return [...all].sort((a, b) => a - b)
  }, [timeline, today])
  const previousStop = [...stops].reverse().find((day) => day < head)
  const nextStop = stops.find((day) => day > head)

  /** Bring a day into view, centred, if it is near or past an edge. */
  const reveal = (day: number) => {
    const element = scroller.current
    if (!element) return
    const position = LABEL_WIDTH + xPx(day)
    const left = element.scrollLeft + LABEL_WIDTH + 48
    const right = element.scrollLeft + element.clientWidth - 48
    if (position >= left && position <= right) return
    element.scrollTo({
      left: position - LABEL_WIDTH - (element.clientWidth - LABEL_WIDTH) / 2,
      behavior: reduceMotion ? 'auto' : 'smooth',
    })
  }
  const jump = (day: number) => {
    setPlayhead(day)
    reveal(day)
  }

  // A change of the plan puts the playhead on what changed; the axis scrolls to it when zoomed
  // in. An axis that opens later does not jump to an old change.
  const focusKey = focus?.key ?? null
  const focusDay = focus?.day ?? null
  const [focusSeen, setFocusSeen] = useState(focusKey)
  if (focusKey !== focusSeen) {
    setFocusSeen(focusKey)
    if (focusDay !== null) setPlayhead(focusDay)
  }
  const revealed = useRef(focusKey)
  const revealOn = useEffectEvent((day: number) => reveal(day))
  useEffect(() => {
    if (focusKey === revealed.current || focusDay === null) return
    revealed.current = focusKey
    revealOn(focusDay)
  }, [focusKey, focusDay])

  /** The day under the pointer; the break in the scale counts as its last day. */
  const dayAt = (clientX: number) => {
    const element = scroller.current
    if (!element) return head
    const content = clientX - element.getBoundingClientRect().left + element.scrollLeft - LABEL_WIDTH
    return Math.min(to, Math.max(from, Math.round(from + ((content - EDGE) / mainPx) * (to - from))))
  }

  // Scrubbing: the playhead follows the pointer on the ruler 1:1.
  const startScrub = (event: PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return
    event.stopPropagation()
    cancelAnimationFrame(glide.current)
    event.currentTarget.setPointerCapture(event.pointerId)
    setScrubbing(true)
    setPlayhead(dayAt(event.clientX))
  }
  const moveScrub = (event: PointerEvent<HTMLElement>) => {
    if (scrubbing) setPlayhead(dayAt(event.clientX))
  }
  const endScrub = () => setScrubbing(false)

  // Dragging the tracks scrolls them, and a flick keeps them gliding (like a carousel).
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    cancelAnimationFrame(glide.current)
    const scrollable = event.currentTarget.scrollWidth > event.currentTarget.clientWidth
    if (event.button !== 0 || !scrollable || (event.target as HTMLElement).closest('button')) return
    drag.current = {
      x: event.clientX,
      left: event.currentTarget.scrollLeft,
      lastX: event.clientX,
      lastT: event.timeStamp,
      v: 0,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const current = drag.current
    if (!current) return
    event.currentTarget.scrollLeft = current.left - (event.clientX - current.x)
    const dt = event.timeStamp - current.lastT
    if (dt > 0) current.v = 0.8 * ((event.clientX - current.lastX) / dt) + 0.2 * current.v
    current.lastX = event.clientX
    current.lastT = event.timeStamp
  }
  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const current = drag.current
    drag.current = null
    if (!current || reduceMotion || Math.abs(current.v) < 0.05) return
    const element = event.currentTarget
    let velocity = current.v
    let lastTime = performance.now()
    const step = (now: number) => {
      const dt = now - lastTime
      lastTime = now
      element.scrollLeft -= velocity * dt
      velocity *= Math.pow(GLIDE_DECAY, dt)
      const atEdge =
        element.scrollLeft <= 0 || element.scrollLeft >= element.scrollWidth - element.clientWidth
      if (Math.abs(velocity) > 0.02 && !atEdge) glide.current = requestAnimationFrame(step)
    }
    glide.current = requestAnimationFrame(step)
  }

  // Keyframes per track. The birth is a keyframe on the child's track and a line through all.
  const flags: Record<Lane, Flag[]> = { child: [], mother: [], father: [], documents: [] }
  for (const m of timeline.markers) {
    const day = dayNumber(m.date)
    flags[m.lane === 'documents' ? 'documents' : 'child'].push({
      id: m.id,
      day,
      // Behind the break the year matters.
      text: `${m.label} · ${isFar(day) ? formatShortDate(m.date) : formatDayMonthShort(m.date)}`,
      icon: markerIcon(m),
      kind: 'marker',
      key: isKeyMarker(m),
      locked: m.irreversible !== null && m.irreversible.days_left >= 0,
    })
  }
  for (const d of timeline.documents) {
    flags.documents.push({
      id: d.id,
      day: dayNumber(d.needed_by),
      text: `${d.label} · ${formatDayMonthShort(d.needed_by)}`,
      icon: documentIcon(d),
      kind: 'document',
      done: d.done,
      key: !d.done,
    })
  }
  const lanes = (Object.keys(LANES) as Lane[])
    .filter((lane) => flags[lane].length > 0 || laneSegments(lane).length > 0)
    .sort((a, b) => LANE_ORDER[a] - LANE_ORDER[b])
  // The money track: what is paid for each period, the mother's above the father's.
  const payments = timeline.payments
  const moneyLanes = (['mother', 'father'] as const).filter((lane) => payments.some((p) => p.lane === lane))
  const rowsBelowRuler = Math.max(1, lanes.length + (payments.length > 0 ? 1 : 0))

  const sortedIn = (lane: Lane) =>
    laneSegments(lane).sort((a, b) => a.start.localeCompare(b.start))
  const joins = (a: Segment | undefined, b: Segment | undefined) =>
    Boolean(a && b && a.tone === b.tone && dayNumber(a.end) + 1 === dayNumber(b.start))

  // What the tooltips say: the engine's names, dates and amounts, nothing computed here.
  const segmentTip = (s: Segment) => () => {
    const lines = [`${dayRange(s.start, s.end)} · ${length(s.days)}`]
    if (s.tone === 'option') {
      const deadline = deadlineOf(timeline, s)
      lines.push(
        !deadline
          ? 'Do wyboru'
          : optionWindow(timeline, s)
            ? `Do wyboru: w dowolnym czasie do ${formatShortDate(deadline.date)}`
            : `Do wyboru, najpóźniej do ${formatShortDate(deadline.date)}`,
      )
    }
    const payment = paymentFor(timeline, s.id)
    if (payment) lines.push(`${formatPlnShort(payment.monthly)} / mies. · ${formatRate(payment.rate)}`)
    return lines
  }
  const paymentTip = (p: Payment) => () => [
    `${formatPlnShort(p.monthly)} / mies. · ${formatRate(p.rate)}`,
    `${dayRange(p.start, p.end)} · ${length(p.days)} · razem ${formatPlnShort(p.total)}`,
  ]

  // The money track: one row per parent. Pieces paid the same per month, end to end (sick pay,
  // then the sickness benefit, then maternity benefit), share one amount.
  const moneyRow = (p: Payment) => Math.max(0, moneyLanes.indexOf(p.lane))
  const moneyTop = (row: number) =>
    moneyLanes.length === 1
      ? (ROW_HEIGHT - MONEY_CLIP) / 2
      : (ROW_HEIGHT - 2 * MONEY_CLIP - 4) / 2 + row * (MONEY_CLIP + 4)
  const moneyName = (p: Payment) => {
    const segment = timeline.segments.find((s) => s.id === p.segment_id)
    if (!segment) return p.title
    return family(segment)?.part ?? shortName(segment)
  }
  const paidTogether = (a: Payment, b: Payment) =>
    a.lane === b.lane && a.monthly === b.monthly && dayNumber(a.end) + 1 === dayNumber(b.start)
  const moneyUnits = moneyLanes.flatMap((lane) => {
    const row = [...payments.filter((p) => p.lane === lane)].sort((a, b) => a.start.localeCompare(b.start))
    const units: Payment[][] = []
    for (const p of row) {
      const last = units.at(-1)
      if (last && paidTogether(last[last.length - 1], p)) last.push(p)
      else units.push([p])
    }
    let taken = EDGE
    return units.map((members, index) => {
      const first = members[0]
      const lastMember = members[members.length - 1]
      const start = xPx(dayNumber(first.start))
      const end = xPx(dayNumber(lastMember.end) + 1)
      const nextStart = index < units.length - 1 ? xPx(dayNumber(units[index + 1][0].start)) : EDGE + mainPx
      const amount = `${formatPlnShort(first.monthly)} / mies.`
      const name = members.length === 1 ? moneyName(first) : null
      const inside = [...(name ? [`${name} · ${amount}`] : []), amount, formatPlnShort(first.monthly)].find(
        (text) => fit.xs(text) + MONEY_PAD <= end - start,
      )
      let outside: { text: string; side: 'right' | 'left' } | null = null
      if (!inside) {
        for (const text of [...(name ? [`${name} · ${amount}`] : []), amount]) {
          const need = fit.xs(text) + BESIDE
          const side = nextStart - end >= need ? 'right' : start - taken >= need ? 'left' : null
          if (side) {
            outside = { text, side }
            taken = side === 'right' ? end + need : end
            break
          }
        }
      }
      if (!outside) taken = end
      return { members, row: moneyRow(first), inside: inside ?? null, outside }
    })
  })

  // Ruler ticks: weeks when they have room, days when zoomed in far.
  const ticks: { day: number; size: 'day' | 'week' }[] = []
  if (pxPerDay * 7 >= 12) {
    for (let day = Math.ceil(from); day <= to; day += 1) {
      if (isMonday(day)) ticks.push({ day, size: 'week' })
      else if (pxPerDay >= 12) ticks.push({ day, size: 'day' })
    }
  }

  // The playhead's label stays beside the line near the ends instead of sliding under the names.
  const headPx = xPx(head)
  const headSide = headPx < 56 ? 'start' : headPx > width - 56 ? 'end' : 'middle'

  return (
    <div>
      <div className="mb-2 flex items-center gap-1">
        {toolbarStart}
        <ToolButton
          label="Poprzednie zdarzenie"
          onClick={() => previousStop !== undefined && jump(previousStop)}
          disabled={previousStop === undefined}
        >
          <ChevronLeft className="size-4" />
        </ToolButton>
        <ToolButton label="Pokaż dziś" onClick={() => jump(today)} disabled={head === today}>
          <span className="px-1 text-xs font-bold">Dziś</span>
        </ToolButton>
        <ToolButton
          label="Następne zdarzenie"
          onClick={() => nextStop !== undefined && jump(nextStop)}
          disabled={nextStop === undefined}
        >
          <ChevronRight className="size-4" />
        </ToolButton>
        <span className="ml-auto" />
        <ToolButton
          label="Oddal"
          onClick={() => zoomTo(zoomRef.current / ZOOM_STEP)}
          disabled={zoom <= MIN_ZOOM + 0.001}
        >
          <Minus className="size-4" />
        </ToolButton>
        <ToolButton
          label="Przybliż"
          onClick={() => zoomTo(zoomRef.current * ZOOM_STEP)}
          disabled={zoom >= MAX_ZOOM - 0.001}
        >
          <Plus className="size-4" />
        </ToolButton>
        {onToggleExpanded && (
          <ToolButton label={expanded ? 'Zwiń oś' : 'Rozwiń oś'} onClick={onToggleExpanded}>
            {expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </ToolButton>
        )}
      </div>

      <div
        ref={scroller}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => (drag.current = null)}
        className={cn(
          'overflow-x-auto overscroll-x-contain pb-2 select-none [scrollbar-width:thin]',
          zoom > 1.001 && 'cursor-grab active:cursor-grabbing',
        )}
      >
        <div
          className="grid"
          style={{ gridTemplateColumns: `${LABEL_WIDTH}px ${width}px`, width: LABEL_WIDTH + width }}
        >
          {/* Ruler. */}
          <div
            className="sticky left-0 z-30 border-b border-line bg-white"
            style={{ gridColumn: 1, gridRow: 1, height: RULER_HEIGHT }}
          />
          <div
            data-ruler
            onPointerDown={startScrub}
            onPointerMove={moveScrub}
            onPointerUp={endScrub}
            onPointerCancel={endScrub}
            className="relative cursor-ew-resize border-b border-line"
            style={{ gridColumn: 2, gridRow: 1, height: RULER_HEIGHT }}
          >
            {months.map((month, index) => {
              const left = Math.max(x(from), x(month.start))
              const next = months[index + 1]
              if (next && ((x(next.start) - left) / 100) * width < 44) return null
              // The break's own label needs the room at the end of the scale.
              if (breakPx > 0 && (left / 100) * width > EDGE + mainPx - 64) return null
              return (
                <span
                  key={`${month.year}-${month.start}`}
                  className="absolute top-2 pl-1.5 text-xs font-bold whitespace-nowrap text-navy-500"
                  style={{ left: `${left}%` }}
                >
                  {month.label.replace('.', '')}
                  {(index === 0 || month.label.startsWith('sty')) && (
                    <span className="ml-1 font-normal">{month.year}</span>
                  )}
                </span>
              )
            })}
            {months.map((month) =>
              month.start > from ? (
                <span
                  key={`m-${month.start}`}
                  className="absolute bottom-0 h-4 w-px bg-navy-200"
                  style={{ left: `${x(month.start)}%` }}
                />
              ) : null,
            )}
            {ticks.map((tick) => (
              <span
                key={tick.day}
                className={cn(
                  'absolute bottom-0 w-px',
                  tick.size === 'week' ? 'h-2 bg-navy-200' : 'h-1 bg-navy-100',
                )}
                style={{ left: `${x(tick.day)}%` }}
              />
            ))}
            {breakPx > 0 && (
              <span
                className="absolute top-2 flex justify-center text-xs font-bold whitespace-nowrap text-navy-400"
                style={{ left: `${x(to)}%`, width: BREAK_GAP }}
                title="Przerwa w skali"
              >
                ⋯ {breakYears >= 1 ? `${breakYears} ${breakYears === 1 ? 'rok' : breakYears < 5 ? 'lata' : 'lat'}` : 'później'} ⋯
              </span>
            )}
            {head !== today && (
              <span
                className="absolute bottom-1.5 -translate-x-1/2 text-[10px] font-bold text-navy-400"
                style={{ left: `${x(today)}%` }}
              >
                dziś
              </span>
            )}
          </div>

          {/* Under the clips: month lines, today and the break in the scale. */}
          <div
            className="pointer-events-none relative"
            style={{ gridColumn: 2, gridRow: `2 / span ${rowsBelowRuler}` }}
          >
            {months.map((month) =>
              month.start > from ? (
                <span
                  key={month.start}
                  className="absolute inset-y-0 w-px bg-line/60"
                  style={{ left: `${x(month.start)}%` }}
                />
              ) : null,
            )}
            <span className="absolute inset-y-0 w-px bg-navy-200" style={{ left: `${x(today)}%` }} />
            {breakPx > 0 && (
              <span
                className="absolute inset-y-0 border-x border-dashed border-navy-200 bg-[repeating-linear-gradient(135deg,transparent_0_7px,var(--color-navy-50)_7px_14px)]"
                style={{ left: `${x(to)}%`, width: BREAK_GAP }}
              />
            )}
          </div>

          {/* Over the clips: the birth and the playhead. */}
          <div
            className="pointer-events-none relative z-20"
            style={{ gridColumn: 2, gridRow: `1 / span ${rowsBelowRuler + 1}` }}
          >
            <span
              className="absolute bottom-0 w-0 -translate-x-1/2 border-l-2 border-dashed border-sun-400"
              style={{ left: `${x(birth)}%`, top: RULER_HEIGHT }}
            />
            <motion.div
              className="absolute inset-y-0 z-30 w-0"
              initial={false}
              animate={{ left: `${x(head)}%` }}
              transition={scrubbing || reduceMotion ? { duration: 0 } : SPRING_LAYOUT}
            >
              <span className="absolute top-[30px] bottom-0 left-0 w-0.5 -translate-x-1/2 bg-navy-900" />
              <span
                onPointerDown={startScrub}
                onPointerMove={moveScrub}
                onPointerUp={endScrub}
                onPointerCancel={endScrub}
                className={cn(
                  'pointer-events-auto absolute top-1 left-0 cursor-ew-resize rounded-full bg-navy-900 px-2.5 py-1 text-xs font-bold whitespace-nowrap text-white shadow-[0_6px_14px_-6px_rgb(26_36_56/0.6)] transition-transform duration-150',
                  headSide === 'start' && '-translate-x-2',
                  headSide === 'middle' && '-translate-x-1/2',
                  headSide === 'end' && '-translate-x-[calc(100%-8px)]',
                  scrubbing && 'scale-105',
                )}
              >
                {head === today ? 'Dziś · ' : ''}
                {head > to ? formatShortDate(isoFromDay(head)) : formatDayMonthShort(isoFromDay(head))}
              </span>
            </motion.div>
          </div>

          {lanes.map((lane, laneIndex) => {
            const placed = placeFlags(flags[lane], x, width, chipWidths)
            const rows = Math.max(1, placed.reduce((n, f) => Math.max(n, f.row + 1), 0))
            const sorted = sortedIn(lane)
            const laneWindows = windows.filter((w) => w.segment.lane === lane)
            // Rows stacked one under another, centred in the track; a chip is centred in its row.
            const stack = rows * FLAG_ROW - FLAG_GAP
            const trackHeight = Math.max(ROW_HEIGHT + (laneWindows.length > 0 ? WINDOW_BAND : 0), stack + 2 * TRACK_PAD)
            const firstRow = (trackHeight - stack) / 2
            const flagTop = (row: number, key: boolean) =>
              firstRow +
              row * FLAG_ROW +
              (FLAG_EVENT_HEIGHT - (key ? FLAG_EVENT_HEIGHT : FLAG_HINT_HEIGHT)) / 2

            // Pieces of one period end to end (sick leave: the employer's days, then ZUS's) are
            // one unit for the label.
            const units: Unit[] = []
            for (const s of sorted) {
              const last = units.at(-1)
              const previous = last?.members.at(-1)
              const kind = family(s)?.kind
              if (last && previous && kind && joins(previous, s) && family(previous)?.kind === kind) {
                last.members.push(s)
                last.end = dayNumber(s.end) + 1
              } else units.push({ members: [s], start: dayNumber(s.start), end: dayNumber(s.end) + 1 })
            }
            // Labels beside clips take the room in order, so two never claim the same gap.
            let taken = EDGE
            const clipLabels = new Map<string, ClipLabel>()
            const runLabels: { unit: Unit; label: ClipLabel }[] = []
            const unitLabels = units.map((unit, index) => {
              const start = xPx(unit.start)
              const end = xPx(unit.end)
              const after = index < units.length - 1 ? xPx(units[index + 1].start) : EDGE + mainPx
              const first = unit.members[0]
              const option = first.tone === 'option'
              const dates = (s: Segment) => `${formatDayMonthShort(s.start)} – ${formatDayMonthShort(s.end)}`
              let label: ClipLabel
              if (unit.members.length === 1) {
                label = labelClip(clipNames(first), first.days, option, end - start, start - taken, after - end, fit, dates(first))
                clipLabels.set(first.id, label)
              } else {
                // Each piece by its own name when every one fits; else the period once, over all.
                const pieces = unit.members.map((s) =>
                  labelClip([family(s)?.part ?? shortName(s)], s.days, option, xPx(dayNumber(s.end) + 1) - xPx(dayNumber(s.start)), 0, 0, fit, null),
                )
                if (pieces.every((p) => p.named)) {
                  unit.members.forEach((s, i) => clipLabels.set(s.id, pieces[i]))
                  label = NO_LABEL
                } else {
                  const days = unit.members.reduce((sum, s) => sum + s.days, 0)
                  label = labelClip(runNames(first), days, option, end - start, start - taken, after - end, fit, null)
                  for (const s of unit.members) clipLabels.set(s.id, NO_LABEL)
                  runLabels.push({ unit, label: { ...label, icon: false, dates: false } })
                }
              }
              taken = label.outside?.side === 'right' ? end + label.outside.width : end
              return label
            })
            return (
              <Fragment key={lane}>
                <div
                  className="sticky left-0 z-30 flex items-center gap-2 border-b border-line bg-white pr-3"
                  style={{ gridColumn: 1, gridRow: laneIndex + 2 }}
                >
                  <Illustration src={LANES[lane].image} size="lane" />
                  <span className="text-sm font-bold text-navy-900">{LANES[lane].label}</span>
                </div>
                <div
                  className="relative border-b border-line transition-[height] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none"
                  style={{ gridColumn: 2, gridRow: laneIndex + 2, height: rem(trackHeight) }}
                >
                  {placed.map((flag) => (
                    <FlagChip
                      key={flag.id}
                      measureRef={measureChip}
                      flag={flag}
                      x={x(flag.day)}
                      top={flagTop(flag.row, flag.key)}
                      selected={selectedId === flag.id}
                      hovered={hoveredId === flag.id}
                      changed={changedIds.has(flag.id)}
                      changeVersion={changeVersion}
                      onClick={() => onSelect(flag.id)}
                      onHover={(on) => onHover(on ? flag.id : null)}
                    />
                  ))}

                  {/* The window a period can be taken in: a thin bracket under its clip, from the
                      first day it can start to the last day it can be taken. */}
                  {laneWindows.map(({ segment, deadline }) => {
                    const left = x(dayNumber(segment.start))
                    const right = x(dayNumber(deadline.date) + 1)
                    const px = ((right - left) / 100) * width
                    const until = `do ${formatShortDate(deadline.date)}`
                    const text = [`${tinyName(segment.id, shortName(segment))}: w dowolnym czasie ${until}`, `w dowolnym czasie ${until}`, until].find(
                      (t) => fit.xs(t) + 40 <= px,
                    )
                    const on = selectedId === segment.id || hoveredId === segment.id
                    const father = segment.lane === 'father'
                    return (
                      <button
                        key={`window-${segment.id}`}
                        type="button"
                        onClick={() => onSelect(segment.id)}
                        onMouseEnter={hoverWith(segment.id, periodName(segment), () => [
                          `${length(segment.days)} do wyboru: w dowolnym czasie ${until}`,
                          'Na osi stoi od pierwszego możliwego dnia.',
                        ])}
                        onMouseLeave={() => hoverWith(segment.id, '', () => [])(null)}
                        aria-label={`${periodName(segment)}: w dowolnym czasie ${until}`}
                        className="group absolute flex items-center justify-end focus-visible:outline-none"
                        style={{ top: rem(CLIP_TOP + CLIP_HEIGHT + 3), height: rem(WINDOW_BAND - 2), left: `${left}%`, width: `${right - left}%` }}
                      >
                        <span
                          aria-hidden
                          className={cn(
                            'absolute inset-x-0 top-1/2 -translate-y-1/2 border-t-2 border-dashed transition-colors duration-150',
                            father ? 'border-navy-300' : 'border-zus-300',
                            on && (father ? 'border-navy-700' : 'border-zus-700'),
                          )}
                        />
                        {(['left-0', 'right-0'] as const).map((edge) => (
                          <span
                            key={edge}
                            aria-hidden
                            className={cn(
                              'absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded-full transition-colors duration-150',
                              edge,
                              father ? 'bg-navy-300' : 'bg-zus-300',
                              on && (father ? 'bg-navy-700' : 'bg-zus-700'),
                            )}
                          />
                        ))}
                        {text && (
                          <span
                            className={cn(
                              'relative mr-3 rounded-full bg-white px-2 text-xs leading-5 font-bold whitespace-nowrap transition-colors duration-150 group-focus-visible:ring-2 group-focus-visible:ring-zus-400',
                              father ? 'text-navy-500' : 'text-zus-700',
                              on && 'text-navy-900',
                            )}
                          >
                            {text}
                          </span>
                        )}
                      </button>
                    )
                  })}

                  {sorted.length > 0 && (
                    <>
                      <AnimatePresence>
                        {shadow?.segments.filter((s) => s.lane === lane).map((s) => (
                          <motion.span
                            key={`${shadow.key}-${s.id}`}
                            initial={{ opacity: 0.8 }}
                            animate={{ opacity: 0 }}
                            transition={{ duration: 2.4, delay: 0.8, ease: 'easeIn' }}
                            className="absolute rounded-xl border-2 border-dashed border-navy-300"
                            style={{
                              top: rem(CLIP_TOP),
                              height: rem(CLIP_HEIGHT),
                              left: `${x(dayNumber(s.start))}%`,
                              width: `${x(dayNumber(s.end) + 1) - x(dayNumber(s.start))}%`,
                            }}
                          />
                        ))}
                      </AnimatePresence>
                      <AnimatePresence initial>
                        {sorted.map((s, index) => (
                          <Clip
                            key={s.id}
                            segment={s}
                            left={x(dayNumber(s.start))}
                            span={x(dayNumber(s.end) + 1) - x(dayNumber(s.start))}
                            label={clipLabels.get(s.id) ?? NO_LABEL}
                            index={index}
                            joinLeft={joins(sorted[index - 1], s)}
                            joinRight={joins(s, sorted[index + 1])}
                            inRun={units.some((u) => u.members.length > 1 && u.members.indexOf(s) > 0)}
                            changed={changedIds.has(s.id)}
                            changeVersion={changeVersion}
                            selected={selectedId === s.id}
                            hovered={hoveredId === s.id}
                            onClick={() => onSelect(s.id)}
                            onHover={hoverWith(s.id, periodName(s), segmentTip(s))}
                          />
                        ))}
                      </AnimatePresence>
                      {/* A run of pieces named once, over all of them (the pieces stay clickable). */}
                      {runLabels.map(({ unit, label }) =>
                        label.inside ? (
                          <motion.span
                            key={`run-${unit.members[0].id}`}
                            aria-hidden
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.3, delay: 0.6 }}
                            className={cn(
                              'pointer-events-none absolute z-11 flex items-center justify-center px-3 text-center',
                              RUN_TEXT[parentOf(unit.members[0])][unit.members[0].tone],
                            )}
                            style={{
                              top: rem(CLIP_TOP),
                              height: rem(CLIP_HEIGHT),
                              left: `${x(unit.start)}%`,
                              width: `${x(unit.end) - x(unit.start)}%`,
                            }}
                          >
                            <InsideText lines={label.inside} />
                          </motion.span>
                        ) : null,
                      )}
                      {units.map((unit, index) => {
                        const outside = unitLabels[index].outside
                        if (!outside) return null
                        const s = unit.members[0]
                        const edge = outside.side === 'right' ? x(unit.end) : x(unit.start)
                        const on = unit.members.some((m) => m.id === selectedId || m.id === hoveredId)
                        return (
                          <button
                            key={`label-${s.id}`}
                            type="button"
                            onClick={() => onSelect(s.id)}
                            onMouseEnter={hoverWith(s.id, periodName(s), segmentTip(s))}
                            onMouseLeave={() => hoverWith(s.id, '', () => [])(null)}
                            className={cn(
                              'absolute flex items-center text-sm font-bold whitespace-nowrap underline-offset-4 transition-colors duration-150',
                              outside.side === 'right' ? 'pl-2.5' : '-translate-x-full pr-2.5',
                              s.lane === 'father' ? 'text-navy-700 hover:text-navy-900' : 'text-zus-700 hover:text-zus-900',
                              on && 'underline decoration-2',
                            )}
                            style={{ top: rem(CLIP_TOP), height: rem(CLIP_HEIGHT), left: `${edge}%` }}
                          >
                            {outside.text}
                          </button>
                        )
                      })}
                    </>
                  )}
                </div>
              </Fragment>
            )
          })}

          {payments.length > 0 && (
            <>
              <div
                className="sticky left-0 z-30 flex items-center gap-2 border-b border-line bg-white pr-3"
                style={{ gridColumn: 1, gridRow: lanes.length + 2 }}
              >
                <Illustration src={pieniadze} size="lane" />
                <span className="text-sm font-bold text-navy-900">Pieniądze</span>
              </div>
              <div
                className="relative border-b border-line"
                style={{ gridColumn: 2, gridRow: lanes.length + 2, height: ROW_HEIGHT }}
              >
                {moneyUnits.map(({ members, row, inside, outside }) => {
                  const top = moneyTop(row)
                  const unitStart = x(dayNumber(members[0].start))
                  const unitEnd = x(dayNumber(members[members.length - 1].end) + 1)
                  const father = members[0].lane === 'father'
                  const on = members.some((m) => m.id === selectedId || m.id === hoveredId)
                  return (
                    <Fragment key={members[0].id}>
                      {members.map((payment, index) => {
                        const left = x(dayNumber(payment.start))
                        const span = x(dayNumber(payment.end) + 1) - left
                        const option = timeline.segments.find((s) => s.id === payment.segment_id)?.tone === 'option'
                        return (
                          <MoneyClip
                            key={payment.id}
                            payment={payment}
                            option={option}
                            text={members.length === 1 ? inside : null}
                            left={left}
                            span={span}
                            top={top}
                            joinLeft={index > 0}
                            joinRight={index < members.length - 1}
                            selected={selectedId === payment.id}
                            hovered={hoveredId === payment.id}
                            changed={changedIds.has(payment.id)}
                            changeVersion={changeVersion}
                            onClick={() => onSelect(payment.id)}
                            onHover={hoverWith(payment.id, payment.title, paymentTip(payment))}
                          />
                        )
                      })}
                      {members.length > 1 && inside && (
                        <span
                          aria-hidden
                          className={cn(
                            'pointer-events-none absolute z-11 flex items-center px-2 text-xs font-bold whitespace-nowrap tabular-nums',
                            father ? 'text-navy-900' : 'text-zus-900',
                          )}
                          style={{ top, height: MONEY_CLIP, left: `${unitStart}%`, width: `${unitEnd - unitStart}%` }}
                        >
                          {inside}
                        </span>
                      )}
                      {outside && (
                        <button
                          type="button"
                          onClick={() => onSelect(members[0].id)}
                          onMouseEnter={hoverWith(members[0].id, members[0].title, paymentTip(members[0]))}
                          onMouseLeave={() => hoverWith(members[0].id, '', () => [])(null)}
                          className={cn(
                            'absolute flex items-center text-xs font-bold whitespace-nowrap tabular-nums underline-offset-4 transition-colors duration-150',
                            outside.side === 'right' ? 'pl-2.5' : '-translate-x-full pr-2.5',
                            father ? 'text-navy-700 hover:text-navy-900' : 'text-zus-700 hover:text-zus-900',
                            on && 'underline decoration-2',
                          )}
                          style={{ top, height: MONEY_CLIP, left: `${outside.side === 'right' ? unitEnd : unitStart}%` }}
                        >
                          {outside.text}
                        </button>
                      )}
                    </Fragment>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {tip &&
        createPortal(
          <motion.div
            role="tooltip"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.12 }}
            className="pointer-events-none fixed z-[70] w-max max-w-72 rounded-2xl bg-navy-900 px-3.5 py-2.5 text-white shadow-[0_12px_28px_-12px_rgb(26_36_56/0.6)]"
            style={{
              left: Math.min(Math.max(tip.x, 150), window.innerWidth - 150),
              top: tip.top < 120 ? tip.bottom + 10 : tip.top - 10,
              transform: `translate(-50%, ${tip.top < 120 ? '0' : '-100%'})`,
            }}
          >
            <p className="text-sm leading-snug font-bold">{tip.title}</p>
            {tip.lines.map((line) => (
              <p key={line} className="mt-0.5 text-xs leading-snug text-white/80 tabular-nums">
                {line}
              </p>
            ))}
          </motion.div>,
          document.body,
        )}

    </div>
  )
}

function ToolButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="grid h-9 min-w-9 place-items-center rounded-full px-2 text-navy-500 transition-[background-color,color,opacity,transform] duration-150 hover:bg-navy-50 hover:text-navy-900 active:scale-[0.94] disabled:pointer-events-none disabled:opacity-30 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}

/** The outline of the element whose details are open, and of the one under the pointer. The
 *  white offset keeps it visible on any colour, and lifts the element over its neighbours. */
const SELECTED = 'z-10 ring-2 ring-navy-900 ring-offset-2'
const HOVERED = 'z-10 ring-2 ring-navy-900/30 ring-offset-2'

function FlagChip({
  flag,
  x,
  top,
  selected,
  hovered,
  changed,
  changeVersion,
  onClick,
  onHover,
  measureRef,
}: {
  flag: PlacedFlag
  x: number
  top: number
  selected: boolean
  hovered: boolean
  changed: boolean
  changeVersion: number
  onClick: () => void
  onHover: (on: boolean) => void
  measureRef: (element: HTMLElement | null) => void
}) {
  const document = flag.kind === 'document'
  return (
    <motion.button
      ref={measureRef}
      data-flag={flag.id}
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      aria-pressed={selected}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.5 }}
      className={cn(
        'absolute z-20 flex items-center rounded-full border whitespace-nowrap',
        // A flag that moves to another row (after a recalculation or zoom) slides there.
        'transition-[top,border-color,background-color,box-shadow] duration-200 motion-reduce:transition-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        flag.side === 'left' ? '-translate-x-full' : '-translate-x-1.5',
        flag.key
          ? 'h-10 gap-2 border-sun-300 bg-sun-100/70 pr-4 pl-0.5 text-sm font-bold text-navy-900'
          : 'h-7.5 gap-1.5 border-line bg-white pr-3 pl-1 text-xs font-bold text-navy-700',
        document && flag.done && 'border-zus-200 text-zus-700',
        (hovered || selected) && (flag.key ? 'border-sun-400 bg-sun-100' : 'border-navy-300 bg-navy-50'),
        hovered && !selected && 'z-30 ring-2 ring-navy-900/25 ring-offset-2',
        selected && 'z-30 ring-2 ring-navy-900 ring-offset-2',
      )}
      style={{ top: rem(top), left: `${x}%` }}
    >
      {changed && <Pulse key={changeVersion} />}
      <Illustration src={flag.icon} size={flag.key ? 'event' : 'hint'} className={flag.key ? 'bg-white' : ''} />
      {flag.text}
      {flag.locked && (
        <Lock className="size-3.5 text-sun-700" strokeWidth={2.5} aria-label="bez powrotu" />
      )}
      {document && flag.done && <Check className="size-3.5" strokeWidth={3} />}
    </motion.button>
  )
}

/** A label inside a clip: one line, or the name over the length. */
function InsideText({ lines }: { lines: string[] }) {
  return (
    <span className="relative flex min-w-0 flex-col leading-tight">
      <span className="text-sm font-bold whitespace-nowrap">{lines[0]}</span>
      {lines[1] && <span className="text-xs font-bold whitespace-nowrap opacity-80">{lines[1]}</span>}
    </span>
  )
}

/** The text colour of a run's label, as on its clips. */
const RUN_TEXT: Record<'mother' | 'father', Record<Segment['tone'], string>> = {
  mother: { leave: 'text-white', option: 'text-zus-900', work: 'text-navy-700' },
  father: { leave: 'text-white', option: 'text-navy-900', work: 'text-navy-700' },
}

function Clip({
  segment,
  left,
  span,
  label,
  index,
  joinLeft,
  joinRight,
  inRun,
  changed,
  changeVersion,
  selected,
  hovered,
  onClick,
  onHover,
}: {
  segment: Segment
  left: number
  span: number
  label: ClipLabel
  index: number
  joinLeft: boolean
  joinRight: boolean
  /** A later piece of one period (named once over all its pieces): a faint seam. */
  inRun: boolean
  changed: boolean
  changeVersion: number
  selected: boolean
  hovered: boolean
  onClick: () => void
  onHover: (event: MouseEvent<HTMLElement> | null) => void
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      onMouseEnter={(event) => onHover(event)}
      onMouseLeave={() => onHover(null)}
      aria-label={`${segment.title}, ${length(segment.days)}`}
      aria-pressed={selected}
      initial={{ opacity: 0, clipPath: 'inset(0% 100% 0% 0%)' }}
      animate={{ opacity: 1, clipPath: 'inset(0% 0% 0% 0%)' }}
      exit={{ opacity: 0 }}
      transition={{
        clipPath: { duration: 0.7, delay: 0.15 + index * 0.12, ease: [0.77, 0, 0.175, 1] },
        opacity: { duration: 0.2, delay: 0.15 + index * 0.12 },
      }}
      className={cn(
        'absolute flex items-center gap-2 overflow-hidden rounded-xl px-3 text-left whitespace-nowrap',
        // A recalculated plan glides into place (rare, so animating left/width is fine here).
        'transition-[left,width,filter,box-shadow] duration-[500ms,500ms,150ms,150ms] ease-[cubic-bezier(0.23,1,0.32,1)]',
        'outline-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2',
        CLIP[parentOf(segment)][segment.tone],
        joinLeft && 'rounded-l-none border-l-0',
        joinRight && 'rounded-r-none',
        hovered && !selected && cn(HOVERED, 'brightness-[0.97]'),
        selected && SELECTED,
      )}
      style={{ top: rem(CLIP_TOP), height: rem(CLIP_HEIGHT), left: `${left}%`, width: `${span}%` }}
    >
      {/* The seam between two pieces joined end to end. */}
      {joinLeft && segment.tone !== 'option' && (
        <span aria-hidden className={cn('absolute inset-y-0 left-0 w-0.5', inRun ? 'bg-white/25' : 'bg-white/70')} />
      )}
      {changed && <Pulse key={changeVersion} className="rounded-[inherit] ring-inset" />}
      {label.icon && <Illustration src={segmentIcon(segment)} size="event" className="relative -ml-1.5" />}
      {label.inside && (
        <span className={cn('relative flex', !label.icon && !label.dates && 'mx-auto text-center')}>
          <InsideText lines={label.inside} />
        </span>
      )}
      {label.dates && (
        <span className="relative ml-auto text-xs font-bold whitespace-nowrap opacity-70">
          {formatDayMonthShort(segment.start)} – {formatDayMonthShort(segment.end)}
        </span>
      )}
    </motion.button>
  )
}

/** What is paid for a period, on the money track: green the mother's, navy the father's;
 *  dashed while the period is still to decide. Pieces paid the same, end to end, are joined. */
function MoneyClip({
  payment,
  option,
  text,
  left,
  span,
  top,
  joinLeft,
  joinRight,
  selected,
  hovered,
  changed,
  changeVersion,
  onClick,
  onHover,
}: {
  payment: Payment
  option: boolean
  /** The amount inside, when it fits and is not said over a run of pieces. */
  text: string | null
  left: number
  span: number
  top: number
  joinLeft: boolean
  joinRight: boolean
  selected: boolean
  hovered: boolean
  changed: boolean
  changeVersion: number
  onClick: () => void
  onHover: (event: MouseEvent<HTMLElement> | null) => void
}) {
  const father = payment.lane === 'father'
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={(event) => onHover(event)}
      onMouseLeave={() => onHover(null)}
      aria-label={`${payment.title}: ${formatPlnShort(payment.monthly)} miesięcznie, ${formatRate(payment.rate)}`}
      aria-pressed={selected}
      className={cn(
        'absolute flex items-center overflow-hidden rounded-lg border px-2 text-xs font-bold whitespace-nowrap tabular-nums',
        'transition-[left,width,box-shadow,background-color] duration-[500ms,500ms,150ms,150ms] ease-[cubic-bezier(0.23,1,0.32,1)]',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        father
          ? option
            ? 'border-dashed border-navy-300 bg-navy-50/70 text-navy-700'
            : 'border-navy-200 bg-navy-100 text-navy-900'
          : option
            ? 'border-dashed border-zus-300 bg-zus-50/70 text-zus-700'
            : 'border-zus-200 bg-zus-100 text-zus-900',
        joinLeft && 'rounded-l-none',
        joinRight && 'rounded-r-none border-r-0',
        hovered && !selected && 'z-10 ring-2 ring-navy-900/30 ring-offset-1',
        selected && 'z-10 ring-2 ring-navy-900 ring-offset-1',
      )}
      style={{ top, height: MONEY_CLIP, left: `${left}%`, width: `${span}%` }}
    >
      {changed && <Pulse key={changeVersion} className="rounded-[inherit] ring-inset" />}
      {text && <span className="relative">{text}</span>}
    </button>
  )
}
