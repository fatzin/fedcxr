// Estado compartilhado pelas telas: dados do servidor, grade e execução escolhidas e preferências da análise.
import {batch, computed, signal} from '@preact/signals';
import {fetchLaunchInfo, fetchState} from './api.js';
import {groupsOf, pickSeries, seriesOf} from './analysis.js';
import {chooseGrid, chooseRun, liveGridsOf} from './domain.js';
import {persisted} from './prefs.js';

export const data = signal(null);    // /api/state
export const launch = signal(null);  // /api/launch-info
export const conn = signal({text: 'Conectando…', off: false});

// "picked": escolhida pela pessoa (não troca sozinha para a grade que está rodando)
export const grid = signal(null);
const gridPicked = signal(false);
export const run = signal(null);
const runPicked = signal(false);

export const gridObj = computed(() => data.value?.grids.find(g => g.grid === grid.value) || {runs: [], expected: 0});
export const runs = computed(() => gridObj.value.runs.filter(r => r.status !== 'error'));
export const liveGrids = computed(() => new Set(liveGridsOf(data.value?.grids || [])));
export const baseRun = computed(() => runs.value.find(r => r.name === run.value) || null);
export const groups = computed(() => groupsOf(runs.value));
export const series = computed(() => seriesOf(groups.value));

function reconcile() {
  const D = data.value; if (!D) return;
  batch(() => {
    grid.value = chooseGrid(D.grids, grid.value, gridPicked.value);
    run.value = chooseRun(runs.value, run.value, runPicked.value);
  });
}

export function pickGrid(g) {
  batch(() => { grid.value = g; gridPicked.value = true; runPicked.value = false; reconcile(); });
}
export function pickRun(g, name) {
  batch(() => { grid.value = g; gridPicked.value = true; run.value = name; runPicked.value = true; reconcile(); });
}

const POLL_MS = 5000;

async function poll() {
  let next;
  try {
    next = await fetchState();
  } catch (e) {
    conn.value = {text: 'Sem conexão com o PC', off: true};
    return;
  }
  batch(() => {
    data.value = next;
    conn.value = {text: 'Ao vivo · ' + new Date().toLocaleTimeString('pt-BR'), off: false};
    reconcile();
  });
  if (!launch.value) launch.value = await fetchLaunchInfo().catch(() => null);  // sem resposta: tenta na próxima consulta
}

// a próxima consulta só sai depois da resposta da anterior, então elas não chegam fora de ordem
export async function startPolling() {
  await poll();
  setTimeout(startPolling, POLL_MS);
}

// Alvo de acurácia e série das curvas, salvos entre visitas. A série salva pode não existir na grade atual.
export const TARGET = {min: .05, max: .99, initial: '0.75'};
const analysisPrefs = persisted('fedcxr-ui3', s => ({method: s?.method ?? null, target: s?.target || TARGET.initial}));
export const target = computed(() => analysisPrefs.value.target);
export const clampTarget = t => Math.min(TARGET.max, Math.max(TARGET.min, t));
export const targetNum = computed(() => { const t = parseFloat(target.value); return Number.isFinite(t) ? clampTarget(t) : +TARGET.initial; });
export const curveSeries = computed(() => pickSeries(groups.value, analysisPrefs.value.method));
export const setTarget = value => { analysisPrefs.value = {...analysisPrefs.value, target: value}; };
export const setMethod = value => { analysisPrefs.value = {...analysisPrefs.value, method: value}; };
