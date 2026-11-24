// Cartão de uma GPU: temperatura, limite de clock, medidores, treino em cima dela e histórico de 15 minutos.
import {html} from 'htm/preact';
import {chartOpts} from '../charts.js';
import {STATUS, clockPct, gpuOfRun, lastRound, limitOf, procsOn, runLabel, tempLevel} from '../domain.js';
import {NA, gpuShort, lrTxt, nf} from '../format.js';
import {css} from '../theme.js';
import {ChartBox} from './Chart.js';
import {Explain} from './ui.js';

// posições de cada amostra em gpu_hist.g[i] (ver GPU_HIST em dashboard/server.py)
const TEMP = 0, CLOCK = 3;

const Meter = ({label, pct, text}) => html`<div class="meter"><span>${label}</span><div class="track"><div style=${{width: `${pct}%`}}></div></div><span>${text}</span></div>`;

// gi: posição da GPU em data.gpus, a mesma das amostras do histórico
function history(D, g, gi) {
  const {hot, cool} = D.guard, h = D.gpu_hist, t0 = h.length ? h.at(-1).t : 0;
  const pts = f => h.filter(s => s.g[gi]).map(s => ({x: (s.t - t0) / 60, y: f(s.g[gi])}));
  const ref = (v, l) => ({label: l, data: [{x: -15, y: v}, {x: 0, y: v}], borderColor: css('--faint'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0});
  const o = chartOpts('', ''); o.scales.x.type = 'linear'; o.scales.x.min = -15; o.scales.x.max = 0;
  o.scales.x.ticks.callback = v => v === 0 ? 'agora' : `${v} min`; o.plugins.legend.display = false; o.scales.y.suggestedMin = 30; o.scales.y.suggestedMax = 100;
  return {type: 'line', options: o, data: {datasets: [
    {label: 'Temperatura (°C)', data: pts(s => s[TEMP]), borderColor: css('--bad'), backgroundColor: css('--bad'), borderWidth: 1.6, pointRadius: 0, tension: .2},
    {label: 'Clock (% do máximo)', data: pts(s => clockPct({clock: s[CLOCK], clock_max: g.clock_max})), borderColor: css('--accent'), backgroundColor: css('--accent'), borderWidth: 1.6, pointRadius: 0, tension: .2},
    ref(hot, 'Pausa'), ref(cool, 'Retoma')]}};
}

// running: execuções em andamento de todas as grades, com a grade em r.grid
export function GpuCard({D, g, gi, running}) {
  const [lab, cls, help] = limitOf(g), on = running.filter(r => gpuOfRun(D, r) === g), procs = procsOn(D, g);
  return html`<div class="card"><div>
      <div class="gpuhead"><div><div class="eyebrow">GPU ${g.index} · ${gpuShort(g.name)}</div>
        <div class="big num"><span class=${tempLevel(g.temp, D.guard.hot)}>${nf(g.temp, 0)} °C</span></div></div>
        <div style="text-align:right"><span class=${`tag ${cls}`}>${lab}</span><div class="sub" style="max-width:230px">${help}</div></div></div>
      <div class="meters">
        <${Meter} label="Clock" pct=${clockPct(g)} text=${`${nf(g.clock, 0)} / ${nf(g.clock_max, 0)} MHz`} />
        <${Meter} label="Consumo" pct=${100 * g.power / (g.power_limit || 1)} text=${`${nf(g.power, 0)} / ${nf(g.power_limit, 0)} W`} />
        <${Meter} label="Uso" pct=${g.util} text=${`${nf(g.util, 0)}%`} />
        <${Meter} label="Memória" pct=${100 * g.mem_used / g.mem_total} text=${`${nf(g.mem_used / 1024, 1)} / ${nf(g.mem_total / 1024, 0)} GB`} />
        <${Meter} label="Ventoinha" pct=${g.fan ?? 0} text=${g.fan == null ? NA : nf(g.fan, 0) + '%'} />
      </div>
      <div class="onrun">${on.length ? on.map((r, i) => html`${i ? html`<br />` : ''}${STATUS[r.status][0]}: <b>${runLabel(r)}</b> · seed ${r.seed} · lr ${lrTxt(r.lr)} · rodada ${lastRound(r)}/${r.max_rounds} (grade ${r.grid})`)
        : procs.length ? `Sem treino; ${procs.length} processo(s) do sistema usando ${nf(procs.reduce((s, p) => s + (p.mem || 0), 0) / 1024, 1)} GB` : 'Nenhum treino nesta placa.'}</div></div>
    <${Explain} open style="margin:4px 0 6px"><div><b>Últimos 15 minutos:</b> temperatura (vermelho, °C) e clock (branco, % do máximo). As linhas tracejadas são os limites da proteção. Clock caindo enquanto a temperatura sobe é thermal throttling.</div><//>
    <${ChartBox} size="sm" ...${history(D, g, gi)} /></div>`;
}
