// Moldura do painel: barra lateral, barra do topo e a tela da rota atual.
import {html} from 'htm/preact';
import {Sidebar} from './components/Sidebar.js';
import {Toolbar} from './components/Toolbar.js';
import {route} from './router.js';
import {SCREENS} from './screens.js';
import {setSide, sideOpen} from './side.js';

export function App() {
  const {view} = route.value, {View} = SCREENS[view];
  return html`<div class=${sideOpen.value ? 'app' : 'app collapsed'}>
    <div class="scrim" onClick=${() => setSide(false)}></div>
    <${Sidebar} />
    <div><${Toolbar} /><main><${View} key=${view} /></main></div>
  </div>`;
}
