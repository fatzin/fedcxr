// Cartão de uma execução em andamento (Visão geral): progresso, acurácia e tempo restante.
import {html} from 'htm/preact';
import {gpuOfRun, lastRound, progress, runLabel, secLeft} from '../domain.js';
import {NA, dur, gpuShort, lrTxt, nf} from '../format.js';
import {openRun} from '../router.js';
import {StatusTag} from './ui.js';

export function RunCard({r, data}) {
  const last = r.rows.at(-1) || {}, prev = r.rows.at(-6), d = prev ? last.val_bacc - prev.val_bacc : null, gpu = gpuOfRun(data, r);
  const dir = d > .005 ? 'up' : d < -.005 ? 'down' : 'flat';
  return html`<button class="runcard" onClick=${() => openRun(r.name)}>
    <div class="top"><span class="name">${runLabel(r)}</span><${StatusTag} s=${r.status} /></div>
    <div class="meta">seed ${r.seed} · lr ${lrTxt(r.lr)} · ${gpuShort(gpu ? gpu.name : r.gpu_name) || NA}</div>
    <div class=${`prog ${r.status === 'paused' ? 'warn' : ''}`}><div style=${{width: `${100 * progress(r)}%`}}></div></div>
    <div class="row"><span>Rodada <b class="num">${lastRound(r)}/${r.max_rounds}</b></span>
      <span>Acurácia val. <b class="num">${nf(last.val_bacc, 3)}</b>${d == null ? '' : html`<span class=${`delta ${dir}`} title="variação nas últimas 5 rodadas">${dir === 'up' ? '▲' : dir === 'down' ? '▼' : '•'} ${nf(Math.abs(d), 3)}</span>`}</span>
      <span>Termina em <b class="num">${r.status === 'running' ? dur(secLeft(r)) : NA}</b></span></div></button>`;
}
