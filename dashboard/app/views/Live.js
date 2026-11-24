// Treino ao vivo / Execução / Replay: uma execução rodada a rodada.
import {html} from 'htm/preact';
import {axis, chartOpts} from '../charts.js';
import {ChartBox} from '../components/Chart.js';
import {ClientTable} from '../components/ClientTable.js';
import {ReplayBar} from '../components/ReplayBar.js';
import {Dim, Explain, kpis} from '../components/ui.js';
import {CLASSES, active, bestVal, gpuOfRun, lastRound, runLabel, variesLr} from '../domain.js';
import {NA, bytes, dateTime, gpuShort, lrTxt, nf} from '../format.js';
import {frameOf, reachedTarget} from '../replay-core.js';
import {replay} from '../replay.js';
import {openRun} from '../router.js';
import {baseRun, data, run, runs} from '../state.js';
import {css} from '../theme.js';

function RunMode({base, isReplay}) {
  if (!base) return html`<div class="runmode"></div>`;
  return html`<div class="runmode">${isReplay
    ? html`<span class="tag replay">Replay</span><span>Simulação a partir dos registros gravados. Nada está treinando agora.</span>`
    : active(base) ? html`<span class="tag ok"><span class="ld" aria-hidden="true"></span>Treinando</span><span>Dados chegando da GPU a cada rodada.</span>`
    : html`<span class="tag neutral">Registro</span><span>${`Execução ${base.status === 'done' ? 'concluída' : 'interrompida'}${base.updated
        ? ' em ' + dateTime(base.updated) : ''}. Use o replay para ver rodada a rodada.`}</span>`}</div>`;
}

function RunPicker({rs}) {
  const multiLr = variesLr(rs);
  const list = [...rs].sort((a, b) => (active(a) ? 0 : 1) - (active(b) ? 0 : 1) || a.name.localeCompare(b.name));
  return html`<div class="control"><label for="runSel">Execução</label>
    <select id="runSel" value=${run.value ?? ''} onChange=${e => openRun(e.target.value)}>${list.map(r => html`
      <option key=${r.name} value=${r.name}>${active(r) ? '● ' : ''}${runLabel(r)} · seed ${r.seed}${multiLr ? ` · lr ${lrTxt(r.lr)}` : ''}</option>`)}</select></div>`;
}

// flash: o replay acabou de cruzar o alvo (o KPI de acurácia pisca)
function liveKpis(r, flash) {
  const last = r.rows.at(-1) || {};
  const lastTest = r.rows.findLast(x => x.test_bacc != null);
  return [
    ['Rodada', html`${lastRound(r)} <${Dim}>/ ${r.max_rounds}<//>`, 'Em cada rodada, todos os hospitais treinam uma época e o servidor faz a média.'],
    ['Acurácia balanceada (validação)', nf(last.val_bacc, 3), html`Melhor até agora: <b>${nf(bestVal(r), 3)}</b>. 0,33 = chute; 1 = perfeito.`, flash ? 'hit' : ''],
    ['Perda: treino / validação', html`${nf(last.train_loss, 3)} <${Dim}>/ ${nf(last.val_loss, 3)}<//>`, 'Entropia cruzada; menor é melhor. A de treino é a média dos hospitais.'],
    ['F1 macro · AUC (validação)', html`${nf(last.val_f1, 3)} <${Dim}>· ${nf(last.val_auc, 3)}<//>`, 'F1 equilibra precisão e revocação; AUC mede o quanto o modelo separa as classes.'],
    ['Alinhamento dos hospitais', nf(last.cos_mean, 2), 'Cosseno médio entre a atualização de cada hospital e a média. Baixo = client drift.'],
    ['Trafegado até agora', bytes(last.cum_bytes), `${bytes(last.round_bytes)} por rodada (envio e retorno, todos os hospitais).`],
    ['Velocidade', last.imgs_per_sec ? html`${nf(last.imgs_per_sec, 0)} <span style="font-size:14px" class="dim">img/s</span>` : `${nf(last.sec, 1)} s`, `${nf(last.sec, 1)} s por rodada, incluindo a validação.`],
    r.summary ? ['Resultado no teste', nf(r.summary.test_bacc, 3), `AUC ${nf(r.summary.test_auc, 3)} · F1 por classe (${CLASSES.map(c => c.name.toLowerCase()).join(' / ')}): ${(r.summary.f1_per_class || []).map(x => nf(x, 2)).join(' / ')}`, 'hl']
      : ['Teste parcial', nf(lastTest?.test_bacc, 3), lastTest ? `Acurácia balanceada no teste na rodada ${lastTest.round}. Medida a cada 10 rodadas.` : 'Medida a cada 10 rodadas.'],
  ];
}

// No replay os eixos ficam fixos na execução inteira, para a curva não mudar de escala enquanto anda.
function learningChart(r, rp) {
  const line = (label, rows, key, color, extra) => ({label, data: rows.map(q => ({x: q.round, y: q[key]})), borderColor: css(color), backgroundColor: css(color), pointRadius: 0, tension: .25, ...extra});
  const ds = [
    line('Acurácia balanceada (val.)', r.rows, 'val_bacc', '--accent', {yAxisID: 'y', borderWidth: 2.2}),
    line('Perda de validação', r.rows, 'val_loss', '--m2', {yAxisID: 'y1', borderWidth: 1.6}),
    line('Perda de treino', r.rows.filter(q => q.train_loss != null), 'train_loss', '--faint', {yAxisID: 'y1', borderWidth: 1.6, borderDash: [4, 3]}),
  ];
  if (r.ghost) ['val_bacc', 'val_loss', 'train_loss'].forEach((k, i) => r.ghost[k] != null && ds[i].data.push({x: r.ghost.round, y: r.ghost[k]}));
  const o = chartOpts('Rodada', 'Acurácia balanceada'); o.scales.x.type = 'linear';
  o.scales.y1 = {position: 'right', ...axis('Perda'), grid: {display: false}, border: {display: false}};
  if (rp) {
    o.scales.x.min = 0; o.scales.x.max = r.max_rounds; o.scales.y.min = .3; o.scales.y.max = Math.max(.85, ...rp.rows.map(q => q.val_bacc));
    o.scales.y1.max = Math.max(...rp.rows.map(q => Math.max(q.val_loss ?? 0, q.train_loss ?? 0)));
    if (reachedTarget(rp)) ds.push({label: `Alvo ${nf(rp.target, 2)} na rodada ${rp.hit.round}`, data: [{x: rp.hit.round, y: .3}, {x: rp.hit.round, y: 1}],
      borderColor: css('--ok'), borderDash: [3, 3], borderWidth: 1.2, pointRadius: 0, yAxisID: 'y'});
  }
  return {type: 'line', data: {datasets: ds}, options: o};
}

function driftChart(r, rp) {
  const drift = [...r.rows, ...(r.ghost ? [r.ghost] : [])].filter(q => q.cos_mean != null);
  const o = chartOpts('Rodada', 'Alinhamento (cosseno)'); o.scales.x.type = 'linear'; o.scales.y.suggestedMin = 0; o.scales.y.suggestedMax = 1;
  if (rp) { o.scales.x.min = 0; o.scales.x.max = r.max_rounds; o.scales.y.min = 0; o.scales.y.max = 1; }
  return {type: 'line', data: {datasets: drift.length ? [{label: 'Alinhamento médio', data: drift.map(q => ({x: q.round, y: q.cos_mean})),
    borderColor: css('--m4'), backgroundColor: css('--m4'), borderWidth: 2, pointRadius: 0, tension: .25}] : []}, options: o};
}

export function Live() {
  const D = data.value, base = baseRun.value, rp = replay.value;
  const r = base && (rp ? frameOf(base, rp) : base), gpu = r && gpuOfRun(D, r);
  const title = !D ? 'Escolha uma execução.' : !base ? 'Nenhuma execução nesta grade ainda.'
    : html`<b style="color:var(--text)">${runLabel(r)}</b>${` · seed ${r.seed} · lr ${lrTxt(r.lr)} · ${r.clients.length || NA} hospitais${gpu ? ' · ' + gpuShort(gpu.name) : ''}`}`;
  const charts = r ? {live: learningChart(r, rp), drift: driftChart(r, rp)} : {live: {}, drift: {}};

  return html`<section class="view">
    <div class=${rp ? 'card is-replay' : 'card'} id="liveCard"><${RunMode} base=${base} isReplay=${!!rp} />
      <div class="cardhead"><div class="sub" style="margin:0">${title}</div><${RunPicker} rs=${runs.value} /></div>
      <${ReplayBar} r=${base} /></div>
    <div class="grid4" key=${rp?.flashAt || 0}>${r && kpis(liveKpis(r, !!rp?.flashAt))}</div>
    <div class="grid2">
      <div class="card"><h3>Aprendizado a cada rodada</h3>
        <${Explain}><div>a acurácia deve subir e as perdas, cair. 0,33 é o mesmo que chutar uma das três classes. Perda de treino caindo com a de validação parada indica que os hospitais estão decorando os próprios dados.</div><//>
        <${ChartBox} ...${charts.live} /></div>
      <div class="card"><h3>Alinhamento entre os hospitais</h3>
        <${Explain}><div>perto de 1, todos puxam o modelo para o mesmo lado. Perto de 0, cada um puxa para um lado: é o <i>client drift</i>. Com dados heterogêneos a linha deve ficar mais baixa.</div><//>
        <${ChartBox} ...${charts.drift} /></div>
    </div>
    <div class="card"><h3>Hospitais simulados</h3>
      <${Explain}><div>em IID todos têm a mesma mistura. Com α baixo, cada um fica quase só com uma classe: costuma ter acurácia local alta (acerta a única classe que vê) e alinhamento baixo com a média.</div><//>
      <div class="legend">${CLASSES.map((c, i) => html`<span><i style=${`background:var(--c${i})`}></i>${c.long}</span>`)}</div>
      <div class="scroll">${r && html`<${ClientTable} r=${r} />`}</div></div>
  </section>`;
}
