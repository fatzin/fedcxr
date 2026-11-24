// Contas das hipóteses e da grade: rodadas e bytes até o alvo, agrupamento por método e nível, tempo restante.
import {NA, lrTxt, nf} from './format.js';
import {active, byHet, hName, mName, secLeft, variesLr} from './domain.js';
import {mean} from './stats.js';

// Primeira linha em que a acurácia de validação atinge o alvo t (-1 se nenhuma).
export const hitIndex = (rows, t) => rows.findIndex(r => r.val_bacc >= t);
// Rodada (R) e bytes acumulados (C) quando atinge o alvo; null se não atinge.
export function hit(rows, t) { const r = rows[hitIndex(rows, t)]; return r ? {R: r.round, C: r.cum_bytes} : null; }

// Execuções agrupadas por série (método, e lr quando a grade varia o lr) e nível de heterogeneidade.
// series é o rótulo mostrado; method é a chave do backend (fedcxr.config.method_key).
export function groupsOf(runs) {
  const multiLr = variesLr(runs), series = r => multiLr ? `${mName(r.method)} · lr ${lrTxt(r.lr)}` : mName(r.method), g = {};
  for (const r of runs) { const key = `${series(r)}|${r.het}`; (g[key] ??= {series: series(r), method: r.method, het: r.het, runs: []}).runs.push(r); }
  return Object.values(g).sort((a, b) => a.series.localeCompare(b.series) || byHet(a.het, b.het));
}
export const doneRuns = g => g ? g.runs.filter(r => r.status === 'done') : [];
const hitsOf = (g, t) => doneRuns(g).map(r => hit(r.rows, t)).filter(Boolean);
export const seriesOf = groups => [...new Set(groups.map(g => g.series))];
export const hetsOf = groups => [...new Set(groups.map(g => g.het))].sort(byHet);
// primeira série (em ordem alfabética) do método; as variantes (-r16, -mu0.1) contam como o mesmo método
const seriesWith = (groups, method) => groups.find(g => g.method === method || g.method.startsWith(`${method}-`))?.series;
// Série das curvas: a escolhida se existe nesta grade, senão o FedAvg completo, senão a primeira.
export function pickSeries(groups, wanted) {
  const series = seriesOf(groups);
  return series.includes(wanted) ? wanted : seriesWith(groups, 'fedavg-full') ?? series[0] ?? null;
}

// Média de R e C entre as seeds concluídas que atingiram o alvo; null se nenhuma atingiu.
export function meanToTarget(g, t) {
  const h = hitsOf(g, t);
  return h.length ? {R: mean(h.map(x => x.R)), C: mean(h.map(x => x.C))} : null;
}

// Acurácia de validação média entre as seeds, rodada a rodada, até a rodada que todas já têm; x vem da primeira seed.
export function meanCurve(g, xKey) {
  const n = Math.min(...g.runs.map(r => r.rows.length));
  if (!isFinite(n)) return [];
  return Array.from({length: n}, (_, i) => ({x: g.runs[0].rows[i][xKey], y: mean(g.runs.map(r => r.rows[i].val_bacc))}));
}

// Andamento da grade: contagens, tempo médio por execução e tempo restante com as GPUs em paralelo.
export function gridProgress(runs, expected, nGpu) {
  const fin = runs.filter(r => r.status === 'done'), act = runs.filter(active);
  const total = expected ?? runs.length, pending = Math.max(0, total - fin.length - act.length);
  const secPerRun = fin.length ? mean(fin.map(r => r.summary.wall_sec))
    : act.length ? mean(act.map(r => (r.rows.length ? mean(r.rows.map(x => x.sec)) : 0) * r.max_rounds)) : NaN;
  const left = act.reduce((s, r) => s + secLeft(r), 0);
  const best = fin.length ? fin.reduce((a, b) => b.summary.test_bacc > a.summary.test_bacc ? b : a) : null;
  return {fin, act, total, pending, secPerRun, eta: (pending * secPerRun + left) / nGpu, best};
}

// [rótulo, valor, ajuda, classe] dos cartões H1, H2 e "não atingiu".
export function insightCards(groups, t, m) {
  const hets = hetsOf(groups);
  const worst = hets.filter(h => h !== 'IID').at(-1), gm = (s, h) => groups.find(g => g.series === s && g.het === h);
  const iid = hitsOf(gm(m, 'IID'), t), wst = hitsOf(gm(m, worst), t);
  const fA = seriesWith(groups, 'fedavg-full'), fL = seriesWith(groups, 'fedavg-lora');
  const lv = worst ?? 'IID', full = hitsOf(gm(fA, lv), t), lora = hitsOf(gm(fL, lv), t);
  const notHit = groups.reduce((s, g) => s + doneRuns(g).filter(r => !hit(r.rows, t)).length, 0);
  const h1 = iid.length && wst.length, h2 = full.length && lora.length;
  const avg = (xs, k) => mean(xs.map(x => x[k]));
  return [
    ['H1 · Custo extra da heterogeneidade', h1 ? `${nf(avg(wst, 'C') / avg(iid, 'C'), 2)}×` : NA,
      h1 ? `${m} trafega isso a mais para chegar a ${nf(t, 2)} em ${hName(worst)} do que em IID (R de ${nf(avg(iid, 'R'), 0)} para ${nf(avg(wst, 'R'), 0)} rodadas).`
        : `Custo até o alvo no nível mais heterogêneo dividido pelo do IID. Aparece quando os dois atingirem ${nf(t, 2)} em execuções concluídas.`, h1 ? 'hl' : ''],
    ['H2 · Economia do LoRA', h2 ? `${nf(avg(full, 'C') / avg(lora, 'C'), 0)}×` : NA,
      h2 ? `menos bytes que o FedAvg completo até o alvo em ${hName(lv)} (R de ${nf(avg(full, 'R'), 0)} para ${nf(avg(lora, 'R'), 0)}).`
        : 'Quantas vezes menos o LoRA trafega até o alvo no nível mais heterogêneo. Aparece quando FedAvg e FedAvg + LoRA atingirem o alvo.', h2 ? 'hl' : ''],
    ['Concluídas sem atingir o alvo', String(notHit), `Execuções terminadas abaixo de ${nf(t, 2)}. Se forem muitas, baixe o alvo ou aumente as rodadas.`],
  ];
}
