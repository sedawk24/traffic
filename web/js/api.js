// Thin fetch wrappers — every endpoint in one place; 404s resolve to null.
const j = r => (r.ok ? r.json() : null);

export const getRuns = () => fetch('/api/runs').then(j);
export const getMeta = id => fetch(`/api/runs/${id}/meta`).then(j);
export const getVolumes = id => fetch(`/api/runs/${id}/volumes`).then(j).catch(() => ({}));
export const getSignalsLive = id =>
  fetch(`/api/runs/${id}/signals-live`).then(j).catch(() => null);
export const getHotspots = id => fetch(`/api/runs/${id}/hotspots`).then(j).catch(() => null);
export const getTimeline = id => fetch(`/api/runs/${id}/timeline`).then(j).catch(() => null);
export const getNetwork = area => fetch(`/api/network?net=${area}`).then(j);
export const getZones = area => fetch(`/api/zones?net=${area}`).then(j).catch(() => null);
export const getTransit = area => fetch(`/api/transit?net=${area}`).then(j).catch(() => null);
export const getTransitVehicles = area =>
  fetch(`/api/transit-vehicles?net=${area}`).then(j).catch(() => null);

export function getTrips(runId, { lo = null, hi = null, every = 2 } = {}) {
  const q = lo != null ? `?every=${every}&start=${lo}&end=${hi}` : `?every=${every}`;
  return fetch(`/api/runs/${runId}/trips${q}`).then(j).then(w => {
    for (const tr of w || []) {
      tr.t0 = tr.timestamps[0];
      tr.tN = tr.timestamps[tr.timestamps.length - 1];
    }
    return w || [];
  });
}
