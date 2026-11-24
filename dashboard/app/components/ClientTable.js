// Tabela dos hospitais simulados: partição, métricas locais e alinhamento com a média.
// As linhas têm chave pelo hospital, então as barras mudam de largura no lugar (com transição) a cada rodada.
import {Fragment} from 'preact';
import {html} from 'htm/preact';
import {CLASSES} from '../domain.js';
import {NA, nf} from '../format.js';
import {Missing} from './ui.js';

const cosColor = c => c >= .5 ? 'var(--ok)' : c >= .2 ? 'var(--warn)' : 'var(--bad)';
function CosCell({c}) {
  if (c == null) return html`<${Missing} />`;
  const w = Math.min(1, Math.abs(c)) * 50;
  return html`<span class="cosbar"><span style=${{left: `${c >= 0 ? 50 : 50 - w}%`, width: `${w}%`, background: cosColor(c)}}></span></span><span class="num">${nf(c, 2)}</span>`;
}

function Row({c, s}) {
  const tot = c.counts.reduce((a, b) => a + b, 0) || 1;
  return html`<tr><td>#${c.id + 1}</td><td class="r">${nf(c.n, 0)}</td>
    <td><span class="mix">${c.counts.map((n, i) => html`<span style=${{width: `${100 * n / tot}%`, background: `var(--c${i})`}} title=${`${CLASSES[i].name}: ${n}`}></span>`)}</span> <span style="color:var(--faint);font-size:12px">${c.counts.join(' / ')}</span></td>
    <td class="r">${nf(c.kl, 2)}</td>
    <td class="r">${nf(s.loss, 3)}</td><td class="r">${nf(s.acc, 3)}</td>
    <td><${CosCell} c=${s.cos} /></td>
    <td class="r">${nf(s.upd_norm, 3)}</td><td class="r">${s.sec == null ? NA : nf(s.sec, 1) + ' s'}</td></tr>`;
}

export function ClientTable({r}) {
  const cs = r.client_stats || [], counts = r.clients || [];
  if (!counts.length) return html`<div class="empty">Sem dados de partição para esta execução.</div>`;
  const byId = Object.fromEntries(cs.map(c => [c.id, c]));
  // chave nova (outra execução ou começo do registro por hospital) recria a tabela em vez de animar
  return html`<${Fragment} key=${r.name + '|' + cs.length}><table><thead><tr><th>Hospital</th><th class="r">Imagens</th><th>${`Mistura de diagnósticos (${CLASSES.map(c => c.name[0]).join(' / ')})`}</th><th class="r">KL</th><th class="r">Perda local</th><th class="r">Acurácia local</th><th>Alinhamento com a média</th><th class="r">Tamanho da atualização</th><th class="r">Tempo</th></tr></thead>
    <tbody>${counts.map(c => html`<${Row} key=${c.id} c=${c} s=${byId[c.id] || {}} />`)}</tbody></table>
    ${cs.length ? '' : html`<div class="empty" style="padding-top:10px">Esta execução começou antes do registro por hospital; aqui aparece só a partição.</div>`}<//>`;
}
