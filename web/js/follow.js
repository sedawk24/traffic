// Follow-vehicle mode: click a vehicle to chase-cam it; Esc (or the vehicle
// finishing its trip) exits. On start the camera eases to the vehicle once;
// during playback it lerps after it each rendered frame. While paused there is
// deliberately NO per-frame camera work (software-GL friendly).
import { S } from './state.js';
import { updateUrl } from './config.js';
import { setFollowChip, toast } from './hud.js';

let map = null;
let requestRender = () => {};
let missFrames = 0;

export function initFollow(m, onNeedRender) {
  map = m;
  if (onNeedRender) requestRender = onNeedRender;
}

export function startFollow(vid) {
  S.follow = vid;
  missFrames = 0;
  updateUrl({ follow: vid });
  const v = S.frame.find(d => d.vid === vid);
  if (v) {
    map.easeTo({
      center: v.position,
      zoom: Math.max(map.getZoom(), 16.2),
      duration: 700,
    });
    map.once('moveend', () => requestRender());
  }
  requestRender();
}

export function stopFollow(silent = false) {
  if (!S.follow) return;
  S.follow = null;
  S.followPos = null;
  updateUrl({ follow: null });
  setFollowChip(null);
  if (!silent) toast('follow ended');
}

// called from render() with the interpolated vehicle list
export function tickFollow(frame) {
  if (!S.follow || !map) return;
  const v = frame.find(d => d.vid === S.follow);
  if (!v) {
    // windowed reloads can briefly drop the vehicle; give it a moment
    if (++missFrames > 90) { stopFollow(true); toast('vehicle finished its trip'); }
    return;
  }
  missFrames = 0;
  S.followPos = v.position;
  setFollowChip(v);
  if (!S.playing || map.isEasing()) return; // camera chases only during playback
  const c = map.getCenter();
  const dx = v.position[0] - c.lng, dy = v.position[1] - c.lat;
  if (Math.abs(dx) < 5e-7 && Math.abs(dy) < 5e-7) return;
  const k = 0.16; // ease factor: smooth chase without rubber-banding
  map.jumpTo({ center: [c.lng + dx * k, c.lat + dy * k] });
}
