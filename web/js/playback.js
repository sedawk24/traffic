// Clock, per-frame vehicle interpolation, and windowed trip streaming with
// next-window prefetch (dense runs stream 300 s windows; the prefetch removes
// the stall the old viewer hit at every window edge).
import { WIN_SPAN, WIN_EVERY } from './config.js';
import { S } from './state.js';
import { getTrips } from './api.js';

const R = 6371000, rad = Math.PI / 180;
const distM = (a, b) => {
  const dLat = (b[1] - a[1]) * rad, dLon = (b[0] - a[0]) * rad, la = a[1] * rad, lb = b[1] * rad;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(la) * Math.cos(lb) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
};

// trips or busTrips changed -> rebuild the combined stable array once
export function refreshAllTrips() {
  S.allTrips = S.busTrips.length ? S.trips.concat(S.busTrips) : S.trips;
}

// interpolate every active vehicle at time t -> [{position, angle, cls, vid, speed}]
export function interpAt(t) {
  const out = [];
  const all = S.allTrips;
  for (const tr of all) {
    if (t < tr.t0 || t > tr.tN) continue;
    const ts = tr.timestamps, n = ts.length;
    let lo = 0, hi = n - 1;
    while (lo + 1 < hi) { const m = (lo + hi) >> 1; if (ts[m] <= t) lo = m; else hi = m; }
    const a = tr.path[lo], b = tr.path[Math.min(lo + 1, n - 1)], dt = (ts[lo + 1] - ts[lo]) || 1;
    const f = Math.max(0, Math.min(1, (t - ts[lo]) / dt));
    const lon = a[0] + (b[0] - a[0]) * f, lat = a[1] + (b[1] - a[1]) * f;
    const dE = (b[0] - a[0]) * Math.cos(lat * rad), dN = b[1] - a[1];
    out.push({
      position: [lon, lat],
      angle: -((dE || dN) ? Math.atan2(dE, dN) / rad : 0),
      cls: tr.cls,
      vid: tr.vid,
      speed: distM(a, b) / dt,
    });
  }
  return out;
}

export async function loadWindow(lo, hi) {
  return getTrips(S.runId, { lo, hi, every: WIN_EVERY });
}

// keep the streamed window covering T; prefetch the next one before it's needed
export function ensureWindow() {
  if (!S.windowed) return;
  const past = S.T < S.winLo, nearEnd = S.T > S.winHi - 120;
  if (!S.winBusy && (past || S.T > S.winHi)) {
    // hard miss (scrub/jump): fetch the containing window now
    S.winBusy = true;
    const lo = Math.max(0, Math.floor(S.T) - 30), hi = Math.floor(S.T) + WIN_SPAN;
    loadWindow(lo, hi)
      .then(w => { S.trips = w; S.winLo = lo; S.winHi = hi; S.nextWin = null; refreshAllTrips(); })
      .finally(() => { S.winBusy = false; });
    return;
  }
  if (nearEnd && S.nextWin && S.nextWin.trips) {
    // swap in the prefetched window once we cross into it
    if (S.T >= S.nextWin.lo + 30) {
      S.trips = S.nextWin.trips;
      S.winLo = S.nextWin.lo;
      S.winHi = S.nextWin.hi;
      S.nextWin = null;
      refreshAllTrips();
    }
    return;
  }
  if (nearEnd && !S.nextWin && !S.winBusy) {
    const lo = S.winHi - 60, hi = S.winHi - 60 + WIN_SPAN;
    S.nextWin = { lo, hi, trips: null };
    loadWindow(lo, hi).then(w => { if (S.nextWin && S.nextWin.lo === lo) S.nextWin.trips = w; });
  }
}

// frame stats for the HUD (EMA-smoothed so the numbers don't flicker)
let ema = null;
export function frameStats(frame) {
  const n = frame.length;
  let sum = 0, stopped = 0, buses = 0;
  for (const v of frame) {
    sum += v.speed;
    if (v.speed < 0.5) stopped++;
    if (v.cls === 'bus') buses++;
  }
  const cur = {
    active: n,
    kmh: n ? (sum / n) * 3.6 : 0,
    stopped: n ? (stopped / n) * 100 : 0,
    buses,
  };
  if (!ema) ema = cur;
  const k = 0.12;
  ema = {
    active: cur.active, // count is exact, no smoothing
    kmh: ema.kmh + (cur.kmh - ema.kmh) * k,
    stopped: ema.stopped + (cur.stopped - ema.stopped) * k,
    buses: cur.buses,
  };
  return ema;
}
