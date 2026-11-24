// Visão geral: andamento da grade, saúde das GPUs, resumo das hipóteses e atividade recente.
import {html} from 'htm/preact';
import {gridProgress, insightCards} from '../analysis.js';
import {GUARD_EVENTS, active, clockPct, guardStats, limitOf, runLabel, tempLevel} from '../domain.js';
import {NA, clock, dur, gpuShort, nf, plural} from '../format.js';
import {viewHash} from '../routes.js';
import {curveSeries, data, grid, gridObj, groups, runs, targetNum} from '../state.js';
import {RunCard} from '../components/RunCard.js';
import {Dim, GuardTag, kpis} from '../components/ui.js';

function Kpis({D, rs}) {
  const nGpu = Math.max(1, D.gpus.length), p = gridProgress(rs, gridObj.value.expected, nGpu);
  const stalled = rs.filter(r => r.status === 'stalled').length, paused = rs.filter(r => r.status === 'paused').length;
  return kpis([
    ['Execuções concluídas', html`${p.fin.length} <${Dim}>de ${p.total}<//>`, html`Grade <b>${grid.value}</b> · ${p.pending} na fila`],
    ['Em andamento', p.act.length, stalled ? html`<span class="bad">${stalled} sem atualizar há mais de ${dur(D.stalled_after)}</span>`
      : paused ? html`<span class="warn">${paused} pausada(s) pela proteção térmica</span>` : 'Nenhuma travada'],
    ['Tempo restante estimado', p.fin.length === p.total && p.total ? 'Concluída' : dur(p.eta), html`Cerca de <b>${dur(p.secPerRun)}</b> por execução, ${nGpu} ${plural(nGpu, 'GPU')} em paralelo`],
    ['Melhor acurácia no teste', p.best ? nf(p.best.summary.test_bacc, 3) : NA, p.best ? `${runLabel(p.best)} · seed ${p.best.seed}` : 'Aparece quando a primeira execução terminar'],
  ]);
}

function Health({D}) {
  const G = D.guard;
  return html`${D.gpus.map(g => { const [lab, cls] = limitOf(g); return html`
    <div class="hrow"><span class="t">${gpuShort(g.name)} <span class=${`${tempLevel(g.temp, G.hot)} num`} style="font-weight:700">${nf(g.temp, 0)} °C</span></span><span class=${`tag ${cls}`}>${lab}</span>
      <span class="s num">Uso ${nf(g.util, 0)}% · ${nf(g.power, 0)} W · clock ${nf(clockPct(g), 0)}% do máximo</span></div>`; })}
    <div class="hrow"><span class="t">Proteção térmica</span><${GuardTag} alive=${G.alive} />
      <span class="s">Pausa em ${nf(G.hot, 0)} °C, retoma em ${nf(G.cool, 0)} °C · ${guardStats(G, D.time).p1h} pausa(s) na última hora</span></div>`;
}

// eventos da proteção (menos os informativos) e execuções concluídas, mais recentes primeiro
function Feed({D, rs}) {
  const ev = [...D.guard.events.filter(e => e.kind !== 'info').map(e => ({t: e.t, c: GUARD_EVENTS[e.kind][1], m: e.msg})),
    ...rs.filter(r => r.status === 'done').map(r => ({t: r.updated, c: 'accent', m: html`Concluída: <b>${runLabel(r)}</b> · seed ${r.seed} · teste ${nf(r.summary.test_bacc, 3)}`}))]
    .sort((a, b) => b.t - a.t).slice(0, 7);
  return ev.length ? ev.map(e => html`<div><time>${clock(e.t)}</time><span class="dot" style=${`background:var(--${e.c})`}></span><span>${e.m}</span></div>`)
    : html`<div class="empty" style="display:block">Sem eventos ainda.</div>`;
}

export function Overview() {
  const D = data.value, rs = runs.value, t = targetNum.value, act = rs.filter(active);
  return html`<section class="view">
    <div class="grid4">${D && html`<${Kpis} D=${D} rs=${rs} />`}</div>
    <div class="grid21">
      <div class="card"><div class="cardhead"><h3>Em andamento</h3><a class="linkbtn" href=${viewHash('runs')}>Todas as execuções</a></div>
        <div class="runs" style="margin-top:12px">${D && (act.length ? act.map(r => html`<${RunCard} key=${r.name} r=${r} data=${D} />`)
          : html`<div class="empty">Nada treinando nesta grade. O comando para iniciar está em <a href="#/infra">Infraestrutura</a>, no cartão Configurar treino.</div>`)}</div></div>
      <div class="card"><div class="cardhead"><h3>Saúde do PC</h3><a class="linkbtn" href=${viewHash('infra')}>Infraestrutura</a></div>
        <div class="health" style="margin-top:12px">${D && html`<${Health} D=${D} />`}</div></div>
    </div>
    <div class="grid21">
      <div class="card"><div class="cardhead"><h3>Hipóteses nesta grade</h3><a class="linkbtn" href=${viewHash('hyp')}>Abrir análise</a></div>
        <div class="explain">${D && html`<div>Alvo de acurácia ${nf(t, 2)}, execuções concluídas.</div>`}</div>
        <div class="grid4">${D && kpis(insightCards(groups.value, t, curveSeries.value).slice(0, 2))}</div></div>
      <div class="card"><h3>Atividade recente</h3><div class="feed" style="margin-top:8px">${D && html`<${Feed} D=${D} rs=${rs} />`}</div></div>
    </div></section>`;
}
