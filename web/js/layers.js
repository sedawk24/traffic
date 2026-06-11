// deck.gl layer stack — glow flow ribbons, sprite vehicles with trails,
// halo signal heads, hotspot pulse rings. All layers rebuild per frame; deck
// diffs props internally.
import {
  LOD_Z, SIG_Z, VCOL, TRAIL_COL, ZCOL, RCOL, RW, TRANSIT_COL, DANGER, ACCENT,
  congColor, volColor, sigColor,
} from './config.js';
import { S } from './state.js';
import { buildAtlas, hueJitter, SIZE_M } from './atlas.js';

const ATLAS = buildAtlas();
// luma.gl v9 parameter names (deck.gl 9): disable depth so 2D layers stack by
// order; additive blending for the glow passes.
const NO_DEPTH = { depthCompare: 'always', depthWriteEnabled: false };
const ADD_BLEND = {
  ...NO_DEPTH,
  blendColorOperation: 'add',
  blendColorSrcFactor: 'src-alpha',
  blendColorDstFactor: 'one',
  blendAlphaOperation: 'add',
  blendAlphaSrcFactor: 'one',
  blendAlphaDstFactor: 'one',
};

// binary search the signal state string active at t
function stateAt(ch, t) {
  if (!ch || !ch.length || ch[0][0] > t) return ch && ch[0] ? ch[0][1] : '';
  let lo = 0, hi = ch.length - 1, idx = 0;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (ch[m][0] <= t) { idx = m; lo = m + 1; } else hi = m - 1; }
  return ch[idx][1];
}

// Static layers (zones / roads / transit / closure / gateways) are memoized —
// rebuilding 20k-feature GeoJSON layers every animation frame starves the main
// thread. They only change with run, zoom band, toggles, or closure state.
let staticCache = { key: null, layers: [] };

export function buildLayers(deckgl) {
  const t = Math.min(S.tMax, S.T);
  const flow = S.zoom < LOD_Z;
  const closureActive = S.closedEdges.length &&
    (S.begin + S.T) >= S.closedStart && (!S.closedEnd || (S.begin + S.T) < S.closedEnd);
  const zoneBand = S.zoom >= 15 ? 2 : S.zoom >= 13.5 ? 1 : 0;
  const key = [
    S.runId, S.area, flow, zoneBand, closureActive, S.volRef,
    S.show.zones, S.show.roads, S.show.transit, S.show.labels,
  ].join('|');
  if (staticCache.key !== key) {
    staticCache = { key, layers: buildStatic(deckgl, flow, zoneBand, closureActive) };
  }
  return staticCache.layers.concat(buildDynamic(deckgl, t, flow));
}

function buildStatic(deckgl, flow, zoneBand, closureActive) {
  const L = [];

  // --- land use (very subtle on dark ground) -------------------------------
  if (S.show.zones && S.zonesPoly) {
    const op = zoneBand === 2 ? 0.4 : zoneBand === 1 ? 0.7 : 1.0;
    L.push(new deckgl.GeoJsonLayer({
      id: 'zones', data: S.zonesPoly, filled: true, stroked: false, opacity: op,
      getFillColor: f => ZCOL[f.properties.land_use] || [110, 120, 130, 22],
      parameters: NO_DEPTH,
    }));
  }

  // --- roads: glow flow ribbons (region) / slate casings (street) ----------
  if (S.show.roads && S.roads) {
    if (flow) {
      const w = f => 0.6 + 3.6 * Math.min(1, (S.volMap[f.properties.id] || 0) / S.volRef);
      L.push(new deckgl.GeoJsonLayer({       // wide soft under-glow (additive)
        id: 'flow-glow', data: S.roads, stroked: true, filled: false,
        getLineColor: f => volColor(S.volMap[f.properties.id], S.volRef, 44),
        getLineWidth: f => w(f) * 3.2,
        lineWidthUnits: 'pixels', lineWidthMinPixels: 1.2,
        updateTriggers: { getLineColor: S.volRef, getLineWidth: S.volRef },
        parameters: ADD_BLEND,
      }));
      L.push(new deckgl.GeoJsonLayer({       // bright core
        id: 'flow-core', data: S.roads, stroked: true, filled: false, pickable: true,
        getLineColor: f => volColor(S.volMap[f.properties.id], S.volRef, 235),
        getLineWidth: w,
        lineWidthUnits: 'pixels', lineWidthMinPixels: 0.4,
        updateTriggers: { getLineColor: S.volRef, getLineWidth: S.volRef },
        parameters: NO_DEPTH,
      }));
    } else {
      L.push(new deckgl.GeoJsonLayer({
        id: 'roads', data: S.roads, stroked: true, filled: false, pickable: true,
        getLineColor: f => RCOL[f.properties.class] || RCOL.local,
        getLineWidth: f => (RW[f.properties.class] || 0.5),
        lineWidthUnits: 'pixels', lineWidthMinPixels: 0.4,
        parameters: NO_DEPTH,
      }));
    }
  }

  // --- transit routes -------------------------------------------------------
  if (S.show.transit && S.transitGeo) {
    L.push(new deckgl.GeoJsonLayer({
      id: 'transit', data: S.transitGeo, stroked: true, filled: false,
      getLineColor: TRANSIT_COL, getLineWidth: 1,
      lineWidthUnits: 'pixels', lineWidthMinPixels: 0.6, parameters: NO_DEPTH,
    }));
  }

  // --- closure scenario -----------------------------------------------------
  if (closureActive && S.roads) {
    const set = new Set(S.closedEdges);
    const feats = S.roads.features.filter(x => set.has(x.properties.id));
    if (feats.length) {
      L.push(new deckgl.GeoJsonLayer({
        id: 'closed', data: { type: 'FeatureCollection', features: feats },
        stroked: true, filled: false, getLineColor: DANGER, getLineWidth: 5,
        lineWidthUnits: 'pixels', lineWidthMinPixels: 3, parameters: NO_DEPTH,
      }));
      const mk = feats.find(f => f.properties.id === S.closedMarker) || feats[0];
      const cc = mk.geometry.coordinates, mid = cc[Math.floor(cc.length / 2)];
      L.push(new deckgl.TextLayer({
        id: 'closedlbl', data: [{ position: mid }], getPosition: d => d.position,
        getText: () => '✕ closed', getSize: 13, getColor: [255, 205, 210],
        background: true, getBackgroundColor: [60, 12, 22, 235], backgroundPadding: [5, 3],
        getPixelOffset: [0, -16], fontWeight: 700,
      }));
    }
  }

  // --- gateways --------------------------------------------------------------
  if (S.show.labels && S.gateways.length) {
    L.push(new deckgl.ScatterplotLayer({
      id: 'gw', data: S.gateways, getPosition: f => f.geometry.coordinates,
      getFillColor: [...DANGER, 200], getRadius: 4.5, radiusUnits: 'pixels',
      stroked: true, getLineColor: [10, 14, 19, 255], lineWidthMinPixels: 1.5,
    }));
    L.push(new deckgl.TextLayer({
      id: 'gwl', data: S.gateways, getPosition: f => f.geometry.coordinates,
      getText: f => f.properties.name || '', getSize: 11,
      getColor: [205, 217, 229, 255], getPixelOffset: [0, -14],
      background: true, getBackgroundColor: [13, 20, 27, 215], backgroundPadding: [5, 2],
      fontWeight: 600,
    }));
  }
  return L;
}

function buildDynamic(deckgl, t, flow) {
  const L = [];

  // --- vehicle trails (comet tails, additive) ------------------------------
  if (S.show.trails && !flow && S.allTrips.length) {
    L.push(new deckgl.TripsLayer({
      id: 'trails', data: S.allTrips,  // stable reference — see state.js note
      getPath: d => d.path, getTimestamps: d => d.timestamps,
      getColor: d => TRAIL_COL[d.cls] || TRAIL_COL.car,
      currentTime: t, trailLength: 12, fadeTrail: true,
      widthUnits: 'pixels', getWidth: 1.6, widthMinPixels: 1, capRounded: true,
      parameters: ADD_BLEND,
    }));
  }

  // --- vehicles (sprite icons, meter-true) ----------------------------------
  let frame = [];
  if (S.show.vehicles && !flow) {
    frame = S.frame;
    L.push(new deckgl.IconLayer({
      id: 'veh', data: frame, iconAtlas: ATLAS.url, iconMapping: ATLAS.mapping,
      billboard: false, pickable: true,
      getIcon: d => ATLAS.mapping[d.cls] ? d.cls : 'car',
      getPosition: d => d.position,
      getColor: d => d.cls === 'bus'
        ? VCOL.bus
        : (S.show.congestion ? congColor(d.speed) : hueJitter(VCOL[d.cls] || VCOL.car, d.vid || '')),
      getAngle: d => d.angle,
      getSize: d => SIZE_M[d.cls] || SIZE_M.car,
      sizeUnits: 'meters', sizeMinPixels: 5, sizeMaxPixels: 64,
      alphaCutoff: 0.05,
      updateTriggers: { getColor: S.show.congestion },
      parameters: NO_DEPTH,
    }));
    if (S.follow && S.followPos) {
      L.push(new deckgl.ScatterplotLayer({
        id: 'follow-ring', data: [{ p: S.followPos }], getPosition: d => d.p,
        getRadius: 9, radiusUnits: 'meters', radiusMinPixels: 14,
        stroked: true, filled: false, getLineColor: [...ACCENT, 230],
        lineWidthUnits: 'pixels', getLineWidth: 2, parameters: ADD_BLEND,
      }));
    }
  }

  // --- live signal heads: soft halo + bright core ---------------------------
  if (S.show.signals && S.zoom >= SIG_Z && S.sigGroups.length) {
    const data = S.sigGroups.map(g => {
      const st = stateAt(S.sigChangesMap[g.tls], t);
      let col = 'r';
      for (const i of g.idxs) {
        const c = st[i] || 'r';
        if (c === 'G' || c === 'g') { col = 'G'; break; }
        if ((c === 'y' || c === 'Y') && col === 'r') col = 'y';
      }
      return { position: g.position, color: sigColor(col) };
    });
    L.push(new deckgl.ScatterplotLayer({
      id: 'sig-glow', data, getPosition: d => d.position,
      getFillColor: d => [...d.color, 70], getRadius: 9, radiusUnits: 'meters',
      radiusMinPixels: 5, radiusMaxPixels: 22,
      updateTriggers: { getFillColor: t }, parameters: ADD_BLEND,
    }));
    L.push(new deckgl.ScatterplotLayer({
      id: 'sig-core', data, getPosition: d => d.position,
      getFillColor: d => d.color, getRadius: 3.4, radiusUnits: 'meters',
      radiusMinPixels: 2.4, radiusMaxPixels: 8,
      stroked: true, getLineColor: [8, 12, 16, 235],
      lineWidthUnits: 'pixels', getLineWidth: 1, lineWidthMaxPixels: 1.4,
      updateTriggers: { getFillColor: t }, parameters: NO_DEPTH,
    }));
  }

  // --- hotspot focus: pulsing ring ------------------------------------------
  if (S.hotspotFocus) {
    const phase = (performance.now() / 1200) % 1;
    L.push(new deckgl.ScatterplotLayer({
      id: 'hotspot-pulse', data: [S.hotspotFocus],
      getPosition: d => [d.lon, d.lat],
      getRadius: 18 + 36 * phase, radiusUnits: 'meters', radiusMinPixels: 10,
      stroked: true, filled: false,
      getLineColor: [...DANGER, Math.round(220 * (1 - phase))],
      lineWidthUnits: 'pixels', getLineWidth: 2.5,
      updateTriggers: { getRadius: phase, getLineColor: phase },
      parameters: ADD_BLEND,
    }));
    L.push(new deckgl.ScatterplotLayer({
      id: 'hotspot-dot', data: [S.hotspotFocus], getPosition: d => [d.lon, d.lat],
      getRadius: 7, radiusUnits: 'meters', radiusMinPixels: 5,
      getFillColor: [...DANGER, 210], parameters: NO_DEPTH,
    }));
  }

  return L;
}
