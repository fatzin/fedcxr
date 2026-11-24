// Peças pequenas reutilizadas pelas telas: KPI, "Como ler", etiqueta de estado, controle segmentado, média ± desvio.
import {html} from 'htm/preact';
import {STATUS} from '../domain.js';
import {NA, nf} from '../format.js';
import {mean, std} from '../stats.js';

// texto puro de uma árvore de vnodes, para o title do KPI
const textOf = v => v == null || v === false ? '' : Array.isArray(v) ? v.map(textOf).join('')
  : typeof v === 'object' ? textOf(v.props?.children) : String(v);

const Kpi = ({k: [label, value, help, cls = '']}) => html`
  <div class=${`card kpi ${cls}`}><div class="eyebrow">${label}</div><div class="big num">${value}</div>
    <div class="help" title=${textOf(help)}>${help}</div></div>`;
// cada item: [rótulo, valor, ajuda, classe]
export const kpis = list => list.map(k => html`<${Kpi} k=${k} />`);

// Explicações longas ficam recolhidas atrás de "Como ler"; open mostra o texto direto.
export const Explain = ({open, style, children}) => open
  ? html`<div class="explain" style=${style}>${children}</div>`
  : html`<details class="explain"><summary>Como ler</summary>${children}</details>`;

export const StatusTag = ({s}) => { const [l, c] = STATUS[s] || STATUS.error; return html`<span class=${`tag ${c}`}>${l}</span>`; };
export const GuardTag = ({alive}) => alive ? html`<span class="tag ok">Ativa</span>` : html`<span class="tag bad">Desligada</span>`;
export const Faint = ({children}) => html`<span style="color:var(--faint)">${children}</span>`;
export const Dim = ({children}) => html`<span class="dim">${children}</span>`;
export const Missing = () => html`<${Faint}>${NA}<//>`;

export const pressKeys = fn => e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(); } };

// options: [valor, rótulo, title?]. Responde no pointerdown (sem esperar soltar) e no Enter/Espaço.
// pressed(valor) decide o aria-pressed quando vários podem estar ligados; live marca os valores que estão rodando.
export function Segmented({cls = 'seg', label, options, current, onPick, live, pressed = v => v === current}) {
  return html`<div class=${cls} role="group" aria-label=${label}>${options.map(([v, text, title]) => html`
    <button type="button" key=${v} title=${title} aria-pressed=${String(pressed(v))}
      onPointerDown=${() => onPick(v)} onKeyDown=${pressKeys(() => onPick(v))}>${live?.has(v) ? html`<span class="ld" aria-label="rodando"></span>` : ''}${text}</button>`)}</div>`;
}

// média ± desvio entre seeds
export const pm = (a, d = 1) => a.length ? html`${nf(mean(a), d)}${a.length > 1 ? html` <${Faint}>± ${nf(std(a), d)}<//>` : ''}` : html`<${Missing} />`;
