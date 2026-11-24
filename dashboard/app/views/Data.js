// Dados: conjunto de radiografias, partição entre os hospitais e heterogeneidade medida por nível.
import {html} from 'htm/preact';
import {signal} from '@preact/signals';
import {chartOpts} from '../charts.js';
import {ChartBox} from '../components/Chart.js';
import {Explain, Segmented, kpis, pm} from '../components/ui.js';
import {CLASSES, byHet, hName, hShort} from '../domain.js';
import {NA, nf} from '../format.js';
import {mean} from '../stats.js';
import {data, grid, runs} from '../state.js';
import {css} from '../theme.js';

// nível escolhido, válido só na grade em que foi escolhido
const picked = signal({grid: null, het: null});

const SPLITS = [['train', 'Treino (dividido entre hospitais)'], ['val', 'Validação'], ['test', 'Teste oficial']];

function partitionChart(ref) {
  const o = chartOpts('Radiografias', ''); o.indexAxis = 'y'; o.scales.x.stacked = true; o.scales.y.stacked = true;
  o.scales.x.grid = {color: css('--hairline')}; o.scales.y.grid = {display: false};
  o.plugins.tooltip.callbacks = {label: c => `${c.dataset.label}: ${nf(c.parsed.x, 0)}`, afterBody: it => `KL: ${nf(ref.clients[it[0].dataIndex].kl, 3)}`};
  return {type: 'bar', options: o, data: {labels: ref.clients.map(c => `Hospital ${c.id + 1}`),
    datasets: CLASSES.map((c, i) => ({label: c.name, data: ref.clients.map(x => x.counts[i]), backgroundColor: css('--c' + i), borderRadius: 0, maxBarThickness: 22}))}};
}

function DatasetTable({D, tot}) {
  if (!D.train) return html`<div class="empty">Sem informação do conjunto nesta grade.</div>`;
  return html`<table><thead><tr><th>Divisão</th>${CLASSES.map((c, i) => html`<th class="r"><span class="swatch" style=${`background:var(--c${i})`}></span>${c.name}</th>`)}<th class="r">Total</th></tr></thead>
    <tbody>${SPLITS.map(([k, l]) => html`<tr><td>${l}</td>${Object.values(D[k] || {}).map(x => html`<td class="r">${nf(x, 0)}</td>`)}<td class="r"><b>${nf(tot(k), 0)}</b></td></tr>`)}</tbody></table>`;
}

function HetTable({withPart, hets}) {
  if (!hets.length) return html`<div class="empty">Sem partições nesta grade.</div>`;
  const rows = hets.map(h => {
    const seeds = [...new Map(withPart.filter(r => r.het === h).map(r => [r.seed, r])).values()];
    return {h, seeds, kl: seeds.map(r => r.kl_mean), klmax: seeds.map(r => Math.max(...r.clients.map(c => c.kl))),
      dom: seeds.map(r => mean(r.clients.map(c => Math.max(...c.counts) / (c.n || 1)))),
      mn: seeds.map(r => Math.min(...r.clients.map(c => c.n))), mx: seeds.map(r => Math.max(...r.clients.map(c => c.n)))};
  });
  return html`<table><thead><tr><th>Nível</th><th class="r">Seeds</th><th class="r">KL médio</th><th class="r">KL do hospital mais distante</th><th class="r">Classe dominante (fração média)</th><th class="r">Menor hospital</th><th class="r">Maior hospital</th></tr></thead>
    <tbody>${rows.map(x => html`<tr><td>${hName(x.h)}</td><td class="r">${x.seeds.length}</td><td class="r">${pm(x.kl, 3)}</td><td class="r">${pm(x.klmax, 2)}</td><td class="r">${pm(x.dom.map(v => 100 * v), 0)}%</td><td class="r">${pm(x.mn, 0)}</td><td class="r">${pm(x.mx, 0)}</td></tr>`)}</tbody></table>`;
}

export function Data() {
  const loaded = !!data.value, rs = runs.value;
  const withPart = rs.filter(r => r.clients && r.clients.length);
  const hets = [...new Set(withPart.map(r => r.het))].sort(byHet);
  const want = picked.value.grid === grid.value ? picked.value.het : null;
  const cur = hets.includes(want) ? want : hets.at(-1) ?? null;
  const ref = withPart.find(r => r.het === cur && r.seed === 0) || withPart.find(r => r.het === cur);
  const D = (rs.find(r => r.dataset && r.dataset.train) || {}).dataset || {};
  const tot = s => Object.values(D[s] || {}).reduce((a, b) => a + b, 0);
  return html`<section class="view">
    <div class="grid4">${loaded && kpis([
      ['Radiografias', D.train ? nf(tot('train') + tot('val') + tot('test'), 0) : NA, 'Kermany pediátrico, 3 classes, 224 × 224 em tons de cinza.'],
      ['Hospitais simulados', ref ? ref.clients.length : NA, ref ? `De ${nf(Math.min(...ref.clients.map(c => c.n)), 0)} a ${nf(Math.max(...ref.clients.map(c => c.n)), 0)} imagens cada em ${hName(ref.het)}.` : 'Clientes do FL.'],
      ['KL médio da partição', ref ? nf(ref.kl_mean, 3) : NA, ref ? `${hName(ref.het)} · seed ${ref.seed}. 0 = todos iguais à mistura geral.` : NA],
      ['Níveis de heterogeneidade', hets.length, 'IID e α de Dirichlet presentes nesta grade.'],
    ])}</div>
    <div class="grid21">
      <div class="card"><div class="cardhead"><h3>Partição entre os hospitais</h3>
          <div class="control"><label>Nível</label><${Segmented} label="Nível de heterogeneidade" options=${hets.map(h => [h, hShort(h)])}
            current=${cur} onPick=${h => { picked.value = {grid: grid.value, het: h}; }} /></div></div>
        <${Explain}><div>em IID as barras têm as mesmas proporções. Quanto menor o α, mais cada barra fica de uma cor só, e mais diferentes ficam os tamanhos.</div><//>
        <${ChartBox} size="tall" ...${ref ? partitionChart(ref) : {}} /></div>
      <div class="card"><h3>Conjunto de dados</h3>
        <${Explain}><div>Kermany et al. (2018), radiografias pediátricas de tórax. A validação foi separada do treino por paciente; o teste é o oficial. Só o treino é dividido entre os hospitais.</div><//>
        <div class="scroll">${loaded && html`<${DatasetTable} D=${D} tot=${tot} />`}</div></div>
    </div>
    <div class="card"><h3>Heterogeneidade medida por nível</h3>
      <${Explain}><div><b>KL</b> é a divergência entre a mistura de cada hospital e a mistura geral. Valores medidos no sorteio de Dirichlet.</div><//>
      <div class="scroll">${loaded && html`<${HetTable} withPart=${withPart} hets=${hets} />`}</div></div>
  </section>`;
}
