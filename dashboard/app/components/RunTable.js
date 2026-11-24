// Tabela de execuções com filtro por estado, busca e ordenação por coluna.
import {html} from 'htm/preact';
import {signal} from '@preact/signals';
import {HET_ORDER, STATUS, active, bestVal, hName, lastRound, mName, progress, runLabel} from '../domain.js';
import {NA, bytes, dur, gpuShort, lrTxt, nf} from '../format.js';
import {openRun} from '../router.js';
import {Missing, Segmented, StatusTag} from './ui.js';

// ficam entre as visitas à tela
const filter = signal('all'), query = signal(''), sort = signal(['status', 1]);

const FILTERS = [['all', 'Todas', () => true], ['active', 'Em andamento', active],
  ['done', 'Concluídas', r => r.status === 'done'], ['problem', 'Paradas', r => r.status === 'stalled']];
const runTime = r => r.summary?.wall_sec ?? r.rows.reduce((s, x) => s + (x.sec || 0), 0);
const STATUS_ORDER = Object.keys(STATUS);
// [chave, título, valor para ordenar, alinhada à direita]
const COLS = [
  ['status', 'Estado', r => STATUS_ORDER.indexOf(r.status)],
  ['method', 'Método', r => mName(r.method)], ['het', 'Heterogeneidade', r => -HET_ORDER(r.het)], ['seed', 'Seed', r => r.seed, true],
  ['lr', 'lr', r => r.lr, true], ['round', 'Progresso', progress],
  ['best', 'Melhor val.', r => bestVal(r) ?? -1, true], ['test', 'Teste', r => r.summary?.test_bacc ?? -1, true],
  ['bytes', 'Trafegado', r => r.rows.at(-1)?.cum_bytes || 0, true], ['time', 'Tempo', runTime, true],
  ['gpu', 'GPU', r => gpuShort(r.gpu_name)],
];

function Row({r}) {
  return html`<tr class="click" onClick=${() => openRun(r.name)}><td><${StatusTag} s=${r.status} /></td><td>${mName(r.method)}</td><td>${hName(r.het)}</td><td class="r">${r.seed}</td><td class="r">${lrTxt(r.lr)}</td>
    <td><span class="minibar"><span style=${{width: `${100 * progress(r)}%`}}></span></span><span class="num">${`${lastRound(r)}/${r.max_rounds}`}</span></td>
    <td class="r">${nf(bestVal(r), 3)}</td><td class="r">${r.summary ? html`<b>${nf(r.summary.test_bacc, 3)}</b>` : html`<${Missing} />`}</td>
    <td class="r">${bytes(r.rows.at(-1)?.cum_bytes)}</td><td class="r">${dur(runTime(r))}</td><td>${gpuShort(r.gpu_name) || NA}</td></tr>`;
}

// runs: null enquanto o /api/state não chegou
export function RunTable({runs}) {
  const loaded = runs != null, all = runs || [];
  const q = query.value.trim().toLowerCase(), [key, dir] = sort.value, sortKey = COLS.find(c => c[0] === key)[2];
  const list = all.filter(FILTERS.find(f => f[0] === filter.value)[2])
    .filter(r => !q || `${runLabel(r)} seed ${r.seed} lr ${lrTxt(r.lr)} ${r.name}`.toLowerCase().includes(q))
    .sort((a, b) => { const x = sortKey(a), y = sortKey(b); return (x < y ? -1 : x > y ? 1 : a.name.localeCompare(b.name)) * dir; });
  const sortBy = k => { sort.value = [k, key === k ? -dir : 1]; };
  return html`<div class="card">
    <div class="cardhead">
      <div class="controls">
        <${Segmented} label="Filtrar por estado" options=${loaded ? FILTERS.map(([id, label, test]) => [id, `${label} ${all.filter(test).length}`]) : []}
          current=${filter.value} onPick=${v => { filter.value = v; }} />
        <input type="search" placeholder="Buscar método, α, seed…" aria-label="Buscar execuções" value=${query.value} onInput=${e => { query.value = e.target.value; }} />
      </div>
      <span class="eyebrow">${loaded ? `${list.length} de ${all.length}` : ''}</span>
    </div>
    <div class="scroll">${loaded && (list.length ? html`<table><thead><tr>${COLS.map(([k, l, , right]) => html`
      <th class=${right ? 'sort r' : 'sort'} aria-sort=${k === key ? (dir > 0 ? 'ascending' : 'descending') : undefined} onClick=${() => sortBy(k)}>${l}</th>`)}</tr></thead>
      <tbody>${list.map(r => html`<${Row} key=${r.name} r=${r} />`)}</tbody></table>`
      : html`<div class="empty">Nenhuma execução com esse filtro.</div>`)}</div>
  </div>`;
}
