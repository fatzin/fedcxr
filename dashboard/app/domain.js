// Vocabulário do experimento: métodos, níveis, classes, estados das execuções e das GPUs, e contas de uma execução.
import {mean} from './stats.js';

const METHOD_NAMES = {'fedavg-full': 'FedAvg', 'fedavg-lora': 'FedAvg + LoRA', 'fedprox-full': 'FedProx', 'scaffold-full': 'SCAFFOLD',
  'fedprox-lora': 'FedProx + LoRA', 'scaffold-lora': 'SCAFFOLD + LoRA',
  'scaffold-full-cweighted': 'SCAFFOLD (c ponderado)', 'scaffold-full-uniform': 'SCAFFOLD (uniforme)', 'scaffold-full-clip': 'SCAFFOLD (recorte)'};
export const mName = m => {
  if (METHOD_NAMES[m]) return METHOD_NAMES[m];
  let x = m.match(/^(.*)-mu([\d.e-]+)$/); if (x) return `${mName(x[1])} · μ ${x[2].replace('.', ',')}`;
  x = m.match(/^(.*)-r(\d+)$/); if (x) return `${mName(x[1])} · r ${x[2]}`;
  return m;
};

const HET_NAMES = {'IID': 'IID (sem heterogeneidade)', 'α=1.0': 'α = 1,0 · leve', 'α=0.5': 'α = 0,5 · moderada', 'α=0.3': 'α = 0,3 · forte',
  'α=0.2': 'α = 0,2 · forte', 'α=0.15': 'α = 0,15 · muito forte', 'α=0.1': 'α = 0,1 · extrema'};
export const hName = h => HET_NAMES[h] || h.replace('α=', 'α = ').replace('.', ',');
export const hShort = h => h.replace('α=', 'α ').replace('.', ',');
export const HET_ORDER = h => h === 'IID' ? 1e9 : parseFloat((h.match(/α=([\d.]+)/) || [0, -1])[1]);
export const byHet = (a, b) => HET_ORDER(b) - HET_ORDER(a);

// índice = rótulo do modelo; a cor de cada classe é o token --c<índice>
export const CLASSES = [{name: 'Normal', long: 'Normal'}, {name: 'Bacteriana', long: 'Pneumonia bacteriana'},
  {name: 'Viral', long: 'Pneumonia viral'}];

export const STATUS = {running: ['Treinando', 'ok'], paused: ['Pausada · calor', 'warn'], stalled: ['Parada', 'bad'],
  done: ['Concluída', 'neutral'], error: ['Erro', 'bad']};
export const active = r => r.status === 'running' || r.status === 'paused' || r.status === 'stalled';
export const runLabel = r => `${mName(r.method)} · ${hName(r.het)}`;
export const variesLr = runs => new Set(runs.map(r => r.lr)).size > 1;

export const lastRound = r => r.rows.at(-1)?.round ?? 0;
export const progress = r => lastRound(r) / r.max_rounds;
export const bestVal = r => r.rows.length ? Math.max(...r.rows.map(x => x.val_bacc)) : null;
const recentSec = r => r.rows.length ? mean(r.rows.slice(-5).map(x => x.sec)) : 0;
export const secLeft = r => (r.max_rounds - lastRound(r)) * recentSec(r);

export const liveGridsOf = grids => grids.filter(g => g.runs.some(active)).map(g => g.grid);

// Grade mostrada: a escolhida, senão a atualizada por último (e a que está rodando, se a atual não estiver).
export function chooseGrid(grids, current, picked) {
  const live = liveGridsOf(grids);
  if (grids.some(g => g.grid === current) && (picked || !live.length || live.includes(current))) return current;
  const last = g => Math.max(0, ...g.runs.map(r => r.updated || 0));
  return [...grids].sort((a, b) => last(b) - last(a))[0]?.grid ?? null;
}

// Execução mostrada: a escolhida, senão a que está treinando, a em andamento ou a atualizada por último.
export function chooseRun(runs, current, picked) {
  if (picked && runs.some(r => r.name === current)) return current;
  const latest = [...runs].sort((a, b) => (b.updated || 0) - (a.updated || 0))[0];
  return (runs.find(r => r.status === 'running') || runs.find(active) || latest)?.name ?? null;
}

const LIMITS = {none: ['Livre', 'ok', 'Sem redução de clock.'], idle: ['Ociosa', 'neutral', 'Sem trabalho no momento.'],
  power: ['Limitada por energia', 'neutral', 'Bateu no teto de consumo. Normal sob carga total.'],
  thermal: ['Limitada por calor', 'warn', 'O driver reduziu o clock para conter a temperatura (thermal throttling).'],
  hw_thermal: ['Calor crítico', 'bad', 'Redução forte por temperatura no limite. Verifique a refrigeração.'],
  hw: ['Redução de hardware', 'bad', 'A placa reduziu o clock por proteção de hardware.']};
export const limitOf = g => LIMITS[g.limit] || LIMITS.none;

export const GUARD_EVENTS = {pause: ['Pausa', 'warn'], resume: ['Retomada', 'ok'], error: ['Erro', 'bad'], info: ['Info', 'neutral']};

const TEMP_WARN = 80, NEAR_PAUSE = 3;  // °C
export const tempLevel = (temp, hot) => temp >= hot - NEAR_PAUSE ? 'bad' : temp >= TEMP_WARN ? 'warn' : '';
export const clockPct = g => 100 * g.clock / (g.clock_max || 1);

// só o fim do endereço PCI (0000:01:00.0): a largura do domínio muda de uma ferramenta para outra
const sameBus = (a, b) => a.slice(-12) === b.slice(-12);
export const procsOn = (data, g) => data.procs.filter(p => sameBus(p.bus, g.bus));

// GPU em que a execução roda: pelo pid na lista de processos, senão pelo barramento gravado no status.
export function gpuOfRun(data, r) {
  const bus = data.procs.find(p => p.pid === r.pid)?.bus ?? r.gpu_bus;
  return bus ? data.gpus.find(g => sameBus(g.bus, bus)) ?? null : null;
}

// now: relógio do servidor (/api/state time), o mesmo dos eventos
export function guardStats(G, now) {
  const open = {};
  let pausedSec = 0, p1h = 0, p24 = 0;
  const dayAgo = now - 86400, inDay = t => Math.max(t, dayAgo);
  for (const e of G.events) {
    if (e.kind === 'pause') { open[e.gpu] = e.t; if (now - e.t < 3600) p1h++; if (e.t > dayAgo) p24++; }
    if (e.kind === 'resume' && open[e.gpu] != null) { if (e.t > dayAgo) pausedSec += e.t - inDay(open[e.gpu]); delete open[e.gpu]; }
  }
  for (const k in open) pausedSec += now - inDay(open[k]);
  return {p1h, p24, pausedSec, openGpus: Object.keys(open).map(Number)};
}
