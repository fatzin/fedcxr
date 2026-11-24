// Proteção térmica: escala de temperatura com os limites, posição de cada GPU e contagem de pausas.
import {html} from 'htm/preact';
import {guardStats, tempLevel} from '../domain.js';
import {dur, gpuShort, nf} from '../format.js';
import {Explain, GuardTag, kpis} from './ui.js';

const LO = 40, HI = 100, pos = v => `${100 * (Math.min(HI, Math.max(LO, v)) - LO) / (HI - LO)}%`;

export function GuardCard({D}) {
  const {hot, cool, alive} = D.guard, st = guardStats(D.guard, D.time);
  return html`<div class="card"><div class="cardhead"><h3>Proteção térmica</h3><${GuardTag} alive=${alive} /></div>
    <${Explain} open><div>Quando uma placa chega a <b>${nf(hot, 0)} °C</b>, o treino dela é pausado; quando esfria até <b>${nf(cool, 0)} °C</b>, ele continua de onde parou. ${alive ? ''
      : html`<span class="bad">O processo não está rodando. O comando para iniciar está em Configurar treino, aba Local.</span>`}</div><//>
    <div class="thermo" role="img" aria-label="Escala de temperatura com limites e posição de cada GPU">
      <div class="mk" style=${{left: pos(cool)}}><span>${`retoma ${nf(cool, 0)} °C`}</span></div><div class="mk" style=${{left: pos(hot)}}><span>${`pausa ${nf(hot, 0)} °C`}</span></div>
      ${D.gpus.map(g => html`<div class=${`gp ${tempLevel(g.temp, hot) || 'ok'}`} style=${{left: pos(g.temp)}}>${gpuShort(g.name)} ${nf(g.temp, 0)}°</div>`)}
    </div>
    <div class="grid4" style="margin-top:12px">${kpis([
      ['Pausas na última hora', st.p1h, 'Muitas pausas seguidas indicam ventilação insuficiente para a carga.'],
      ['Pausas em 24 h', st.p24, 'Cada pausa dura até a placa esfriar.'],
      ['Tempo pausado em 24 h', dur(st.pausedSec), 'Tempo de treino perdido esperando esfriar.'],
      ['Agora', st.openGpus.length ? html`<span class="warn">Pausada</span>` : html`<span class="ok">Treinando</span>`, st.openGpus.length ? `GPU ${st.openGpus.join(', ')} esfriando.` : 'Nenhuma placa em pausa.'],
    ])}</div></div>`;
}
