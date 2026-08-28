/**
 * The one shared labyrinth geometry generator — Hero, SectionLabyrinth, and
 * SectionClarity all reference the *same* generated asset (brief section 9/
 * 10: "the labyrinth (from earlier sections' shared SVG asset) visually
 * disappears, leaving only the thread"), so this lives in one place rather
 * than being redrawn per section. A generated square spiral, not a
 * historically exact unicursal Cretan labyrinth — the brief itself asks to
 * "reinterpret in an extremely modern way," not reproduce myth literally.
 * Pure function of fixed inputs, deterministic, safe to call during SSR or
 * client render with identical output either way.
 */

export type Point = [number, number];

export function squareSpiral(
  center: Point,
  startArm: number,
  turns: number,
  decrement: number,
  minArm = 8,
): { d: string; points: Point[] } {
  const dirs: Point[] = [
    [1, 0],
    [0, 1],
    [-1, 0],
    [0, -1],
  ];
  let [x, y] = [center[0] - startArm, center[1] - startArm];
  let len = startArm;
  const points: Point[] = [[x, y]];
  let d = `M ${x} ${y}`;
  for (let i = 0; i < turns; i++) {
    const [dx, dy] = dirs[i % 4];
    x += dx * len;
    y += dy * len;
    d += ` L ${x} ${y}`;
    points.push([x, y]);
    len = Math.max(len - decrement, minArm);
  }
  return { d, points };
}

/** The "resolved" clean path a labyrinth morphs into — brief's stage 6/10.
 * MorphSVG needs a real path with a compatible-enough point count to
 * interpolate; a gently bowed line (not perfectly straight, which would
 * morph less convincingly from a many-cornered spiral) drawn with enough
 * intermediate points to match segment counts reasonably. */
export function resolvedPath(from: Point, to: Point, segments: number): string {
  const [x1, y1] = from;
  const [x2, y2] = to;
  const midY = (y1 + y2) / 2 - 18;
  let d = `M ${x1} ${y1}`;
  for (let i = 1; i <= segments; i++) {
    const t = i / segments;
    const x = x1 + (x2 - x1) * t;
    // A single gentle quadratic-like bow, sampled at even steps so the
    // point count matches the spiral path MorphSVG interpolates from.
    const y = y1 + (y2 - y1) * t - Math.sin(t * Math.PI) * (y1 - midY);
    d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return d;
}
