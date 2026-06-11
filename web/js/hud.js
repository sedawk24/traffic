// HUD chrome: top bar (brand / run / clock / transport controls), right rail
// (Stats, Hotspots, Layers, Legend, Scenario cards), bottom timeline with an
// active-vehicle histogram, hover tooltip, toasts, keyboard shortcuts.
import {
  AREA_LABEL, ZCOL, ZONE_LABELS, css, hms, hm, congColor, volColor, updateUrl,
} from './config.js';
import { S } from './state.js';

const $ = sel => document.querySelector(sel);
let hooks = {}; // {onScrub, onPlayToggle, onSpeed, onRunChange, onTilt, onHotspotClick}

export function initHud(h) {
  hooks = h;
  document.body.insertAdjacentHTML('beforeend', `
  <header id="topbar">
    <div class="brand"><span class="pulse-dot"></span><b>VANCOUVER</b><span class="thin">TRAFFIC</span></div>
    <span class="chip" id="areachip">—</span>
    <select id="runsel" title="run"></select>
    <div class="grow"></div>
    <div id="clockwrap"><span id="clock">07:00:00</span><span id="daypart">AM PEAK</span></div>
    <div class="grow"></div>
    <div class="controls">
      <button id="play" class="btn-accent" title="space">⏸</button>
      <div class="speed"><button id="spdn" title="↓">−</button><span id="spdv">30×</span><button id="spup" title="↑">+</button></div>
      <button id="tilt" title="3D tilt">3D</button>
      <button id="railtoggle" title="panels">☰</button>
    </div>
  </header>

  <aside id="rail">
    <section class="card" id="statscard">
      <h4>Live</h4>
      <div class="stats">
        <div><b id="st-active">0</b><span>on road</span></div>
        <div><b id="st-kmh">—</b><span>mean km/h</span></div>
        <div><b id="st-stop">—</b><span>stopped</span></div>
        <div><b id="st-bus">0</b><span>buses</span></div>
      </div>
    </section>
    <section class="card" id="scenariocard" style="display:none"><h4>Scenario</h4><div id="scenariobody"></div></section>
    <section class="card" id="hotspotcard">
      <h4>Worst intersections <span class="hint" id="hotspot-hint"></span></h4>
      <div id="hotspotlist" class="hotlist"></div>
    </section>
    <section class="card">
      <h4>Layers</h4>
      <div id="toggles" class="toggles"></div>
    </section>
    <section class="card" id="legendcard"><h4>Legend</h4><div id="legend"></div></section>
  </aside>

  <footer id="timeline">
    <canvas id="tlcanvas"></canvas>
    <div id="tlcursor"></div>
  </footer>

  <div id="tooltip"></div>
  <div id="followchip" style="display:none"></div>
  <div id="toast"></div>
  <div id="loading"><div class="spinner"></div><span id="loadingmsg">Loading network &amp; trace…</span></div>`);

  $('#play').onclick = () => hooks.onPlayToggle();
  $('#spup').onclick = () => hooks.onSpeed(+1);
  $('#spdn').onclick = () => hooks.onSpeed(-1);
  $('#tilt').onclick = () => hooks.onTilt();
  $('#railtoggle').onclick = () => document.getElementById('rail').classList.toggle('hidden');
  $('#runsel').onchange = e => hooks.onRunChange(+e.target.value);

  const tl = $('#tlcanvas');
  let scrubbing = false;
  const scrubTo = ev => {
    const r = tl.getBoundingClientRect();
    const f = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
    hooks.onScrub(f * S.tMax);
  };
  tl.addEventListener('pointerdown', e => { scrubbing = true; tl.setPointerCapture(e.pointerId); scrubTo(e); });
  tl.addEventListener('pointermove', e => { if (scrubbing) scrubTo(e); });
  tl.addEventListener('pointerup', () => { scrubbing = false; });

  window.addEventListener('keydown', e => {
    if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault(); hooks.onPlayToggle(); }
    else if (e.key === 'ArrowRight') hooks.onScrub(Math.min(S.tMax, S.T + 30));
    else if (e.key === 'ArrowLeft') hooks.onScrub(Math.max(0, S.T - 30));
    else if (e.key === 'ArrowUp') { e.preventDefault(); hooks.onSpeed(+1); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); hooks.onSpeed(-1); }
    else if (e.key === 'Escape') hooks.onEscape && hooks.onEscape();
  });
  window.addEventListener('resize', () => sizeTimeline());
  sizeTimeline();
}

export function setLoading(msg) {
  const el = $('#loading');
  if (msg === null) { el.style.display = 'none'; return; }
  el.style.display = 'flex';
  $('#loadingmsg').innerHTML = msg;
}

export function toast(msg, ms = 2600) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), ms);
}

export function setRuns(runs, current) {
  $('#runsel').innerHTML = runs.map(r => {
    const p = r.params || {};
    const tag = p.area || 'peninsula';
    return `<option value="${r.run_id}" ${r.run_id === current ? 'selected' : ''}>#${r.run_id} ${p.name || 'run'} · ${tag}</option>`;
  }).join('');
}

export function setArea(area) { $('#areachip').textContent = AREA_LABEL[area] || area; }

export function setPlaying(playing) { $('#play').textContent = playing ? '⏸' : '▶'; }
export function setSpeed(v) { $('#spdv').textContent = `${v}×`; }
export function setTilted(on) { $('#tilt').classList.toggle('on', on); }

export function setClock(sec) {
  $('#clock').textContent = hms(sec);
  const h = sec / 3600;
  $('#daypart').textContent =
    h < 6 ? 'NIGHT' : h < 9.5 ? 'AM PEAK' : h < 15 ? 'MIDDAY' : h < 18.5 ? 'PM PEAK' : 'EVENING';
}

export function setStats(st) {
  $('#st-active').textContent = st.active.toLocaleString();
  $('#st-kmh').textContent = isFinite(st.kmh) && st.kmh ? st.kmh.toFixed(0) : '—';
  $('#st-kmh').style.color = isFinite(st.kmh) && st.kmh ? css(congColor(st.kmh / 3.6)) : '';
  $('#st-stop').textContent = isFinite(st.stopped) ? `${st.stopped.toFixed(0)}%` : '—';
  $('#st-bus').textContent = isFinite(st.buses) ? st.buses : '—';
}

export function buildToggles(onChange) {
  $('#toggles').innerHTML = Object.keys(S.show).map(k =>
    `<label><input type="checkbox" data-k="${k}" ${S.show[k] ? 'checked' : ''}><span>${k}</span></label>`
  ).join('');
  document.querySelectorAll('#toggles input').forEach(cb => {
    cb.onchange = e => { S.show[e.target.dataset.k] = e.target.checked; onChange(e.target.dataset.k); };
  });
}

export function buildLegend() {
  const zon = Object.keys(ZONE_LABELS).map(k =>
    `<div class="row"><span class="sw" style="background:${css(ZCOL[k])}"></span>${ZONE_LABELS[k]}</div>`).join('');
  $('#legend').innerHTML =
    `<div class="ramp" style="background:linear-gradient(90deg,${css(congColor(0))},${css(congColor(5.5))},${css(congColor(11))})"></div>
     <div class="row spread muted"><span>stopped</span><span>vehicles</span><span>free flow</span></div>
     <div class="ramp" style="background:linear-gradient(90deg,${css(volColor(0, 180))},${css(volColor(60, 180))},${css(volColor(180, 180))})"></div>
     <div class="row spread muted"><span>quiet</span><span>road flow</span><span>busy</span></div>
     <div class="row muted" style="margin-top:6px"><span class="dot" style="background:#34d399"></span><span class="dot" style="background:#fbbf24"></span><span class="dot" style="background:#f43f5e"></span> live signals · zoom in</div>
     ${zon}
     <div class="row muted"><span class="swl" style="background:rgba(184,120,52,.55)"></span>bus routes · <span class="dot" style="background:#f43f5e"></span> gateways</div>`;
}

// ---- hotspots card ---------------------------------------------------------
export function setHotspots(hs, focusRank) {
  const list = $('#hotspotlist'), hint = $('#hotspot-hint');
  if (!hs || !hs.hotspots || !hs.hotspots.length) {
    hint.textContent = '';
    list.innerHTML = `<div class="muted pad">No diagnosis for this run yet — run<br><code>sim diagnose --run &lt;name&gt;</code></div>`;
    return;
  }
  hint.textContent = `top ${Math.min(10, hs.hotspots.length)} · ${hs.total_stop_veh_h.toLocaleString()} veh·h stopped`;
  list.innerHTML = hs.hotspots.slice(0, 10).map(h => `
    <div class="hot ${focusRank === h.rank ? 'sel' : ''}" data-rank="${h.rank}">
      <span class="rank">${h.rank}</span>
      <span class="name">${h.name}<small>${h.cov_kind ? h.cov_kind : (h.tls_id ? 'signal (unverified)' : 'priority junction')}</small></span>
      <span class="val">${h.stop_veh_h}<small>veh·h</small></span>
    </div>`).join('');
  list.querySelectorAll('.hot').forEach(el => {
    el.onclick = () => hooks.onHotspotClick(+el.dataset.rank);
  });
}

// ---- scenario card ---------------------------------------------------------
export function setScenario(info, statusHtml) {
  const card = $('#scenariocard'), body = $('#scenariobody');
  if (!info) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  let html = `<div id="scnstatus">${statusHtml || ''}</div>`;
  if (info.bm && info.m) {
    const d = (a, b, suf) => {
      const x = a - b, s = x >= 0 ? '+' : '';
      return `<span style="color:${x > 0 ? '#f87171' : '#34d399'}">${s}${x.toFixed(0)}${suf}</span>`;
    };
    const row = (lab, a, b, suf) =>
      `<tr><td>${lab}</td><td>${b.toFixed(0)}${suf}</td><td>${a.toFixed(0)}${suf}</td><td>${d(a, b, suf)}</td></tr>`;
    html += `<table><tr class="muted"><td></td><td>base</td><td>closed</td><td>Δ</td></tr>
      ${row('travel', info.m.avg_duration, info.bm.avg_duration, 's')}
      ${row('wait', info.m.avg_wait, info.bm.avg_wait, 's')}
      ${row('done', info.m.completed, info.bm.completed, '')}</table>`;
  }
  body.innerHTML = html;
}
export function setScenarioStatus(html) {
  const el = $('#scnstatus');
  if (el) el.innerHTML = html;
}

// ---- timeline --------------------------------------------------------------
let tlW = 0, tlH = 0, dpr = 1;
function sizeTimeline() {
  const cv = $('#tlcanvas');
  if (!cv) return;
  dpr = window.devicePixelRatio || 1;
  tlW = cv.clientWidth; tlH = cv.clientHeight;
  cv.width = tlW * dpr; cv.height = tlH * dpr;
  drawTimeline();
}

export function drawTimeline() {
  const cv = $('#tlcanvas');
  if (!cv || !tlW) return;
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, tlW, tlH);
  const tl = S.timeline;
  const padT = 14, padB = 16, plotH = tlH - padT - padB;
  // histogram
  if (tl && tl.counts && tl.counts.length) {
    const n = tl.counts.length, maxC = Math.max(...tl.counts, 1);
    const bw = tlW / n;
    const playedX = (S.T / Math.max(1, S.tMax)) * tlW;
    for (let i = 0; i < n; i++) {
      const h = Math.max(1.5, (tl.counts[i] / maxC) * plotH);
      const x = i * bw;
      const col = congColor((tl.mean_kmh[i] || 0) / 3.6);
      const played = x <= playedX;
      g.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${played ? 0.85 : 0.28})`;
      g.fillRect(x + 0.5, padT + plotH - h, Math.max(1, bw - 1.5), h);
    }
  } else {
    g.fillStyle = 'rgba(140,160,180,.15)';
    g.fillRect(0, padT + plotH - 2, tlW * (S.tMax ? 1 : 0), 2);
  }
  // hour ticks
  g.fillStyle = 'rgba(150,170,190,.55)';
  g.font = '10px system-ui';
  g.textAlign = 'center';
  const t0 = S.begin, t1 = S.begin + S.tMax;
  for (let hsec = Math.ceil(t0 / 1800) * 1800; hsec <= t1; hsec += 1800) {
    const x = ((hsec - t0) / Math.max(1, S.tMax)) * tlW;
    const isHour = hsec % 3600 === 0;
    g.fillStyle = isHour ? 'rgba(150,170,190,.5)' : 'rgba(150,170,190,.22)';
    g.fillRect(x, padT - 4, 1, plotH + 6);
    if (isHour) { g.fillStyle = 'rgba(170,190,210,.75)'; g.fillText(hm(hsec), x, tlH - 4); }
  }
  // cursor
  const cx = (S.T / Math.max(1, S.tMax)) * tlW;
  $('#tlcursor').style.left = `${cx}px`;
}

// ---- tooltip ---------------------------------------------------------------
export function setTooltip(info) {
  const el = $('#tooltip');
  if (!info) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.style.left = `${info.x + 14}px`;
  el.style.top = `${info.y + 14}px`;
  el.innerHTML = info.html;
}

// ---- follow chip -----------------------------------------------------------
export function setFollowChip(v) {
  const el = $('#followchip');
  if (!v) { el.style.display = 'none'; return; }
  el.style.display = 'flex';
  el.innerHTML = `<span class="dot" style="background:#22d3ee"></span>
    following <b>${v.cls}</b> · ${(v.speed * 3.6).toFixed(0)} km/h
    <span class="muted">esc to exit</span>`;
}
