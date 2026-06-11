// Vehicle sprite atlas v2 — top-down silhouettes drawn on a canvas, used as a
// tint mask (alpha = shape, color via getColor). Cells are 128px; vehicles are
// drawn pointing "up" at a common scale so meters sizing stays street-true.
const CELL = 128;

// vehicle occupies this fraction of the cell height; getSize (meters) must be
// real length / SPRITE_FRAC so the drawn body spans its true length.
export const SPRITE_FRAC = 0.8;
export const SIZE_M = { car: 4.6 / SPRITE_FRAC, bus: 12.0 / SPRITE_FRAC, truck: 10.5 / SPRITE_FRAC, rail: 30 / SPRITE_FRAC };

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.roundRect(x, y, w, h, r);
  g.fill();
}

function drawCar(g, cx) {
  const w = 46, h = CELL * SPRITE_FRAC, x = cx - w / 2, y = (CELL - h) / 2;
  g.globalAlpha = 1;
  roundRect(g, x, y, w, h, 14);                       // body
  g.globalAlpha = 0.45;
  roundRect(g, x + 6, y + h * 0.22, w - 12, h * 0.16, 5);  // windshield
  roundRect(g, x + 7, y + h * 0.72, w - 14, h * 0.12, 5);  // rear window
  g.globalAlpha = 0.7;
  roundRect(g, x + 8, y + h * 0.40, w - 16, h * 0.30, 6);  // roof
  g.globalAlpha = 1;
}

function drawBus(g, cx) {
  const w = 40, h = CELL * SPRITE_FRAC, x = cx - w / 2, y = (CELL - h) / 2;
  g.globalAlpha = 1;
  roundRect(g, x, y, w, h, 8);
  g.globalAlpha = 0.45;
  roundRect(g, x + 5, y + 5, w - 10, 10, 4);          // front window band
  g.globalAlpha = 0.75;
  roundRect(g, x + 5, y + 20, w - 10, h - 32, 4);     // roof
  g.globalAlpha = 0.4;
  for (let i = 0; i < 4; i++)                         // roof hatches
    roundRect(g, x + 10, y + 30 + i * (h - 50) / 3, w - 20, 6, 3);
  g.globalAlpha = 1;
}

function drawTruck(g, cx) {
  const w = 44, h = CELL * SPRITE_FRAC, x = cx - w / 2, y = (CELL - h) / 2;
  g.globalAlpha = 1;
  roundRect(g, x + 4, y, w - 8, h * 0.24, 8);         // cab
  g.globalAlpha = 0.5;
  roundRect(g, x + 8, y + 4, w - 16, 8, 3);           // windshield
  g.globalAlpha = 0.95;
  roundRect(g, x, y + h * 0.28, w, h * 0.72, 5);      // box
  g.globalAlpha = 1;
}

function drawVan(g, cx) {
  const w = 42, h = CELL * SPRITE_FRAC * 0.72, x = cx - w / 2, y = (CELL - h) / 2;
  g.globalAlpha = 1;
  roundRect(g, x, y, w, h, 10);
  g.globalAlpha = 0.45;
  roundRect(g, x + 5, y + 6, w - 10, 10, 4);
  g.globalAlpha = 0.85;
  roundRect(g, x + 5, y + 22, w - 10, h - 28, 5);
  g.globalAlpha = 1;
}

export function buildAtlas() {
  const cv = document.createElement('canvas');
  cv.width = CELL * 4;
  cv.height = CELL;
  const g = cv.getContext('2d');
  g.fillStyle = '#fff';
  drawCar(g, CELL * 0.5);
  drawBus(g, CELL * 1.5);
  drawTruck(g, CELL * 2.5);
  drawVan(g, CELL * 3.5);
  const cellDef = i => ({
    x: i * CELL, y: 0, width: CELL, height: CELL,
    anchorX: CELL / 2, anchorY: CELL / 2, mask: true,
  });
  return {
    url: cv.toDataURL(),
    mapping: { car: cellDef(0), bus: cellDef(1), truck: cellDef(2), van: cellDef(3), rail: cellDef(1) },
  };
}

// stable per-vehicle tint: jitter the class base color by a hash of the id
export function hueJitter(base, vid) {
  let h = 2166136261;
  for (let i = 0; i < vid.length; i++) { h ^= vid.charCodeAt(i); h = Math.imul(h, 16777619); }
  const f = ((h >>> 8) % 1000) / 1000 - 0.5; // -0.5 .. 0.5
  const k = 0.35;
  return [
    Math.max(0, Math.min(255, Math.round(base[0] * (1 + k * f)))),
    Math.max(0, Math.min(255, Math.round(base[1] * (1 + k * -f)))),
    Math.max(0, Math.min(255, Math.round(base[2] * (1 - k * f * 0.5)))),
  ];
}
