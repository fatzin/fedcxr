// Replay da execução aberta: existe enquanto o hash termina em /replay (ver routes.js) e anda sozinho enquanto toca.
import {computed, effect, signal} from '@preact/signals';
import {fetchRunRows} from './api.js';
import {DEFAULT_SPEED, advance, createReplay, pause, seek, togglePlaying} from './replay-core.js';
import {runHash} from './routes.js';
import {openRun, route} from './router.js';
import {baseRun, grid, run, targetNum} from './state.js';

export const replay = signal(null);  // estado de replay-core.js, sempre da execução aberta
export const replaying = computed(() => replay.value != null);
export const speed = signal(DEFAULT_SPEED);

// o mesmo nome de execução pode existir em grades diferentes
const idOf = (g, name) => runHash(g, name);
let loading = null;     // {id}: /api/run pedido; trocar de rota no meio descarta a resposta
let startAt = null;     // {id, k}: arrastar a barra sem replay abre o replay parado nesse ponto

effect(() => {
  const deep = route.value.deep, base = baseRun.value;
  const want = deep?.replay && base?.name === deep.name ? base : null;
  if (!want) { loading = startAt = null; if (replay.peek()) replay.value = null; return; }
  const id = idOf(deep.grid, deep.name);
  if (replay.peek()?.id === id || loading?.id === id) return;
  replay.value = null;
  load(deep.grid, want, id);
});

async function load(g, base, id) {
  const token = loading = {id};
  // sem o /api/run o replay ainda mostra as curvas, só sem os números por hospital
  const rows = await fetchRunRows(g, base.name).catch(() => base.rows);
  if (loading !== token) return;
  const opts = startAt?.id === id ? {k: startAt.k, playing: false} : {};
  loading = startAt = null;
  replay.value = createReplay(id, rows, targetNum.peek(), opts);
  if (replay.value.playing) playLoop();
}

// rAF para de disparar com a aba oculta; o setTimeout mantém o replay andando nesse caso.
function nextFrame(fn) {
  let done = false;
  const once = () => { if (!done) { done = true; fn(); } };
  requestAnimationFrame(once); setTimeout(once, 50);
}

let loopId = 0;
function playLoop() {
  const id = ++loopId;
  let last = performance.now();
  const step = () => {
    const rp = replay.peek();
    if (id !== loopId || !rp?.playing) return;
    const now = performance.now();
    replay.value = advance(rp, now - last, +speed.peek(), now);
    last = now;
    nextFrame(step);
  };
  nextFrame(step);
}

export function togglePlay() {
  const rp = replay.peek();
  if (!rp) { if (run.peek()) openRun(run.peek(), true); return; }
  replay.value = togglePlaying(rp);
  if (replay.value.playing) playLoop();
}

export const stopReplay = () => openRun(run.peek());

// arrastar a barra segue o dedo 1:1 e pausa; soltar não retoma sozinho
export function scrubStart(value) {
  const rp = replay.peek();
  if (rp) { replay.value = pause(rp); return; }
  if (!run.peek()) return;
  startAt = {id: idOf(grid.peek(), run.peek()), k: +value || 1};
  openRun(run.peek(), true);
}
export function scrubTo(value) {
  const rp = replay.peek();
  if (rp) replay.value = seek(rp, +value);
  else if (startAt) startAt = {...startAt, k: +value || 1};
  else scrubStart(value);  // setas do teclado na barra, sem replay aberto
}

addEventListener('keydown', e => {
  if (route.peek().view !== 'live' || e.target.closest('input, select, textarea, button, a, summary')) return;
  if (e.key === ' ' && !e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); togglePlay(); }
  if (e.key === 'Escape' && replay.peek()) stopReplay();
});
