// Hotspot panel: ranked worst intersections from /api/runs/{id}/hotspots
// (produced by `sim diagnose`); click to fly there and pulse the junction.
import { S } from './state.js';
import { getHotspots } from './api.js';
import { setHotspots } from './hud.js';

let map = null;

export function initHotspots(m) { map = m; }

export async function loadHotspots(runId) {
  S.hotspots = await getHotspots(runId);
  S.hotspotFocus = null;
  setHotspots(S.hotspots, null);
}

export function focusHotspot(rank) {
  const h = S.hotspots && S.hotspots.hotspots.find(x => x.rank === rank);
  if (!h || !map) return;
  if (S.hotspotFocus && S.hotspotFocus.rank === rank) {  // toggle off
    S.hotspotFocus = null;
    setHotspots(S.hotspots, null);
    return;
  }
  S.hotspotFocus = h;
  setHotspots(S.hotspots, rank);
  map.flyTo({ center: [h.lon, h.lat], zoom: Math.max(map.getZoom(), 16.3), duration: 1400 });
}
