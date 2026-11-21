// The plan's timeline, built like a video editor's: a ruler with months and week ticks, tracks
// (Dziecko, Mama, Tata, Dokumenty, and Pieniądze once the engine has amounts) with clips
// for leave and keyframes for important days, and a playhead. Drag the playhead along the ruler
// and the readout below says what happens on that day; ‹ › jump between events like keyframes.
// The tracks scroll sideways with momentum (drag them, or use the trackpad) and zoom on a spring
// (− / +, Ctrl/⌘ + wheel or pinch, anchored at the pointer). After a recalculation the old plan
// stays for a moment as a shadow (FUNKCJE F16).
//
// Motion follows Emil Kowalski's rules: springs for anything interruptible, no animation on what
// repeats constantly (scrubbing follows the pointer 1:1), reduced motion respected.
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent, ReactNode } from 'react'
import { animate, AnimatePresence, motion, useReducedMotion } from 'motion/react'
import type { AnimationPlaybackControls } from 'motion/react'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
} from 'lucide-react'
import dziecko from '@/assets/onboarding/dziecko.webp'
import mama from '@/assets/onboarding/mama.webp'
import pieniadze from '@/assets/onboarding/pieniadze.webp'
import tata from '@/assets/onboarding/tata.webp'
import zaswiadczenie from '@/assets/onboarding/zaswiadczenie.webp'
import { dayNumber, formatDayMonthShort, formatDistance, isoFromDay, monthCells } from '@/lib/dates'
import { SPRING_LAYOUT } from '@/lib/ease'
import { Illustration } from '@/components/ui/illustration'
import { documentIcon, ICONS, isKeyMarker, markerIcon, segmentIcon } from '@/lib/icons'
import { formatPln, formatPlnShort, formatRate } from '@/lib/money'
import { LANE_ORDER, segmentLook } from '@/lib/ui'
import { cn } from '@/lib/utils'
import type { Lane, Payment, Segment, Timeline } from '@/types'

/** Days of margin before the first and after the last element. */
const PAD_DAYS = 14
const LABEL_WIDTH = 120
const RULER_HEIGHT = 44
/** Every track is the same height, like tracks in a video editor. */
const ROW_HEIGHT = 84
/** A row of flags; an event chip (40 px) and a hint chip (30 px) are centred in it. */
const FLAG_ROW = 40
const FLAG_EVENT_HEIGHT = 40
const FLAG_HINT_HEIGHT = 30
/** At most two rows of flags fit in a track. */
const MAX_FLAG_ROWS = 2
const CLIP_HEIGHT = 46
const CLIP_TOP = (ROW_HEIGHT - CLIP_HEIGHT) / 2
const MIN_ZOOM = 1
const MAX_ZOOM = 8
const ZOOM_STEP = 1.6
const ZOOM_SPRING = { type: 'spring', stiffness: 260, damping: 32, mass: 0.6 } as const
/** Example only, for the Tata preview track when the engine has no period of the father. */
const PREVIEW_PATERNITY_DAYS = 14
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

const clipClass = (segment: Segment) =>
  CLIP[segment.lane === 'father' ? 'father' : 'mother'][segment.tone]

const weekdayDate = new Intl.DateTimeFormat('pl-PL', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

interface Flag {
  id: string
  day: number
  text: string
  icon: string
  kind: 'marker' | 'document'
  done?: boolean
  /** An event (bigger, bold, amber) rather than a hint. */
  key: boolean
}

interface PlacedFlag extends Flag {
  row: number
  side: 'right' | 'left'
}

const flagWidth = (flag: Flag) => (flag.key ? flag.text.length * 7.6 + 64 : flag.text.length * 6.7 + 48)

/** Flags of one track in as few rows as possible, without overlapping. */
function placeFlags(flags: Flag[], x: (day: number) => number, width: number): PlacedFlag[] {
  const rowEnds: number[] = []
  return [...flags]
    .sort((a, b) => a.day - b.day)
    .map((flag) => {
      const w = flagWidth(flag)
      const px = (x(flag.day) / 100) * width
      const side = px + w > width ? 'left' : 'right'
      const start = side === 'right' ? px : px - w
      let row = rowEnds.findIndex((end) => start > end + 8)
      if (row === -1) {
        row =
          rowEnds.length < MAX_FLAG_ROWS ? rowEnds.length : rowEnds.indexOf(Math.min(...rowEnds))
      }
      rowEnds[row] = start + w
      return { ...flag, row, side }
    })
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
  /** Show the Tata track with example data until the engine computes the father's periods. */
  preview?: boolean
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
  preview = false,
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

  const today = dayNumber(timeline.today)
  const [playhead, setPlayhead] = useState(today)

  const width = Math.max(320, (viewport - LABEL_WIDTH) * zoom)

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
      const track = Math.max(320, (element.clientWidth - LABEL_WIDTH) * zoomRef.current)
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

  const birth = dayNumber(timeline.birth_date)
  const laneSegments = (lane: Lane) => timeline.segments.filter((s) => s.lane === lane)
  const hasFather = timeline.segments.some((s) => s.lane === 'father')
  const days = [
    today,
    birth,
    ...timeline.segments.flatMap((s) => [dayNumber(s.start), dayNumber(s.end) + 1]),
    ...timeline.markers.map((m) => dayNumber(m.date)),
    ...timeline.documents.map((d) => dayNumber(d.needed_by)),
  ]
  const from = Math.min(...days) - PAD_DAYS
  const to = Math.max(...days) + PAD_DAYS
  const x = (day: number) => ((day - from) / (to - from)) * 100
  const pxPerDay = width / (to - from)
  const head = Math.min(Math.max(playhead, from), to)
  const months = monthCells(from, to)

  // A zoomed-in axis (the expanded view) opens at today, not at the start.
  const startAtToday = useRef(initialZoom > 1)
  useLayoutEffect(() => {
    const element = scroller.current
    if (!element || !startAtToday.current || viewport === 0) return
    startAtToday.current = false
    const visible = element.clientWidth - LABEL_WIDTH
    element.scrollLeft = Math.max(0, (x(today) / 100) * width - visible * 0.15)
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
    const position = LABEL_WIDTH + (x(day) / 100) * width
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

  const dayAt = (clientX: number) => {
    const element = scroller.current
    if (!element) return head
    const content = clientX - element.getBoundingClientRect().left + element.scrollLeft - LABEL_WIDTH
    return Math.min(to, Math.max(from, Math.round(from + (content / width) * (to - from))))
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
    let last = performance.now()
    const step = (now: number) => {
      const dt = now - last
      last = now
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
    flags[m.lane === 'documents' ? 'documents' : 'child'].push({
      id: m.id,
      day: dayNumber(m.date),
      text: `${m.label} · ${formatDayMonthShort(m.date)}`,
      icon: markerIcon(m),
      kind: 'marker',
      key: isKeyMarker(m),
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
  // The Tata example only stands in while the engine has nothing of the father's.
  const previewFather = preview && !hasFather
  // Pieniądze (guide section G): the benefit for every period the engine priced.
  const payments = placePayments(timeline.payments)
  const moneyRows = payments.reduce((n, p) => Math.max(n, p.row + 1), 0)
  const moneyRow = lanes.length + 2 + (previewFather ? 1 : 0)
  const rowsBelowRuler = Math.max(
    1,
    lanes.length + (previewFather ? 1 : 0) + (payments.length > 0 ? 1 : 0),
  )
  const toneOf = (p: Payment) => timeline.segments.find((s) => s.id === p.segment_id)?.tone

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

  return (
    <div>
      <div className="mb-2 flex items-center gap-1">
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
              const left = Math.max(0, x(month.start))
              const next = months[index + 1]
              if (next && ((x(next.start) - left) / 100) * width < 44) return null
              return (
                <span
                  key={`${month.year}-${month.start}`}
                  className="absolute top-2 pl-1.5 text-xs font-bold whitespace-nowrap text-navy-500"
                  style={{ left: `${left}%` }}
                >
                  {month.label.replace('.', '')}
                  {month.label.startsWith('sty') && <span className="ml-1 font-normal">{month.year}</span>}
                </span>
              )
            })}
            {months.map((month) =>
              x(month.start) > 0 ? (
                <span
                  key={`m-${month.start}`}
                  className="absolute bottom-0 h-4 w-px bg-navy-300"
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
            {head !== today && (
              <span
                className="absolute bottom-1.5 -translate-x-1/2 text-[10px] font-bold text-navy-400"
                style={{ left: `${x(today)}%` }}
              >
                dziś
              </span>
            )}
          </div>

          {/* Under the clips: month lines and today. */}
          <div
            className="pointer-events-none relative"
            style={{ gridColumn: 2, gridRow: `2 / span ${rowsBelowRuler}` }}
          >
            {months.map((month) =>
              x(month.start) > 0 ? (
                <span
                  key={month.start}
                  className="absolute inset-y-0 w-px bg-line/60"
                  style={{ left: `${x(month.start)}%` }}
                />
              ) : null,
            )}
            <span className="absolute inset-y-0 w-px bg-navy-200" style={{ left: `${x(today)}%` }} />
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
                  'pointer-events-auto absolute top-1 left-0 -translate-x-1/2 cursor-ew-resize rounded-full bg-navy-900 px-2.5 py-1 text-xs font-bold whitespace-nowrap text-white shadow-[0_6px_14px_-6px_rgb(26_36_56/0.6)] transition-transform duration-150',
                  scrubbing && 'scale-105',
                )}
              >
                {head === today ? 'Dziś · ' : ''}
                {formatDayMonthShort(isoFromDay(head))}
              </span>
            </motion.div>
          </div>

          {lanes.map((lane, laneIndex) => {
            const placed = placeFlags(flags[lane], x, width)
            const rows = placed.reduce((n, f) => Math.max(n, f.row + 1), 0)
            const sorted = sortedIn(lane)
            const hasClips = sorted.length > 0
            const height = ROW_HEIGHT
            const clipTop = CLIP_TOP
            // Rows of fixed height, centred in the track; a chip is centred in its row.
            const firstRow = (ROW_HEIGHT - Math.max(1, rows) * FLAG_ROW) / 2
            const flagTop = (row: number, key: boolean) =>
              firstRow + row * FLAG_ROW + (FLAG_ROW - (key ? FLAG_EVENT_HEIGHT : FLAG_HINT_HEIGHT)) / 2
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
                  className="relative border-b border-line"
                  style={{ gridColumn: 2, gridRow: laneIndex + 2, height }}
                >
                  {placed.map((flag) => (
                    <FlagChip
                      key={flag.id}
                      flag={flag}
                      x={x(flag.day)}
                      top={flagTop(flag.row, flag.key)}
                      stemTo={null}
                      active={selectedId === flag.id || hoveredId === flag.id}
                      onClick={() => onSelect(flag.id)}
                      onHover={(on) => onHover(on ? flag.id : null)}
                    />
                  ))}

                  {hasClips && (
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
                              top: clipTop,
                              height: CLIP_HEIGHT,
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
                            trackWidth={width}
                            top={clipTop}
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
                    </>
                  )}
                </div>
              </Fragment>
            )
          })}

          {previewFather && (
            <>
              <PreviewLabel row={lanes.length + 2} label="Tata">
                <Illustration src={tata} size="lane" />
              </PreviewLabel>
              <div className="relative border-b border-line" style={{ gridColumn: 2, gridRow: lanes.length + 2, height: ROW_HEIGHT }}>
                <span
                  className="absolute grid place-items-center rounded-xl border-2 border-dashed border-navy-300 bg-navy-50"
                  style={{
                    top: (ROW_HEIGHT - CLIP_HEIGHT) / 2,
                    height: CLIP_HEIGHT,
                    left: `${x(birth)}%`,
                    width: `max(${CLIP_HEIGHT}px, ${Math.max(x(birth + PREVIEW_PATERNITY_DAYS) - x(birth), 0)}%)`,
                  }}
                  title="Urlop ojcowski — przykład"
                >
                  <Illustration src={ICONS.tataZDzieckiem} size="event" />
                </span>
                <span
                  className="absolute flex items-center pl-3 text-sm font-bold whitespace-nowrap text-navy-500"
                  style={{
                    top: (ROW_HEIGHT - CLIP_HEIGHT) / 2,
                    height: CLIP_HEIGHT,
                    left: `calc(${x(birth)}% + max(${CLIP_HEIGHT}px, ${Math.max(x(birth + PREVIEW_PATERNITY_DAYS) - x(birth), 0)}%))`,
                  }}
                >
                  Urlop ojcowski · przykład
                </span>
              </div>
            </>
          )}
          {payments.length > 0 && (
            <>
              <div
                className="sticky left-0 z-30 flex items-center gap-2 border-b border-line bg-white pr-3"
                style={{ gridColumn: 1, gridRow: moneyRow }}
              >
                <Illustration src={pieniadze} size="lane" />
                <span className="text-sm font-bold text-navy-900">Pieniądze</span>
              </div>
              <div
                className="relative border-b border-line"
                style={{ gridColumn: 2, gridRow: moneyRow, height: ROW_HEIGHT }}
              >
                {payments.map((p) => (
                  <MoneyClip
                    key={p.id}
                    payment={p}
                    rows={moneyRows}
                    left={x(dayNumber(p.start))}
                    span={x(dayNumber(p.end) + 1) - x(dayNumber(p.start))}
                    trackWidth={width}
                    option={toneOf(p) === 'option'}
                    changed={changedIds.has(p.id)}
                    changeVersion={changeVersion}
                    active={selectedId === p.id || hoveredId === p.id}
                    onClick={() => onSelect(p.id)}
                    onHover={(on) => onHover(on ? p.id : null)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <Readout timeline={timeline} day={head} onSelect={onSelect} onHover={onHover} />
    </div>
  )
}

/** Payments in as few rows as possible without overlapping (the parents' periods may run at the
 * same time, e.g. paternity leave during maternity leave). */
function placePayments(payments: Payment[]): (Payment & { row: number })[] {
  const rowEnds: number[] = []
  return [...payments]
    .sort((a, b) => a.start.localeCompare(b.start))
    .map((p) => {
      const start = dayNumber(p.start)
      let row = rowEnds.findIndex((end) => start > end)
      if (row === -1) row = rowEnds.length
      rowEnds[row] = dayNumber(p.end)
      return { ...p, row }
    })
}

/** The benefit for one period: amber, the mother's filled, the father's outlined; dashed while
 * the period is still to decide. Wide enough, it says the rate and the monthly amount. */
function MoneyClip({
  payment,
  rows,
  left,
  span,
  trackWidth,
  option,
  changed,
  changeVersion,
  active,
  onClick,
  onHover,
}: {
  payment: Payment & { row: number }
  rows: number
  left: number
  span: number
  trackWidth: number
  option: boolean
  changed: boolean
  changeVersion: number
  active: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  const gap = 4
  const height = rows === 1 ? 44 : Math.floor((ROW_HEIGHT - 12 - (rows - 1) * gap) / rows)
  const top = rows === 1 ? (ROW_HEIGHT - height) / 2 : 6 + payment.row * (height + gap)
  const px = (span / 100) * trackWidth
  const monthly = formatPlnShort(payment.monthly)
  const rate = formatRate(payment.rate)
  return (
    <motion.button
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      aria-label={`${payment.title}: ${formatPln(payment.monthly)} miesięcznie, ${rate} podstawy`}
      title={`${payment.title}: ${payment.summary}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: 0.4 }}
      className={cn(
        'absolute flex items-center justify-center overflow-hidden rounded-lg px-2 text-xs font-bold whitespace-nowrap text-navy-900',
        'transition-[left,width,box-shadow] duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]',
        'outline-none focus-visible:ring-2 focus-visible:ring-zus-400',
        payment.lane === 'father' ? 'border-2 bg-white' : 'border bg-sun-100',
        option ? 'border-dashed border-sun-400' : 'border-sun-300',
        active && 'ring-2 ring-navy-900/25 ring-offset-1',
      )}
      style={{
        top,
        height,
        left: `calc(${left}% + 2px)`,
        width: `calc(${span}% - 4px)`,
      }}
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
      <span className="relative truncate">
        {px >= 170 ? `${rate} · ${monthly}/mies.` : px >= 90 ? monthly : px >= 44 ? rate : ''}
      </span>
    </motion.button>
  )
}

/** Label of a preview track: the drawing, the name and an "example" badge. */
function PreviewLabel({ row, label, children }: { row: number; label: string; children: ReactNode }) {
  return (
    <div
      className="sticky left-0 z-30 flex items-center gap-2 border-b border-line bg-white pr-2"
      style={{ gridColumn: 1, gridRow: row }}
    >
      {children}
      <span className="min-w-0">
        <span className="block text-sm font-bold text-navy-700">{label}</span>
        <span className="block text-[10px] font-bold text-sun-700">przykład</span>
      </span>
    </div>
  )
}

/** What happens on a day (the playhead's, or today on phones), in a few bold facts. */
export function Readout({
  timeline,
  day,
  onSelect,
  onHover,
}: {
  timeline: Timeline
  day: number
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}) {
  const iso = isoFromDay(day)
  const byStart = [...timeline.segments].sort((a, b) => a.start.localeCompare(b.start))
  const active = byStart.filter((s) => dayNumber(s.start) <= day && day <= dayNumber(s.end))
  const upcoming = byStart.find((s) => dayNumber(s.start) > day)
  const markersToday = timeline.markers.filter((m) => dayNumber(m.date) === day)
  const nextMarker = [...timeline.markers]
    .filter((m) => dayNumber(m.date) > day)
    .sort((a, b) => a.date.localeCompare(b.date))[0]
  const nextDocument = [...timeline.documents]
    .filter((d) => !d.done && dayNumber(d.needed_by) >= day)
    .sort((a, b) => a.needed_by.localeCompare(b.needed_by))[0]

  const lines: { key: string; id: string; icon: string; lead?: string; title: string; rest: string }[] = []
  for (const s of active) {
    const elapsed = day - dayNumber(s.start) + 1
    const progress =
      s.days % 7 === 0 ? `tydzień ${Math.ceil(elapsed / 7)} z ${s.days / 7}` : `dzień ${elapsed} z ${s.days}`
    lines.push({ key: `a-${s.id}`, id: s.id, icon: segmentIcon(s), title: s.title, rest: `${progress} · do ${formatDayMonthShort(s.end)}` })
    // Section G: what this period pays, as the engine computed it.
    const payment = timeline.payments.find((p) => p.segment_id === s.id)
    if (payment) {
      lines.push({
        key: `p-${payment.id}`,
        id: payment.id,
        icon: pieniadze,
        lead: 'Zasiłek',
        title: `${formatPln(payment.monthly)} miesięcznie`,
        rest: `${formatRate(payment.rate)} podstawy`,
      })
    }
  }
  if (active.length === 0 && upcoming) {
    lines.push({
      key: `u-${upcoming.id}`,
      id: upcoming.id,
      icon: segmentIcon(upcoming),
      lead: 'Następnie',
      title: upcoming.title,
      rest: `${formatDistance(iso, upcoming.start)} · ${formatDayMonthShort(upcoming.start)}`,
    })
  }
  for (const m of markersToday) {
    lines.push({ key: `t-${m.id}`, id: m.id, icon: markerIcon(m), title: m.title, rest: 'tego dnia' })
  }
  if (nextMarker) {
    lines.push({
      key: `n-${nextMarker.id}`,
      id: nextMarker.id,
      icon: markerIcon(nextMarker),
      lead: 'Najbliższy ważny dzień',
      title: nextMarker.title,
      rest: `${formatDistance(iso, nextMarker.date)} · ${formatDayMonthShort(nextMarker.date)}`,
    })
  }
  if (nextDocument) {
    lines.push({
      key: `d-${nextDocument.id}`,
      id: nextDocument.id,
      icon: documentIcon(nextDocument),
      lead: 'Dokument',
      title: nextDocument.title,
      rest: `potrzebny ${formatDistance(iso, nextDocument.needed_by)} · ${formatDayMonthShort(nextDocument.needed_by)}`,
    })
  }

  const label = weekdayDate.format(new Date(`${iso}T00:00:00Z`))
  const comma = label.indexOf(', ')
  return (
    <div
      className="mt-3 flex flex-col gap-3 rounded-3xl bg-navy-50/60 px-4 py-4 sm:flex-row sm:gap-6 sm:px-5"
      aria-live="polite"
    >
      <div className="shrink-0 sm:w-44">
        <p className="text-xs font-bold text-navy-500 capitalize">{label.slice(0, comma)}</p>
        <p className="mt-0.5 text-lg leading-tight font-bold text-navy-900">{label.slice(comma + 2)}</p>
        <p className="mt-0.5 text-sm text-navy-500">{formatDistance(timeline.today, iso)}</p>
      </div>
      <ul className="-mx-2 min-w-0 flex-1 space-y-0.5 sm:mx-0">
        {lines.length === 0 && <li className="pt-1 text-navy-500">Tego dnia nic się nie zmienia.</li>}
        {lines.map((line) => (
          <li key={line.key}>
            <button
              type="button"
              onClick={() => onSelect(line.id)}
              onMouseEnter={() => onHover(line.id)}
              onMouseLeave={() => onHover(null)}
              className="flex w-full items-center gap-2.5 rounded-xl px-2 py-1 text-left transition-colors duration-150 hover:bg-white"
            >
              <Illustration src={line.icon} size="hint" />
              <span className="min-w-0">
              {line.lead && <span className="text-navy-500">{line.lead}: </span>}
              <span className="font-bold text-navy-900">{line.title}</span>
              <span className="text-navy-400"> · </span>
              <span className="font-bold text-zus-700">{line.rest}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
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
  stemTo,
  active,
  onClick,
  onHover,
}: {
  flag: PlacedFlag
  x: number
  top: number
  stemTo: number | null
  active: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  const document = flag.kind === 'document'
  return (
    <>
      {stemTo !== null && (
        <span
          className="absolute z-10 w-0 -translate-x-1/2 border-l-2 border-dashed border-sun-400"
          style={{ left: `${x}%`, top: top + FLAG_HINT_HEIGHT, height: stemTo - top - FLAG_HINT_HEIGHT }}
        />
      )}
      <motion.button
        type="button"
        onClick={onClick}
        onMouseEnter={() => onHover(true)}
        onMouseLeave={() => onHover(false)}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.5 }}
        className={cn(
          'absolute z-20 flex items-center rounded-full border whitespace-nowrap',
          'transition-[border-color,background-color] duration-200 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none',
          flag.side === 'left' ? '-translate-x-full' : '-translate-x-[6px]',
          flag.key
            ? 'h-10 gap-2 border-sun-300 bg-sun-100/70 pr-4 pl-0.5 text-sm font-bold text-navy-900'
            : 'h-[30px] gap-1.5 border-line bg-white pr-3 pl-1 text-xs font-bold text-navy-700',
          document && flag.done && 'border-zus-200 text-zus-700',
          active && (flag.key ? 'bg-sun-100' : 'border-sun-300 bg-sun-100/60'),
        )}
        style={{ top, left: `${x}%` }}
      >
        <Illustration src={flag.icon} size={flag.key ? 'event' : 'hint'} className={flag.key ? 'bg-white' : ''} />
        {flag.text}
        {document && flag.done && <Check className="size-3.5" strokeWidth={3} />}
      </motion.button>
    </>
  )
}

function Clip({
  segment,
  left,
  span,
  trackWidth,
  top,
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
  trackWidth: number
  top: number
  index: number
  joinLeft: boolean
  joinRight: boolean
  changed: boolean
  changeVersion: number
  active: boolean
  onClick: () => void
  onHover: (on: boolean) => void
}) {
  const px = (span / 100) * trackWidth
  const weeks = segment.days % 7 === 0 ? `${segment.days / 7} tyg.` : `${segment.days} dni`
  const label = segmentLook(segment).label
  return (
    <motion.button
      type="button"
      onClick={onClick}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      aria-label={`${segment.title}, ${weeks}`}
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
        clipClass(segment),
        joinLeft && 'rounded-l-none border-l-0',
        joinRight && 'rounded-r-none',
        active && 'ring-2 ring-navy-900/25 ring-offset-2 brightness-[0.96]',
      )}
      style={{ top, height: CLIP_HEIGHT, left: `${left}%`, width: `${span}%` }}
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
      {px >= 96 && (
        <Illustration src={segmentIcon(segment)} size="event" className="relative -ml-1.5" />
      )}
      {px >= 150 ? (
        <>
          <span className="relative truncate text-sm font-bold">
            {label} · {weeks}
          </span>
          {px >= 300 && (
            <span className="relative ml-auto truncate text-xs font-bold opacity-70">
              {formatDayMonthShort(segment.start)} – {formatDayMonthShort(segment.end)}
            </span>
          )}
        </>
      ) : px >= 96 ? (
        <span className="relative text-xs font-bold">{weeks}</span>
      ) : px >= 40 ? (
        <span className="relative mx-auto text-xs font-bold">{weeks}</span>
      ) : null}
    </motion.button>
  )
}
