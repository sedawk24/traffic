// Shared mutable app state (single instance, imported everywhere).
import { Q } from './config.js';

export const S = {
  // playback
  T: +Q.get('t') || 300,
  tMax: 0,
  begin: 25200,
  playing: Q.get('play') !== '0',
  speed: +Q.get('speed') || 30,

  // current run + area
  runId: null,
  runsList: [],
  area: null,
  meta: null,

  // per-area static data (cached in areaData)
  roads: null,
  zonesPoly: null,
  gateways: [],
  transitGeo: null,
  busSchedRaw: null,
  areaData: {},

  // per-run dynamic data
  trips: [],
  busTrips: [],
  allTrips: [],  // trips + busTrips, rebuilt ONLY when either changes — deck
                 // layers need a stable data reference or they re-upload buffers
                 // every frame
  volMap: {},
  volRef: 180,
  vehicles: 0,
  sigGroups: [],
  sigChangesMap: {},
  timeline: null,
  hotspots: null,

  // windowed streaming
  windowed: false,
  winLo: 0,
  winHi: -1,
  winBusy: false,
  nextWin: null, // prefetched {lo, hi, trips}

  // scenario (closure)
  closedEdges: [],
  closedMarker: null,
  closedStart: 0,
  closedEnd: 0,
  scenarioInfo: null,

  // interaction
  zoom: +Q.get('zoom') || 0,
  pitch: +Q.get('pitch') || 0,
  follow: Q.get('follow') || null,
  followPos: null,
  hotspotFocus: null,
  hover: null, // {x, y, html}
  frame: [],   // last interpolated vehicle frame
  stats: { active: 0, kmh: 0, stopped: 0 },

  show: {
    zones: true, roads: true, transit: true, vehicles: true,
    trails: true, congestion: true, signals: true, labels: true, buildings: true,
  },
};
