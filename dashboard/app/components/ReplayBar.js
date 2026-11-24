// Barra do replay: reproduzir/pausar, barra de rodadas arrastável, velocidade e saída.
import {html} from 'htm/preact';
import {SPEEDS} from '../replay-core.js';
import {replay, scrubStart, scrubTo, speed, stopReplay, togglePlay} from '../replay.js';
import {Segmented, pressKeys} from './ui.js';

// r: a execução aberta (null antes dos dados)
export function ReplayBar({r}) {
  const rp = replay.value, total = rp ? rp.rows.length : r ? r.rows.length : 0, k = rp ? rp.k : total;
  const cls = ['rpbar', rp && 'on', rp?.playing && 'playing'].filter(Boolean).join(' ');
  return html`<div class=${cls}>
    <button type="button" class="playbtn" aria-label=${rp?.playing ? 'Pausar o replay' : 'Reproduzir o treino rodada a rodada'}
      onPointerDown=${e => { e.preventDefault(); togglePlay(); }} onKeyDown=${pressKeys(togglePlay)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path class="i-play" d="M8 5.5v13l11-6.5z"/><path class="i-pause" d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg></button>
    <span class="rplabel">Replay</span>
    <input type="range" id="rpScrub" min="0" max=${total} step="0.01" value=${k} style=${{'--p': `${100 * k / Math.max(total, 1)}%`}} aria-label="Rodada do replay"
      onPointerDown=${e => scrubStart(e.currentTarget.value)} onInput=${e => scrubTo(e.currentTarget.value)} />
    <span class="rpround num">${`r ${Math.floor(k)} / ${r?.max_rounds ?? 0}`}</span>
    <${Segmented} label="Velocidade do replay" options=${r ? SPEEDS : []} current=${speed.value} onPick=${v => { speed.value = v; }} />
    <button type="button" class="linkbtn" hidden=${!rp} onClick=${stopReplay}>Sair do replay</button>
  </div>`;
}
