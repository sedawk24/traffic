// Dark-cinematic basemap: use openfreemap's hosted dark style if it exists,
// else fetch positron's style JSON and recolor it to the app palette at
// runtime (no tile re-hosting needed — same vector tiles, darker paint).
const DARK_URL = 'https://tiles.openfreemap.org/styles/dark';
const POSITRON_URL = 'https://tiles.openfreemap.org/styles/positron';

const GROUND = '#0a0e13';
const WATER = '#0d1722';
const PARK = '#0f1a17';
const LANDUSE = '#0c1218';
const ROAD_CASING = '#161e28';
const ROAD_MINOR = '#222c38';
const ROAD_MAJOR = '#2b3645';
const ROAD_HIGHWAY = '#344153';
const RAIL = '#1d2733';
const BOUNDARY = '#243140';
const BUILDING = '#111923';
const TEXT = '#5f7488';
const TEXT_HALO = '#0a0e13';

const HIDE = /poi|housenumber|house_num|shield|oneway|ferry|aeroway[-_]?(label|text)|airport[-_]label/i;
const IS_WATER = /water|ocean|river|lake/i;
const IS_PARK = /park|green|wood|grass|cemetery|pitch|garden|zoo|landcover/i;
const IS_BUILDING = /building/i;
const IS_RAIL = /rail|transit/i;
const IS_BOUNDARY = /boundary|admin/i;
const IS_CASING = /casing|outline/i;
const IS_MAJOR = /motorway|trunk|primary|highway[-_]?major|major[-_]?road/i;
const IS_MINOR = /minor|service|track|path|street|secondary|tertiary|road|bridge|tunnel|link/i;

function paint(layer, key, value) {
  layer.paint = layer.paint || {};
  layer.paint[key] = value;
}

export function recolorToDark(style) {
  style.layers = (style.layers || []).filter(l => !HIDE.test(l.id));
  for (const l of style.layers) {
    try {
      const id = l.id || '';
      if (l.type === 'background') paint(l, 'background-color', GROUND);
      else if (l.type === 'fill') {
        if (IS_WATER.test(id)) paint(l, 'fill-color', WATER);
        else if (IS_PARK.test(id)) paint(l, 'fill-color', PARK);
        else if (IS_BUILDING.test(id)) {
          paint(l, 'fill-color', BUILDING);
          paint(l, 'fill-opacity', 0.85);
        } else paint(l, 'fill-color', LANDUSE);
        if (l.paint && 'fill-outline-color' in l.paint) paint(l, 'fill-outline-color', GROUND);
      } else if (l.type === 'line') {
        if (IS_WATER.test(id)) paint(l, 'line-color', WATER);
        else if (IS_BOUNDARY.test(id)) paint(l, 'line-color', BOUNDARY);
        else if (IS_RAIL.test(id)) paint(l, 'line-color', RAIL);
        else if (IS_CASING.test(id)) paint(l, 'line-color', ROAD_CASING);
        else if (IS_MAJOR.test(id)) paint(l, 'line-color', ROAD_MAJOR);
        else if (IS_MINOR.test(id)) paint(l, 'line-color', ROAD_MINOR);
        else paint(l, 'line-color', ROAD_CASING);
        if (/motorway|trunk/.test(id) && !IS_CASING.test(id)) paint(l, 'line-color', ROAD_HIGHWAY);
      } else if (l.type === 'symbol') {
        paint(l, 'text-color', TEXT);
        paint(l, 'text-halo-color', TEXT_HALO);
        paint(l, 'text-halo-width', 1.1);
        if (l.layout && l.layout['icon-image']) paint(l, 'icon-opacity', 0);
      }
    } catch (_e) { /* a stubborn layer keeps its positron paint — fine */ }
  }
  return style;
}

export async function loadBasemapStyle() {
  try {
    const r = await fetch(DARK_URL);
    if (r.ok) {
      const s = await r.json();
      if (s && s.layers && s.layers.length) return { style: s, source: 'openfreemap-dark' };
    }
  } catch (_e) { /* fall through to recolor */ }
  try {
    const r = await fetch(POSITRON_URL);
    const s = await r.json();
    return { style: recolorToDark(s), source: 'positron-recolored' };
  } catch (_e) {
    console.warn('basemap: falling back to stock positron (style fetch failed)');
    return { style: POSITRON_URL, source: 'positron' };
  }
}
