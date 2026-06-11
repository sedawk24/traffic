// Palettes, zoom thresholds, URL params — the dark-cinematic design tokens.

export const LOD_Z = 12.6;   // < flow ribbons | >= vehicle icons (lowered from 13.2)
export const SIG_Z = 14.8;   // >= live traffic-signal heads
export const BLD_Z = 14.5;   // >= 3D building extrusions

// vehicle base colors (per-class), tinted per vehicle by a stable hue jitter
export const VCOL = {
  car: [56, 189, 248],     // cyan-sky
  bus: [251, 191, 36],     // amber
  truck: [196, 154, 108],  // taupe
  rail: [192, 132, 252],
};
export const TRAIL_COL = {
  car: [34, 211, 238, 70],
  bus: [251, 191, 36, 88],
  truck: [196, 154, 108, 70],
  rail: [192, 132, 252, 70],
};
// land-use fills, tuned for the dark basemap (subtle, desaturated)
export const ZCOL = {
  residential: [96, 170, 120, 26],
  commercial: [86, 150, 220, 30],
  industrial: [205, 160, 100, 30],
  parkland: [70, 160, 105, 36],
  'downtown-core': [165, 125, 230, 30],
};
export const ZONE_LABELS = {
  'downtown-core': 'Downtown core', residential: 'Residential', commercial: 'Commercial',
  industrial: 'Industrial', parkland: 'Parkland',
};
// street-zoom road styling by class (casing-like slates on dark ground)
export const RCOL = {
  arterial: [62, 78, 98, 235],
  collector: [46, 58, 73, 200],
  local: [35, 44, 56, 150],
};
export const RW = { arterial: 1.7, collector: 1.0, local: 0.55 };
export const TRANSIT_COL = [184, 120, 52, 60];

export const ACCENT = [34, 211, 238];      // cyan
export const DANGER = [244, 63, 94];       // rose
export const OK = [52, 211, 153];          // emerald

// congestion ramp on dark ground: stopped rose -> amber -> emerald free-flow
export function congColor(s) {
  const x = Math.max(0, Math.min(1, (s || 0) / 11));
  const lerp = (a, b, f) => Math.round(a + (b - a) * f);
  if (x < 0.5) {
    const f = x / 0.5;
    return [lerp(244, 245, f), lerp(63, 158, f), lerp(94, 11, f)];
  }
  const f = (x - 0.5) / 0.5;
  return [lerp(245, 52, f), lerp(158, 211, f), lerp(11, 153, f)];
}

// flow-ribbon ramp: deep blue -> cyan -> amber -> red (sqrt against volRef)
export function volColor(v, volRef, alpha = 215) {
  const x = Math.min(1, Math.sqrt((v || 0) / volRef));
  const stops = [
    [0.0, [29, 78, 216]],
    [0.45, [6, 182, 212]],
    [0.75, [245, 158, 11]],
    [1.0, [239, 68, 68]],
  ];
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [x0, c0] = stops[i - 1], [x1, c1] = stops[i];
      const f = (x - x0) / (x1 - x0 || 1);
      return [0, 1, 2].map(j => Math.round(c0[j] + (c1[j] - c0[j]) * f)).concat([alpha]);
    }
  }
  return stops[stops.length - 1][1].concat([alpha]);
}

export const sigColor = c =>
  (c === 'G' || c === 'g') ? [52, 211, 153] :
  (c === 'y' || c === 'Y') ? [251, 191, 36] :
  (c === 'r' || c === 'R') ? [244, 63, 94] : [120, 134, 148];

export const AREA_VIEW = {
  peninsula: { center: [-123.115, 49.283], zoom: 12.8 },
  central: { center: [-123.135, 49.262], zoom: 13.2 },
  vancouver: { center: [-123.125, 49.255], zoom: 11.8 },
  metro: { center: [-122.99, 49.22], zoom: 10.2 },
};
export const AREA_LABEL = {
  peninsula: 'Downtown peninsula', central: 'Central Vancouver',
  vancouver: 'City of Vancouver', metro: 'Metro Vancouver',
};

export const WIN_SPAN = 300;      // streamed window length (s) for dense runs
export const WIN_EVERY = 2;       // sample step inside a window (s)
export const WINDOWED_ABOVE = 8000; // vehicles; larger runs stream windows

export const Q = new URLSearchParams(location.search);
export function updateUrl(patch) {
  const q = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === undefined || v === '') q.delete(k); else q.set(k, v);
  }
  history.replaceState(null, '', `${location.pathname}?${q}`);
}

export const css = c => `rgb(${c[0]},${c[1]},${c[2]})`;
export const hms = sec => {
  const f = n => String(Math.floor(n)).padStart(2, '0');
  return `${f(sec / 3600 % 24)}:${f(sec / 60 % 60)}:${f(sec % 60)}`;
};
export const hm = sec => hms(sec).slice(0, 5);
