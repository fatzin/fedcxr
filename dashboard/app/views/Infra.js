// Infraestrutura: configurar treino, proteção térmica, GPUs e registro de pausas.
import {html} from 'htm/preact';
import {GpuCard} from '../components/GpuCard.js';
import {GuardCard} from '../components/GuardCard.js';
import {LaunchCard} from '../components/LaunchCard.js';
import {Explain, Faint} from '../components/ui.js';
import {GUARD_EVENTS, active} from '../domain.js';
import {NA, ago, clock, gpuShort, nf} from '../format.js';
import {data} from '../state.js';

function GuardLog({D}) {
  const ev = [...D.guard.events].reverse().slice(0, 80);
  if (!ev.length) return html`<div class="empty">Nenhum evento registrado.</div>`;
  return html`<table><thead><tr><th>Quando</th><th>Evento</th><th>GPU</th><th class="r">Temperatura</th><th>Detalhe</th></tr></thead><tbody>${ev.map(e => { const [lab, cls] = GUARD_EVENTS[e.kind]; return html`
    <tr><td>${clock(e.t)} <${Faint}>· ${ago(e.t, D.time)}<//></td><td><span class=${`tag ${cls}`}>${lab}</span></td>
      <td>${e.gpu == null ? NA : gpuShort(D.gpus.find(g => g.index === e.gpu)?.name) || 'GPU ' + e.gpu}</td><td class="r">${e.temp == null ? NA : nf(e.temp, 0) + ' °C'}</td><td style="color:var(--muted)">${e.msg}</td></tr>`; })}</tbody></table>`;
}

export function Infra() {
  const D = data.value;
  const running = D ? D.grids.flatMap(gr => gr.runs.filter(active).map(r => ({...r, grid: gr.grid}))) : [];
  return html`<section class="view">
    <${LaunchCard} />
    ${D ? html`<${GuardCard} D=${D} />` : html`<div class="card"></div>`}
    <div class="gpus">${D && (D.gpus.length
      ? D.gpus.map((g, gi) => html`<${GpuCard} key=${g.index} D=${D} g=${g} gi=${gi} running=${running} />`)
      : html`<div class="card"><div class="empty">nvidia-smi indisponível nesta máquina.</div></div>`)}</div>
    <div class="card"><h3>Registro da proteção térmica</h3>
      <${Explain}><div>Cada pausa e retomada feita pelo <code>thermal_guard.py</code>. Ele só mexe em processos de treino deste projeto e o treino continua exatamente de onde parou.</div><//>
      <div class="scroll capped">${D && html`<${GuardLog} D=${D} />`}</div></div>
  </section>`;
}
