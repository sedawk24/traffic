// 3D building extrusions from the basemap's own vector tiles (OpenMapTiles
// `building` source-layer), plus the pitch toggle. Vehicles/overlay draw on
// top (interleaved:false) — acceptable: at 55° pitch the streets stay readable.
import { BLD_Z } from './config.js';
import { S } from './state.js';

const LAYER_ID = 'sim-3d-buildings';

export function addBuildings(map) {
  if (map.getLayer(LAYER_ID)) return;
  const style = map.getStyle();
  const srcId = Object.keys(style.sources || {}).find(s => style.sources[s].type === 'vector');
  if (!srcId) { console.warn('buildings: no vector source in basemap style'); return; }
  // insert under the first symbol layer so labels stay on top
  const firstSymbol = (style.layers || []).find(l => l.type === 'symbol');
  try {
    map.addLayer({
      id: LAYER_ID,
      source: srcId,
      'source-layer': 'building',
      type: 'fill-extrusion',
      minzoom: BLD_Z,
      paint: {
        'fill-extrusion-color': '#17222e',
        'fill-extrusion-opacity': 0.88,
        'fill-extrusion-height': [
          'coalesce', ['get', 'render_height'],
          ['*', ['coalesce', ['get', 'levels'], 3], 3.2],
        ],
        'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
      },
    }, firstSymbol && firstSymbol.id);
  } catch (e) {
    console.warn('buildings: extrusion layer failed', e);
  }
}

export function setBuildingsVisible(map, on) {
  if (map.getLayer(LAYER_ID)) map.setLayoutProperty(LAYER_ID, 'visibility', on ? 'visible' : 'none');
}

export function toggleTilt(map) {
  const tilted = map.getPitch() > 5;
  map.easeTo({ pitch: tilted ? 0 : 55, duration: 900 });
  S.pitch = tilted ? 0 : 55;
  return !tilted;
}
