// Ícones de traço de 24 px: o da navegação recebe os traços da tela (screens.js); o painel abre ou recolhe a barra lateral.
import {html} from 'htm/preact';

export const NavIcon = ({paths}) => html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;

export const PanelIcon = ({close}) => html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="square" aria-hidden="true"><rect x="3.5" y="4.5" width="17" height="15"/><path d=${close ? 'M9.5 4.5v15M15.5 10l-2 2 2 2' : 'M9.5 4.5v15'}/></svg>`;
