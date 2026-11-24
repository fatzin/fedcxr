// Configurar treino: monta o comando de cada ambiente (Local, Colab, Modal) com launch-plan.js. Não executa nada.
import {html} from 'htm/preact';
import {useEffect, useRef, useState} from 'preact/hooks';
import {DEFAULT_PREFS, MODAL_MODES, TARGETS, launchPlan, validTarget} from '../launch-plan.js';
import {persisted} from '../prefs.js';
import {data, launch} from '../state.js';
import {Segmented} from './ui.js';

const prefs = persisted('fedcxr-launch', saved => ({...DEFAULT_PREFS, ...saved}));
const setPrefs = patch => { prefs.value = {...prefs.value, ...patch}; };
const PER_MAX = 16;

function Step({label, cmd}) {
  const [copied, setCopied] = useState(false), pre = useRef(null), timer = useRef(0);
  useEffect(() => () => clearTimeout(timer.current), []);
  async function copy() {
    // navigator.clipboard só existe em contexto seguro (https ou localhost); pelo IP do Tailscale, copia a seleção
    let ok = true;
    try { await navigator.clipboard.writeText(cmd); }
    catch (err) { const r = document.createRange(); r.selectNodeContents(pre.current); const sl = getSelection(); sl.removeAllRanges(); sl.addRange(r); ok = document.execCommand('copy'); }
    if (!ok) return;
    setCopied(true); clearTimeout(timer.current); timer.current = setTimeout(() => setCopied(false), 1200);
  }
  return html`<div class="lnstep"><div class="rplabel"><span>${label}</span><button type="button" class="linkbtn" onClick=${copy}>${copied ? 'Copiado' : 'Copiar'}</button></div><pre class="cmd" ref=${pre}>${cmd}</pre></div>`;
}

const Note = ({n}) => n.href ? html`<a class="linkbtn" href=${n.href} target="_blank" rel="noopener">${n.text}</a>`
  : n.warn ? html`<span class="warn">${n.text}</span>` : n.text;

export function LaunchCard() {
  const D = data.value, info = launch.value, p = prefs.value;
  const plan = D && info ? launchPlan(info, p, D.gpus, D.guard.alive) : null, target = plan?.target ?? validTarget(p.target);
  const toggleGpu = id => { const cur = new Set(plan.gpuSel); cur.has(id) ? cur.delete(id) : cur.add(id); if (cur.size) setPrefs({gpus: [...cur].sort()}); };
  const setPer = e => { const v = parseInt(e.target.value); if (v > 0) setPrefs({per: {...p.per, [target]: Math.min(PER_MAX, v)}}); };

  return html`<div class="card" id="launchCard">
    <div class="cardhead"><h3>Configurar treino</h3><${Segmented} label="Onde rodar" options=${TARGETS} current=${target} onPick=${v => setPrefs({target: v})} /></div>
    <div class="controls lnform">
      <div class="control"><label for="lnGrid">Grade</label><select id="lnGrid" value=${plan?.grid} onChange=${e => setPrefs({grid: e.target.value})}>${(plan?.grids || []).map(g => html`
        <option key=${g.name} value=${g.name}>${g.label}</option>`)}</select></div>
      ${target === 'local' && html`<div class="control"><label>GPUs</label><${Segmented} label="GPUs usadas"
        options=${plan ? plan.gpus.map(g => [g.id, g.id, g.name]) : []} pressed=${v => plan.gpuSel.includes(v)} onPick=${toggleGpu} /></div>`}
      ${target === 'modal' && html`<div class="control"><label>Modo</label><${Segmented} label="Modo do Modal" options=${MODAL_MODES} current=${p.mode} onPick=${v => setPrefs({mode: v})} /></div>`}
      <div class="control"><label for="lnPer">Execuções por GPU</label>
        <input type="number" id="lnPer" min="1" max=${PER_MAX} step="1" key=${`${target}|${!!plan}`} defaultValue=${plan?.per ?? ''} onInput=${setPer} onBlur=${e => { if (plan) e.target.value = plan.per; }} /></div>
      ${target === 'local' && html`<div class="control"><label class="chk"><input type="checkbox" checked=${p.dry} onChange=${e => setPrefs({dry: e.target.checked})} /> Só listar (dry run)</label></div>`}
    </div>
    <div>${!D ? '' : !plan ? html`<div class="empty">Carregando…</div>` : html`
      ${plan.steps.map(([label, cmd]) => html`<${Step} key=${label} label=${label} cmd=${cmd} />`)}<div class="lnfoot">${plan.notes.map(n => html`<span><${Note} n=${n} /></span>`)}</div>`}</div>
  </div>`;
}
