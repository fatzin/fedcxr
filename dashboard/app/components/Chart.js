// Gráfico do Chart.js que atualiza no lugar (sem recriar) enquanto o tipo não muda; sem data, não desenha nada.
import {html} from 'htm/preact';
import {useEffect, useLayoutEffect, useRef} from 'preact/hooks';

// o Chart.js vem de /vendor/chart.umd.js como global
const ChartJS = window.Chart;
if (ChartJS) ChartJS.defaults.font.family = getComputedStyle(document.body).fontFamily;

export function Chart({type, data, options}) {
  const canvas = useRef(null), chart = useRef(null);
  useLayoutEffect(() => {
    const c = chart.current;
    if (c && data && c.config.type === type) { c.data = data; c.options = options; c.update('none'); return; }
    c?.destroy();
    chart.current = data && ChartJS ? new ChartJS(canvas.current, {type, data, options}) : null;
  });
  useEffect(() => () => chart.current?.destroy(), []);
  return html`<canvas ref=${canvas}></canvas>`;
}

export const ChartBox = ({size, ...p}) => html`<div class=${size ? `chartbox ${size}` : 'chartbox'}><${Chart} ...${p} /></div>`;
