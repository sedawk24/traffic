// App bootstrap: dark basemap + deck overlay + run loading + frame loop.
import {
  Q, AREA_VIEW, LOD_Z, hm, updateUrl,
} from './config.js';
import { S } from './state.js';
import * as api from './api.js';
import { loadBasemapStyle } from './basemap.js';
import { buildLayers } from './layers.js';
import { interpAt, ensureWindow, frameStats, loadWindow, refreshAllTrips } from './playback.js';
import * as hud from './hud.js';
import { initFollow, startFollow, stopFollow, tickFollow } from './follow.js';
import { initHotspots, loadHotspots, focusHotspot } from './hotspots.js';
import { addBuildings, setBuildingsVisible, toggleTilt } from './buildings.js';
import { WIN_SPAN, WINDOWED_ABOVE } from './config.js';

const deckgl = window.deck;
let map, overlay;

// ---------------------------------------------------------------------------
async function loadArea(area) {
  if (!S.areaData[area]) {
    hud.setLoading(`Loading <b>${area}</b> network…`);
    const net = await api.getNetwork(area);
    let zonesP = null, gw = [], tg = null, busS = null;
    if (area === 'peninsula' || area === 'central') tg = await api.getTransit(area);
    if (area === 'vancouver' || area === 'metro') busS = await api.getTransitVehicles(area);
    if (area !== 'metro') {
      const zones = (await api.getZones(area)) || { features: [] };
      zonesP = { type: 'FeatureCollection', features: zones.features.filter(f => f.geometry.type !== 'Point') };
      gw = zones.features.filter(f => f.properties.is_gateway);
    }
    S.areaData[area] = { roads: net, zonesPoly: zonesP, gateways: gw, transitGeo: tg, busSched: busS };
  }
  const d = S.areaData[area];
  S.roads = d.roads; S.zonesPoly = d.zonesPoly; S.transitGeo = d.transitGeo;
  S.gateways = d.gateways; S.busSchedRaw = d.busSched;
  hud.setArea(area);
  if (area !== S.area) {
    S.area = area;
    if (!Q.get('zoom') && AREA_VIEW[area]) {
      const v = AREA_VIEW[area];
      map.jumpTo(v);
      S.zoom = v.zoom;
    }
  }
}

function groupSignals(sig) {
  S.sigChangesMap = sig.changes || {};
  S.sigGroups = [];
  const sp = sig.pos || {}, se = sig.edges || {};
  const SIG_MERGE = 0.00015; // ~16 m: collapse approaches piled at one complex
  for (const tls in se) {
    const byEdge = {};
    (se[tls] || []).forEach((e, i) => {
      if (e == null || !sp[tls] || !sp[tls][i]) return;
      (byEdge[e] = byEdge[e] || []).push(i);
    });
    const groups = [];
    for (const e in byEdge) {
      const idxs = byEdge[e];
      let lon = 0, lat = 0;
      for (const i of idxs) { lon += sp[tls][i][0]; lat += sp[tls][i][1]; }
      const pos = [lon / idxs.length, lat / idxs.length];
      const near = groups.find(g =>
        Math.abs(g.position[0] - pos[0]) < SIG_MERGE && Math.abs(g.position[1] - pos[1]) < SIG_MERGE);
      if (near) near.idxs.push(...idxs);
      else groups.push({ tls, idxs: [...idxs], position: pos });
    }
    S.sigGroups.push(...groups);
  }
}

async function loadRun(id) {
  S.runId = id;
  hud.setLoading('Loading run…');
  const [meta, vol, sig, timeline] = await Promise.all([
    api.getMeta(id),
    api.getVolumes(id),
    api.getSignalsLive(id).then(s => s || { pos: {}, changes: {}, edges: {} }),
    api.getTimeline(id),
  ]);
  S.meta = meta;
  await loadArea((meta.params && meta.params.area) || 'peninsula');
  S.begin = meta.params.begin ?? 25200;
  S.tMax = meta.stats.trajectory.t_max;
  S.timeline = timeline;
  S.vehicles = meta.stats.trajectory.vehicles;
  S.volMap = vol || {};

  S.busTrips = [];
  if (S.busSchedRaw && S.busSchedRaw.buses) {
    for (const b of S.busSchedRaw.buses) {
      const ts = b.times.map(s => s - S.begin);
      S.busTrips.push({ cls: 'bus', vid: `sched_${S.busTrips.length}`, path: b.path, timestamps: ts, t0: ts[0], tN: ts[ts.length - 1] });
    }
  }

  const vv = Object.values(S.volMap).sort((a, b) => a - b);
  S.volRef = vv.length ? Math.max(8, vv[Math.floor(vv.length * 0.92)]) : 180;
  groupSignals(sig);

  S.windowed = S.vehicles > WINDOWED_ABOVE;
  S.winLo = 0; S.winHi = -1; S.nextWin = null;
  if (S.windowed) {
    S.winLo = Math.max(0, Math.floor(S.T) - 30);
    S.winHi = Math.floor(S.T) + WIN_SPAN;
    S.trips = await loadWindow(S.winLo, S.winHi);
  } else {
    S.trips = await api.getTrips(id, { every: 2 });
  }
  refreshAllTrips();

  // scenario compare (closure runs)
  const p = meta.params || {}, mt = (meta.stats || {}).metrics;
  S.closedEdges = (p.closure && p.closure.edges) || [];
  S.closedMarker = p.closure ? p.closure.edge : null;
  S.closedStart = (p.closure && p.closure.start) || 0;
  S.closedEnd = (p.closure && p.closure.end) || 0;
  S.scenarioInfo = null;
  if (p.scenario && p.scenario !== 'baseline') {
    const base = S.runsList.find(r => r.params && r.params.scenario === 'baseline'
      && r.params.scale === p.scale && r.params.begin === p.begin && r.params.end === p.end);
    let bm = null;
    if (base) bm = ((await api.getMeta(base.run_id)).stats || {}).metrics;
    S.scenarioInfo = { name: p.scenario, m: mt, bm };
  }
  renderScenario();

  await loadHotspots(id);
  stopFollow(true);
  if (Q.get('follow') && !S.windowed) S.follow = Q.get('follow');
  updateUrl({ run: id });
  hud.drawTimeline();
  hud.setLoading(null);
}

function renderScenario() {
  if (!S.scenarioInfo) { hud.setScenario(null); return; }
  hud.setScenario(S.scenarioInfo, scenarioStatusHtml());
}
function scenarioStatusHtml() {
  if (!S.scenarioInfo) return '';
  const bridge = S.scenarioInfo.name.replace(/^close_/, '').replace(/_/g, ' ');
  const now = S.begin + S.T;
  if (now < S.closedStart) return `<span style="color:#fbbf24">${bridge} — closes ${hm(S.closedStart)}</span>`;
  if (!S.closedEnd || now < S.closedEnd) return `<span style="color:#f87171">✕ ${bridge} closed</span>`;
  return `<span style="color:#34d399">${bridge} — reopened ${hm(S.closedEnd)}</span>`;
}

// ---------------------------------------------------------------------------
function render() {
  const flow = S.zoom < LOD_Z;
  S.frame = (!flow && S.show.vehicles) ? interpAt(Math.min(S.tMax, S.T)) : [];
  overlay.setProps({ layers: buildLayers(deckgl) });
  hud.setClock(S.begin + S.T);
  if (flow && S.timeline && S.timeline.counts.length) {
    // no interpolated frame in flow view — read the precomputed timeline bin
    const i = Math.max(0, Math.min(S.timeline.counts.length - 1, Math.floor(S.T / S.timeline.bin)));
    hud.setStats({ active: S.timeline.counts[i] || 0, kmh: S.timeline.mean_kmh[i] || 0, stopped: NaN, buses: NaN });
  } else {
    hud.setStats(frameStats(S.frame));
  }
  hud.drawTimeline();
  if (S.scenarioInfo) hud.setScenarioStatus(scenarioStatusHtml());
  tickFollow(S.frame);
}

let last = 0, lastIdleRender = 0;
function tick(now) {
  if (S.playing && last) {
    S.T += (now - last) / 1000 * S.speed;
    if (S.T >= S.tMax) S.T = 0;
    ensureWindow();
    render();
  } else if (S.hotspotFocus && now - lastIdleRender > 80) {
    lastIdleRender = now;
    render(); // keep the pulse ring animating while paused (~12 fps is plenty)
  }
  last = now;
  requestAnimationFrame(tick);
}

// ---------------------------------------------------------------------------
const SPEEDS = [5, 15, 30, 60, 120, 240];

async function init() {
  const { style, source } = await loadBasemapStyle();
  if (source === 'positron') hud.toast('dark basemap unavailable — using light fallback');

  map = new window.maplibregl.Map({
    container: 'map',
    style,
    center: [+Q.get('lng') || -123.135, +Q.get('lat') || 49.262],
    zoom: +Q.get('zoom') || 13.2,
    pitch: +Q.get('pitch') || 0,
    attributionControl: false,
    antialias: true,
  });
  S.zoom = map.getZoom();
  overlay = new deckgl.MapboxOverlay({
    interleaved: false,
    layers: [],
    onClick: info => {
      if (info && info.layer && info.layer.id === 'veh' && info.object) {
        startFollow(info.object.vid);
      } else if (S.follow) stopFollow();
    },
    onHover: info => {
      if (info && info.object && (info.layer.id === 'flow-core' || info.layer.id === 'roads')) {
        const p = info.object.properties;
        const vol = S.volMap[p.id];
        hud.setTooltip({
          x: info.x, y: info.y,
          html: `<b>${p.name || p.class}</b><br>${p.lanes} lane${p.lanes > 1 ? 's' : ''} · ${Math.round(p.speed * 3.6)} km/h limit${vol ? ` · ${vol} veh` : ''}`,
        });
      } else hud.setTooltip(null);
    },
  });
  map.addControl(overlay);
  initFollow(map, render);
  initHotspots(map);

  map.on('zoom', () => { S.zoom = map.getZoom(); if (!S.playing) render(); });
  map.on('load', () => {
    addBuildings(map);
    setBuildingsVisible(map, S.show.buildings);
    if (S.pitch > 5) { map.easeTo({ pitch: S.pitch, duration: 0 }); hud.setTilted(true); }
  });

  hud.initHud({
    onPlayToggle: () => { S.playing = !S.playing; hud.setPlaying(S.playing); last = 0; },
    onScrub: t => { S.T = t; ensureWindow(); render(); },
    onSpeed: dir => {
      const i = SPEEDS.indexOf(S.speed);
      const ni = Math.max(0, Math.min(SPEEDS.length - 1, (i < 0 ? 2 : i) + dir));
      S.speed = SPEEDS[ni];
      hud.setSpeed(S.speed);
    },
    onRunChange: async id => { await loadRun(id); render(); },
    onTilt: () => hud.setTilted(toggleTilt(map)),
    onHotspotClick: rank => { focusHotspot(rank); render(); },
    onEscape: () => { if (S.follow) { stopFollow(); } else if (S.hotspotFocus) { S.hotspotFocus = null; hud.setHotspots(S.hotspots, null); render(); } },
  });
  hud.setPlaying(S.playing);
  hud.setSpeed(S.speed);
  hud.buildLegend();
  hud.buildToggles(k => {
    if (k === 'buildings') setBuildingsVisible(map, S.show.buildings);
    render();
  });

  const runs = await api.getRuns();
  S.runsList = runs;
  const wantRun = +Q.get('run') || (runs[0] && runs[0].run_id) || 1;
  hud.setRuns(runs, wantRun);
  await loadRun(wantRun);

  render();
  requestAnimationFrame(tick);
  window.__overlay = overlay; // smoke-test hook
  window.__map = map;         // debug hook
  window.__APP_READY = true;  // screenshot/smoke hook
}

init().catch(e => {
  console.error(e);
  hud.setLoading(`init error: ${(e && e.message) || e}`);
});
