// Componente e ícone de cada tela de routes.js (VIEWS).
import {html} from 'htm/preact';
import {Data} from './views/Data.js';
import {Glossary} from './views/Glossary.js';
import {Hyp} from './views/Hyp.js';
import {Infra} from './views/Infra.js';
import {Live} from './views/Live.js';
import {Overview} from './views/Overview.js';
import {Runs} from './views/Runs.js';

export const SCREENS = {
  overview: {View: Overview, icon: html`<path d="M3 13h7V4H3zM14 20h7v-9h-7zM3 20h7v-4H3zM14 4v4h7V4z"/>`},
  runs: {View: Runs, icon: html`<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>`},
  live: {View: Live, icon: html`<path d="M3 12h4l3-8 4 16 3-8h4"/>`},
  hyp: {View: Hyp, icon: html`<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>`},
  data: {View: Data, icon: html`<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>`},
  infra: {View: Infra, icon: html`<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>`},
  glossary: {View: Glossary, icon: html`<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5zM4 21.5A2.5 2.5 0 0 0 6.5 24"/><path d="M8 7h8M8 11h6"/>`},
};
