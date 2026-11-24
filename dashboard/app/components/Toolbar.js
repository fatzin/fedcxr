// Barra do topo: título da tela (ou o modo da execução aberta) e a grade atual / trilha da execução.
import {html} from 'htm/preact';
import {useEffect} from 'preact/hooks';
import {active} from '../domain.js';
import {replaying} from '../replay.js';
import {route} from '../router.js';
import {viewHash, viewOf} from '../routes.js';
import {setSide, sideOpen} from '../side.js';
import {baseRun, data, grid, gridObj, run} from '../state.js';
import {PanelIcon} from './icons.js';

function title() {
  const {view} = route.value, base = baseRun.value;
  if (view !== 'live' || !base) return viewOf(view).name;
  return replaying.value ? 'Replay' : active(base) ? 'Treino ao vivo' : 'Execução';
}

function GridNow() {
  const {view} = route.value;
  if (!data.value || !viewOf(view).usesGrid || !grid.value) return html`<p class="gridnow"></p>`;
  return html`<p class="gridnow">${view === 'live' && run.value
    ? html`<a href=${viewHash('runs')}>Execuções</a> / ${grid.value} / <b>${run.value}</b>`
    : html`grade <b>${grid.value}</b> · ${gridObj.value.runs.length} execuções`}</p>`;
}

export function Toolbar() {
  const t = title(), open = sideOpen.value;
  useEffect(() => { document.title = t; }, [t]);
  return html`<header class="toolbar"><div class="tb">
    <button type="button" class="iconbtn" id="sideOpen" aria-label="Mostrar a barra lateral" aria-expanded=${String(open)} onClick=${() => setSide(true)}><${PanelIcon} /></button>
    <div class="ttl"><h1>${t}</h1><${GridNow} /></div></div></header>`;
}
