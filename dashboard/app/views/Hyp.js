// Hipóteses: curvas por nível de heterogeneidade, rodadas e bytes até o alvo, tabela por configuração.
import {html} from 'htm/preact';
import {doneRuns, hetsOf, hit, insightCards, meanCurve, meanToTarget} from '../analysis.js';
import {bars, hetColor, lineWithTarget, methodToken} from '../charts.js';
import {ChartBox} from '../components/Chart.js';
import {Explain, Segmented, kpis, pm, pressKeys} from '../components/ui.js';
import {hName} from '../domain.js';
import {NA, bytes, nf, plural} from '../format.js';
import {mean} from '../stats.js';
import {css} from '../theme.js';
import {TARGET, clampTarget, curveSeries, data, groups, series, setMethod, setTarget, target, targetNum} from '../state.js';

const nudge = d => setTarget(clampTarget(targetNum.value + d).toFixed(2));

function Controls() {
  return html`<div class="card"><div class="controls">
    <div class="control"><label>Curvas de</label><${Segmented} label="Método das curvas" options=${series.value.map(s => [s, s])} current=${curveSeries.value}
      onPick=${setMethod} /></div>
    <div class="control"><label for="target">Alvo de acurácia</label><div class="step">
      <button aria-label="Diminuir alvo" onPointerDown=${() => nudge(-.01)} onKeyDown=${pressKeys(() => nudge(-.01))}>−</button>
      <input id="target" type="number" step="0.01" min=${TARGET.min} max=${TARGET.max} value=${target.value} onInput=${e => setTarget(e.target.value)} />
      <button aria-label="Aumentar alvo" onPointerDown=${() => nudge(.01)} onKeyDown=${pressKeys(() => nudge(.01))}>+</button></div></div>
  </div></div>`;
}

function GroupTable({t}) {
  const gs = groups.value, ss = series.value;
  if (!gs.length) return html`<div class="empty">Sem execuções nesta grade ainda.</div>`;
  return html`<table><thead><tr><th>Método</th><th>Heterogeneidade</th><th class="r">Seeds prontas</th><th class="r">KL médio</th><th class="r">Por rodada</th><th class="r">R até ${nf(t, 2)}</th><th class="r">C<sub>total</sub> (MB)</th><th class="r">Acurácia bal. teste</th><th class="r">AUC teste</th></tr></thead>
    <tbody>${gs.map(g => {
      const d = doneRuns(g), ok = d.map(r => hit(r.rows, t)).filter(Boolean), cens = d.length - ok.length;
      const kl = g.runs.map(r => r.kl_mean).filter(x => x != null), rb = g.runs.filter(r => r.rows.length).map(r => r.rows[0].round_bytes);
      return html`<tr><td><span class="swatch" style=${{background: css(methodToken(ss.indexOf(g.series)))}}></span>${g.series}</td><td>${hName(g.het)}</td>
        <td class="r">${d.length} / ${g.runs.length}</td><td class="r">${pm(kl, 3)}</td><td class="r">${rb.length ? bytes(mean(rb)) : NA}</td>
        <td class="r">${pm(ok.map(x => x.R))}${cens ? html` <span class="warn">· ${cens} não atinge</span>` : ''}</td><td class="r">${pm(ok.map(x => x.C / 1e6), 0)}</td>
        <td class="r">${pm(d.map(r => r.summary.test_bacc), 3)}</td><td class="r">${pm(d.map(r => r.summary.test_auc).filter(x => x != null), 3)}</td></tr>`; })}</tbody></table>`;
}

function charts(t) {
  const gs = groups.value, ss = series.value, hets = hetsOf(gs);
  const cg = gs.filter(g => g.series === curveSeries.value);
  const lines = (xKey, xScale) => cg.map((g, i) => ({label: `${hName(g.het)} (${g.runs.length} ${plural(g.runs.length, 'seed')})`,
    data: meanCurve(g, xKey).map(p => ({x: p.x / xScale, y: p.y})),
    borderColor: hetColor(i, cg.length), backgroundColor: hetColor(i, cg.length), pointRadius: 0, pointHoverRadius: 4, borderWidth: 2, tension: .25}));
  const bar = pick => ss.map((s, i) => ({label: s, backgroundColor: css(methodToken(i)), borderRadius: 4, maxBarThickness: 26,
    data: hets.map(h => { const m = meanToTarget(gs.find(g => g.series === s && g.het === h), t); return m ? pick(m) : null; })}));
  return {round: lineWithTarget(lines('round', 1), 'Rodada', t), bytes: lineWithTarget(lines('cum_bytes', 1e9), 'Gigabytes trafegados', t),
    R: bars(hets.map(hName), bar(m => m.R), 'Rodadas até o alvo', false), C: bars(hets.map(hName), bar(m => m.C / 1e6), 'MB até o alvo', true)};
}

export function Hyp() {
  const D = data.value, t = targetNum.value, c = D ? charts(t) : {round: {}, bytes: {}, R: {}, C: {}};
  return html`<section class="view">
    <${Controls} />
    <div class="grid4">${D && kpis(insightCards(groups.value, t, curveSeries.value))}</div>
    <div class="grid2">
      <div class="card"><h3>Acurácia por rodada, por nível de heterogeneidade <span class="hyp">H1</span></h3>
        <${Explain}><div>se a H1 estiver certa, as curvas mais escuras (mais heterogêneas) sobem mais devagar e cruzam o alvo depois, ou nem cruzam.</div><//>
        <${ChartBox} ...${c.round} /></div>
      <div class="card"><h3>Acurácia por gigabyte trafegado <span class="hyp">H1 · H2</span></h3>
        <${Explain}><div>quanto mais à esquerda a curva cruza o alvo, mais barato foi chegar lá.</div><//>
        <${ChartBox} ...${c.bytes} /></div>
      <div class="card"><h3>Rodadas até o alvo (R) <span class="hyp">H1</span></h3>
        <${Explain}><div>barras crescendo do IID para α = 0,1 confirmam que a heterogeneidade pede mais rodadas. Sem barra: não atingiu o alvo.</div><//>
        <${ChartBox} ...${c.R} /></div>
      <div class="card"><h3>Custo total até o alvo (C<sub>total</sub>) <span class="hyp">H1 · H2</span></h3>
        <${Explain}><div>é o número central do artigo. A H2 pergunta se a vantagem do LoRA (barras bem menores) se mantém quando a heterogeneidade aumenta R.</div><//>
        <${ChartBox} ...${c.C} /></div>
    </div>
    <div class="card"><h3>Resultados por configuração</h3>
      <${Explain}><div>Média ± desvio entre seeds. <b>KL</b> mede o quanto a mistura de diagnósticos dos hospitais difere da mistura geral (0 = igual).</div><//>
      <div class="scroll">${D && html`<${GroupTable} t=${t} />`}</div></div>
  </section>`;
}
