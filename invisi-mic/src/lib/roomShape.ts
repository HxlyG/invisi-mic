// Geometry helpers for drawing room outlines. All lengths are meters.
export interface Point {
  x: number
  y: number
}

export const DRAW_AREA = { width: 40, length: 30 }
export const MIN_EDGE = 0.3
export const MIN_AREA = 4

const EPSILON = 1e-9

const cross = (a: Point, b: Point, c: Point) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y)

const onSegment = (a: Point, b: Point, p: Point) =>
  Math.abs(cross(a, b, p)) < EPSILON
  && p.x >= Math.min(a.x, b.x) - EPSILON && p.x <= Math.max(a.x, b.x) + EPSILON
  && p.y >= Math.min(a.y, b.y) - EPSILON && p.y <= Math.max(a.y, b.y) + EPSILON

// True when the segments cross or touch anywhere.
const segmentsConflict = (a: Point, b: Point, c: Point, d: Point) => {
  const d1 = cross(a, b, c)
  const d2 = cross(a, b, d)
  const d3 = cross(c, d, a)
  const d4 = cross(c, d, b)
  if (d1 * d2 < 0 && d3 * d4 < 0) return true
  return onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b)
}

export const signedArea = (points: Point[]) =>
  points.reduce((area, p, i) => {
    const next = points[(i + 1) % points.length]
    return area + p.x * next.y - next.x * p.y
  }, 0) / 2

// Folding straight back along the previous wall would overlap it.
const foldsBack = (previous: Point, corner: Point, next: Point) =>
  Math.abs(cross(previous, corner, next)) < EPSILON
  && (corner.x - previous.x) * (next.x - corner.x) + (corner.y - previous.y) * (next.y - corner.y) < 0

// Returns an error message, or null when the next corner is valid.
export function canAddPoint(points: Point[], next: Point): string | null {
  const last = points[points.length - 1]
  if (!last) return null
  if (distance(last, next) < MIN_EDGE) return "Wall is too short"
  if (points.length >= 2 && foldsBack(points[points.length - 2], last, next)) return "Wall overlaps the previous wall"
  // The newest wall shares an endpoint with the last segment, so skip that one.
  for (let i = 0; i < points.length - 2; i++) {
    if (segmentsConflict(last, next, points[i], points[i + 1])) return "Walls can't cross"
  }
  return null
}

export function canClose(points: Point[]): string | null {
  if (points.length < 3) return "A room needs at least 3 corners"
  const first = points[0]
  const last = points[points.length - 1]
  if (distance(first, last) < MIN_EDGE) return "Wall is too short"
  if (foldsBack(points[points.length - 2], last, first) || foldsBack(last, first, points[1])) {
    return "Wall overlaps the previous wall"
  }
  // Skip the segments touching the closing wall at either end.
  for (let i = 1; i < points.length - 2; i++) {
    if (segmentsConflict(last, first, points[i], points[i + 1])) return "Walls can't cross"
  }
  if (Math.abs(signedArea(points)) < MIN_AREA) return "Room is too small"
  return null
}

export const pointInPolygon = (x: number, y: number, outline: Point[]) => {
  let inside = false
  for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    const a = outline[i]
    const b = outline[j]
    if ((a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x) inside = !inside
  }
  return inside
}

// Moves the outline to the origin and winds it counter-clockwise, as the backend expects.
export function normalizeOutline(points: Point[]) {
  const minX = Math.min(...points.map((p) => p.x))
  const minY = Math.min(...points.map((p) => p.y))
  const round = (value: number) => Math.round(value * 100) / 100
  let outline = points.map((p) => ({ x: round(p.x - minX), y: round(p.y - minY) }))
  if (signedArea(outline) < 0) outline = outline.reverse()
  return {
    outline,
    width: Math.max(...outline.map((p) => p.x)),
    length: Math.max(...outline.map((p) => p.y)),
  }
}

// Midpoint of the widest horizontal span through the polygon.
export function interiorPoint(outline: Point[]): Point {
  const ys = outline.map((p) => p.y)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  let best: Point = outline[0]
  let bestWidth = -1
  for (const fraction of [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]) {
    const y = minY + (maxY - minY) * fraction
    const crossings: number[] = []
    outline.forEach((a, i) => {
      const b = outline[(i + 1) % outline.length]
      if ((a.y > y) !== (b.y > y)) crossings.push(a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y))
    })
    crossings.sort((a, b) => a - b)
    for (let i = 0; i + 1 < crossings.length; i += 2) {
      if (crossings[i + 1] - crossings[i] > bestWidth) {
        bestWidth = crossings[i + 1] - crossings[i]
        best = { x: (crossings[i] + crossings[i + 1]) / 2, y }
      }
    }
  }
  return best
}

// Returns the point unchanged when inside, otherwise a spot just inside the nearest wall.
export function moveInside(point: Point, outline: Point[]): Point {
  if (pointInPolygon(point.x, point.y, outline)) return point
  const center = interiorPoint(outline)
  let nearest = center
  let nearestDistance = Infinity
  outline.forEach((a, i) => {
    const b = outline[(i + 1) % outline.length]
    const dx = b.x - a.x
    const dy = b.y - a.y
    const t = Math.min(1, Math.max(0, ((point.x - a.x) * dx + (point.y - a.y) * dy) / (dx * dx + dy * dy || 1)))
    const candidate = { x: a.x + t * dx, y: a.y + t * dy }
    const d = distance(candidate, point)
    if (d < nearestDistance) {
      nearestDistance = d
      nearest = candidate
    }
  })
  const toCenter = distance(center, nearest)
  if (!toCenter) return center
  const step = Math.min(0.3, toCenter) / toCenter
  const moved = { x: nearest.x + (center.x - nearest.x) * step, y: nearest.y + (center.y - nearest.y) * step }
  return pointInPolygon(moved.x, moved.y, outline) ? moved : center
}
