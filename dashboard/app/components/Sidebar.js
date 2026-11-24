// Barra lateral: telas agrupadas com contadores, lista de grades e estado da conexão.
import {html} from 'htm/preact';
import {active, tempLevel} from '../domain.js';
import {NA, plural} from '../format.js';
import {go, route} from '../router.js';
import {VIEWS, viewHash, viewOf} from '../routes.js';
import {SCREENS} from '../screens.js';
import {closeDrawer, setSide} from '../side.js';
import {conn, data, grid, liveGrids, pickGrid, runs} from '../state.js';
import {NavIcon, PanelIcon} from './icons.js';
import {Segmented} from './ui.js';

// [texto, classe] do contador ao lado de cada tela
function badges(D) {
  const G = D.guard, nAct = runs.value.filter(active).length;
  const hot = D.gpus.some(g => tempLevel(g.temp, G.hot) === 'bad'), paused = D.grids.some(gr => gr.runs.some(r => r.status === 'paused'));
  return {runs: [nAct ? String(nAct) : '', 'ok'], infra: [!G.alive ? '!' : paused ? 'pausa' : hot ? 'quente' : '', !G.alive ? 'bad' : 'warn']};
}

function Nav() {
  const {view, deep} = route.value, on = deep ? 'runs' : view, b = data.value ? badges(data.value) : {};
  const groups = [...new Set(VIEWS.map(v => v.group))];
  return html`<nav class="navgroup" onClick=${e => { if (e.target.closest('.nav')) closeDrawer(); }}>${groups.map(grp => html`
    <div class="navgroup"><div class="navlabel">${grp}</div>${VIEWS.filter(v => v.group === grp).map(v => { const [text, cls] = b[v.id] || ['', '']; return html`
      <a class="nav" href=${viewHash(v.id)} aria-current=${v.id === on ? 'page' : undefined}><${NavIcon} paths=${SCREENS[v.id].icon} />${v.name}<span class=${cls ? `badge ${cls}` : 'badge'} hidden=${!text}>${text}</span></a>`; })}</div>`)}</nav>`;
}

// trocar de grade com uma execução aberta volta para a lista de execuções
function choose(g) {
  pickGrid(g);
  if (route.value.deep) go(viewHash('runs'));
}

function Grids() {
  const gs = data.value?.grids || [];
  return html`<div class="navgroup" style=${viewOf(route.value.view).usesGrid ? '' : 'display:none'}><div class="navlabel">Grades</div>
    <${Segmented} cls="gridlist" label="Grade de experimentos" options=${gs.map(g => [g.grid, html`${g.grid}<span class="cnt">${g.runs.length}</span>`])}
      current=${grid.value} onPick=${choose} live=${liveGrids.value} /></div>`;
}

function Foot() {
  const D = data.value, c = conn.value;
  return html`<div class="sidefoot">
    <div class=${c.off ? 'live off' : 'live'}><i></i><span>${c.text}</span></div>
    <div>${D ? html`<b>${D.host || 'PC'}</b> · ${D.gpus.length} ${plural(D.gpus.length, 'GPU')} · proteção ${D.guard.alive ? html`<span class="ok">ativa</span>` : html`<span class="bad">desligada</span>`}` : NA}</div></div>`;
}

export const Sidebar = () => html`<aside class="side" aria-label="Navegação">
  <div class="brand"><span>fedcxr</span><button type="button" class="iconbtn" aria-label="Recolher a barra lateral" onClick=${() => setSide(false)}><${PanelIcon} close /></button></div>
  <${Nav} /><${Grids} /><${Foot} /></aside>`;
