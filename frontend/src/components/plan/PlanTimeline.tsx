// The plan's timeline, built like a video editor's: a ruler with months and week ticks, tracks
// (Dziecko, Mama, Tata, Dokumenty) with clips for leave and keyframes for important days, and a
// playhead. Drag the playhead along the ruler and the readout below says what happens on that
// day; ‹ › jump between events like keyframes. The tracks scroll sideways with momentum (drag
// them, or use the trackpad) and zoom on a spring (− / +, Ctrl/⌘ + wheel or pinch, anchored at
// the pointer). After a recalculation the old plan stays for a moment as a shadow (FUNKCJE F16).
//
// The scale is spent on the leave: deadlines years away (the end of parental leave in the year
// of the 6th birthday) sit behind a break in the scale, "⋯ 5 lat ⋯", so 20 weeks stay a clip you
// can read. A period still to decide is a light clip with its name beside it when it is too
// narrow; one that can be taken any time up to a deadline (paternity leave) shows that window.
//
// Motion follows Emil Kowalski's rules: springs for anything interruptible, no animation on what
// repeats constantly (scrubbing follows the pointer 1:1), reduced motion respected.
import { Fragment, useCallback, useEffect, useEffectEvent, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent, ReactNode } from 'react'
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
import { Illustration } from '@/components/ui/illustration'
import { documentIcon, isKeyMarker, markerIcon, segmentIcon } from '@/lib/icons'
import { formatPlnShort, formatRate } from '@/lib/money'
import { clipName, length, optionWindow } from '@/lib/plan'
import { LANE_ORDER } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Lane, Payment, Segment, Timeline } from '@/types'
import { Readout } from './Readout'

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
/** Heights in the tracks follow the text size ("Większy tekst" scales rem), like the chips. */
const rem = (px: number) => `${px / 16}rem`
const MIN_ZOOM = 1
const MAX_ZOOM = 8
const ZOOM_STEP = 1.6
const ZOOM_SPRING = { type: 'spring', stiffness: 260, damping: 32, mass: 0.6 } as const
/** Momentum after a drag: share of the velocity kept per millisecond. */
const GLIDE_DECAY = 0.995
/** Rough width of bold 14 px text, per character, for fitting labels. */
const CHAR_PX = 7.4

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

/** The window a period can be taken in: lighter than the clip, so the clip stays the answer. */
const WINDOW: Record<'mother' | 'father', string> = {
  mother: 'border border-dashed border-zus-200 bg-zus-50/60 text-zus-700',
  father: 'border border-dashed border-navy-200 bg-navy-50/60 text-navy-500',
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

/** How a clip is labelled: inside if it fits, else beside it, else just its length. */
interface ClipLabel {
  inside: string | null
  icon: boolean
  dates: boolean
  outside: { text: string; side: 'right' | 'left'; width: number } | null
}

const textPx = (text: string) => text.length * CHAR_PX + 28

function labelClip(segment: Segment, px: number, roomBefore: number, roomAfter: number): ClipLabel {
  const weeks = length(segment.days)
  const name = clipName(segment)
  const short = name.replace(/\s+(po porodzie|przed porodem)$/, '')
  const option = segment.tone === 'option'
  const candidates = [
    ...(option ? [`${name} · ${weeks} · do wyboru`] : []),
    `${name} · ${weeks}`,
    `${short} · ${weeks}`,
  ]
  const inside = candidates.find((text) => px >= textPx(text)) ?? null
  if (inside) {
    const icon = px >= textPx(inside) + 40
    return { inside, icon, dates: icon && px >= textPx(inside) + 160, outside: null }
  }
  const text = `${name} · ${weeks}${option ? ' · do wyboru' : ''}`
  const needed = text.length * CHAR_PX + 24
  const side = roomAfter >= needed ? 'right' : roomBefore >= needed ? 'left' : null
  return {
    inside: side ? null : px >= 40 ? weeks : null,
    icon: false,
    dates: false,
    outside: side ? { text, side, width: needed } : null,
  }
}

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

  // A change of the plan puts the playhead on what changed, so the readout says what it is; the
  // axis scrolls to it when zoomed in. An axis that opens later does not jump to an old change.
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
            // Rows stacked one under another, centred in the track; a chip is centred in its row.
            const stack = rows * FLAG_ROW - FLAG_GAP
            const trackHeight = Math.max(ROW_HEIGHT, stack + 2 * TRACK_PAD)
            const firstRow = (trackHeight - stack) / 2
            const flagTop = (row: number, key: boolean) =>
              firstRow +
              row * FLAG_ROW +
              (FLAG_EVENT_HEIGHT - (key ? FLAG_EVENT_HEIGHT : FLAG_HINT_HEIGHT)) / 2
            // Labels beside clips take the room in order, so two never claim the same gap.
            let taken = EDGE
            const labels = sorted.map((s, index) => {
              const start = xPx(dayNumber(s.start))
              const end = xPx(dayNumber(s.end) + 1)
              const after = index < sorted.length - 1 ? xPx(dayNumber(sorted[index + 1].start)) : EDGE + mainPx
              const label = labelClip(s, end - start, start - taken, after - end)
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
                      active={selectedId === flag.id || hoveredId === flag.id}
                      onClick={() => onSelect(flag.id)}
                      onHover={(on) => onHover(on ? flag.id : null)}
                    />
                  ))}

                  {/* The window a period can be taken in, under its clip. */}
                  {windows
                    .filter((w) => w.segment.lane === lane)
                    .map(({ segment, deadline }) => {
                      const left = x(dayNumber(segment.start))
                      const right = x(dayNumber(deadline.date) + 1)
                      const px = ((right - left) / 100) * width
                      // The words sit at the window's end; another period there (the father's
                      // parental leave inside his paternity window) would run over them.
                      const end = dayNumber(deadline.date)
                      const covered = timeline.segments.some(
                        (o) =>
                          o.lane === lane &&
                          o.id !== segment.id &&
                          dayNumber(o.start) <= end &&
                          dayNumber(o.end) >= end - 220 / pxPerDay,
                      )
                      return (
                        <button
                          key={`window-${segment.id}`}
                          type="button"
                          onClick={() => onSelect(segment.id)}
                          onMouseEnter={() => onHover(segment.id)}
                          onMouseLeave={() => onHover(null)}
                          aria-label={`Okno: ${clipName(segment)} do ${formatShortDate(deadline.date)}`}
                          className={cn(
                            'absolute flex items-center justify-end rounded-xl pr-3 text-xs font-bold whitespace-nowrap',
                            WINDOW[parentOf(segment)],
                          )}
                          style={{ top: rem(CLIP_TOP), height: rem(CLIP_HEIGHT), left: `${left}%`, width: `${right - left}%` }}
                        >
                          {px > 420 && !covered && <>w dowolnym czasie do {formatShortDate(deadline.date)}</>}
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
                            label={labels[index]}
                            index={index}
                            joinLeft={joins(sorted[index - 1], s)}
                            joinRight={joins(s, sorted[index + 1])}
                            changed={changedIds.has(s.id)}
                            changeVersion={changeVersion}
                            active={selectedId === s.id || hoveredId === s.id}
                            onClick={() => onSelect(s.id)}
                            onHover={(on) => onHover(on ? s.id : null)}
                          />
                        ))}
                      </AnimatePresence>
                      {sorted.map((s, index) => {
                        const outside = labels[index].outside
                        if (!outside) return null
                        const edge = outside.side === 'right' ? x(dayNumber(s.end) + 1) : x(dayNumber(s.start))
                        return (
                          <button
                            key={`label-${s.id}`}
                            type="button"
                            onClick={() => onSelect(s.id)}
                            onMouseEnter={() => onHover(s.id)}
                            onMouseLeave={() => onHover(null)}
                            className={cn(
                              'absolute flex items-center text-sm font-bold whitespace-nowrap transition-colors duration-150',
                              outside.side === 'right' ? 'pl-2.5' : '-translate-x-full pr-2.5',
                              s.lane === 'father' ? 'text-navy-700 hover:text-navy-900' : 'text-zus-700 hover:text-zus-900',
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
                {payments.map((payment) => {
                  const left = x(dayNumber(payment.start))
                  const span = x(dayNumber(payment.end) + 1) - left
                  const row = moneyLanes.indexOf(payment.lane)
                  const top =
                    moneyLanes.length === 1
                      ? (ROW_HEIGHT - MONEY_CLIP) / 2
                      : (ROW_HEIGHT - 2 * MONEY_CLIP - 4) / 2 + row * (MONEY_CLIP + 4)
                  const option = timeline.segments.find((s) => s.id === payment.segment_id)?.tone === 'option'
                  return (
                    <MoneyClip
                      key={payment.id}
                      payment={payment}
                      option={option}
                      left={left}
                      span={span}
                      px={(span / 100) * width}
                      top={top}
                      active={selectedId === payment.id || hoveredId === payment.id}
                      onClick={() => onSelect(payment.id)}
                      onHover={(on) => onHover(on ? payment.id : null)}
                    />
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      <Readout timeline={timeline} day={head} onSelect={onSelect} onHover={onHover} />
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

function FlagChip({
  flag,
  x,
  top,
  active,
  onClick,
  onHover,
  measureRef,
}: {
  flag: PlacedFlag
  x: number
  top: number
  active: boolean
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
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.5 }}
      className={cn(
        'absolute z-20 flex items-center rounded-full border whitespace-nowrap',
        // A flag that moves to another row (after a recalculation or zoom) slides there.
        'transition-[top,border-color,background-color] duration-200 motion-reduce:transition-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        flag.side === 'left' ? '-translate-x-full' : '-translate-x-[6px]',
        flag.key
          ? 'h-10 gap-2 border-sun-300 bg-sun-100/70 pr-4 pl-0.5 text-sm font-bold text-navy-900'
          : 'h-7.5 gap-1.5 border-line bg-white pr-3 pl-1 text-xs font-bold text-navy-700',
        document && flag.done && 'border-zus-200 text-zus-700',
        active && (flag.key ? 'bg-sun-100' : 'border-sun-300 bg-sun-100/60'),
      )}
      style={{ top: rem(top), left: `${x}%` }}
    >
      <Illustration src={flag.icon} size={flag.key ? 'event' : 'hint'} className={flag.key ? 'bg-white' : ''} />
      {flag.text}
      {flag.locked && (
        <Lock className="size-3.5 text-sun-700" strokeWidth={2.5} aria-label="bez powrotu" />
      )}
      {document && flag.done && <Check className="size-3.5" strokeWidth={3} />}
    </motion.button>
  )
}

function Clip({
  segment,
  left,
  span,
  label,
  index,
  joinLeft,
  joinRight,
  changed,
  changeVersion,
  active,
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
  changed: boolean
  changeVersion: number
  active: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      aria-label={`${segment.title}, ${length(segment.days)}`}
      title={segment.title}
      initial={{ opacity: 0, clipPath: 'inset(0% 100% 0% 0%)' }}
      animate={{ opacity: 1, clipPath: 'inset(0% 0% 0% 0%)' }}
      exit={{ opacity: 0 }}
      transition={{
        clipPath: { duration: 0.7, delay: 0.15 + index * 0.12, ease: [0.77, 0, 0.175, 1] },
        opacity: { duration: 0.2, delay: 0.15 + index * 0.12 },
      }}
      className={cn(
        'absolute flex items-center gap-2 overflow-hidden rounded-xl px-3 text-left leading-tight whitespace-nowrap',
        // A recalculated plan glides into place (rare, so animating left/width is fine here).
        'transition-[left,width,filter,box-shadow] duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]',
        'outline-none focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:ring-offset-2',
        CLIP[parentOf(segment)][segment.tone],
        joinLeft && 'rounded-l-none border-l-0',
        joinRight && 'rounded-r-none',
        active && 'ring-2 ring-navy-900/25 ring-offset-2 brightness-[0.96]',
      )}
      style={{ top: rem(CLIP_TOP), height: rem(CLIP_HEIGHT), left: `${left}%`, width: `${span}%` }}
    >
      {changed && (
        <motion.span
          key={changeVersion}
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 1.6, ease: 'easeOut' }}
          className="absolute inset-0 rounded-[inherit] ring-4 ring-sun-300 ring-inset"
        />
      )}
      {label.icon && <Illustration src={segmentIcon(segment)} size="event" className="relative -ml-1.5" />}
      {label.inside && (
        <span className={cn('relative truncate text-sm font-bold', !label.icon && !label.dates && 'mx-auto')}>
          {label.inside}
        </span>
      )}
      {label.dates && (
        <span className="relative ml-auto truncate text-xs font-bold opacity-70">
          {formatDayMonthShort(segment.start)} – {formatDayMonthShort(segment.end)}
        </span>
      )}
    </motion.button>
  )
}

/** What is paid for a period, on the money track: green the mother's, navy the father's;
 *  dashed while the period is still to decide. */
function MoneyClip({
  payment,
  option,
  left,
  span,
  px,
  top,
  active,
  onClick,
  onHover,
}: {
  payment: Payment
  option: boolean
  left: number
  span: number
  px: number
  top: number
  active: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  const father = payment.lane === 'father'
  const text =
    px >= 116 ? `${formatPlnShort(payment.monthly)} / mies.` : px >= 64 ? formatPlnShort(payment.monthly) : ''
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      aria-label={`${payment.title}: ${formatPlnShort(payment.monthly)} miesięcznie, ${formatRate(payment.rate)}`}
      title={`${payment.title} · ${formatRate(payment.rate)}`}
      className={cn(
        'absolute flex items-center overflow-hidden rounded-lg border px-2 text-xs font-bold whitespace-nowrap tabular-nums',
        'transition-[left,width,box-shadow,background-color] duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]',
        'focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
        father
          ? option
            ? 'border-dashed border-navy-300 bg-navy-50/70 text-navy-700'
            : 'border-navy-200 bg-navy-100 text-navy-900'
          : option
            ? 'border-dashed border-zus-300 bg-zus-50/70 text-zus-700'
            : 'border-zus-200 bg-zus-100 text-zus-900',
        active && 'ring-2 ring-navy-900/25 ring-offset-1',
      )}
      style={{ top, height: MONEY_CLIP, left: `${left}%`, width: `${span}%` }}
    >
      <span className="truncate">{text}</span>
    </button>
  )
}
