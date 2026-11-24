// Ponto de entrada: segue o hash, desenha o App e começa a consultar o servidor.
import {render} from 'preact';
import {html} from 'htm/preact';
import {App} from './App.js';
import {startRouter} from './router.js';
import {startPolling} from './state.js';

startRouter();
render(html`<${App} />`, document.getElementById('root'));
startPolling();
