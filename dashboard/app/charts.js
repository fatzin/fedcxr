// Opções e cores dos gráficos, com as cores do tema lidas dos tokens CSS.
import {nf} from './format.js';
import {css} from './theme.js';

const METHOD_TOKENS = ['--m1', '--m2', '--m3', '--m4', '--m5', '--m6'];
export const methodToken = i => METHOD_TOKENS[i % METHOD_TOKENS.length];

// do mais claro (i = 0) ao mais escuro (i = n - 1)
export function hetColor(i, n) {
  const a = +css('--het-light'), b = +css('--het-dark');
  return `hsl(${css('--het-hue')} 85% ${n <= 1 ? (a + b) / 2 : a - (a - b) * i / (n - 1)}%)`;
}

// eixo com título (escondido quando vazio) e marcas na cor apagada do tema
export const axis = title => {
  const muted = css('--muted');
  return {title: {display: !!title, text: title, color: muted, font: {size: 12}}, ticks: {color: muted, font: {size: 11}}};
};

export function chartOpts(xTitle, yTitle) {
  const muted = css('--muted'), hair = css('--hairline');
  return {responsive: true, maintainAspectRatio: false, animation: false, interaction: {mode: 'index', intersect: false},
    plugins: {legend: {position: 'bottom', labels: {color: muted, usePointStyle: true, pointStyle: 'circle', boxWidth: 7, boxHeight: 7, padding: 14, font: {size: 12}}},
      tooltip: {backgroundColor: css('--surface-2'), titleColor: css('--text'), bodyColor: css('--text'), borderColor: hair, borderWidth: 1, padding: 10, cornerRadius: 0,
        usePointStyle: true, boxPadding: 4, callbacks: {label: c => `${c.dataset.label}: ${nf(c.parsed.y, Math.abs(c.parsed.y) >= 100 ? 0 : 3)}`}}},
    scales: {x: {...axis(xTitle), grid: {display: false}, border: {color: hair}}, y: {...axis(yTitle), grid: {color: hair}, border: {display: false}}}};
}

// Curvas de acurácia com a linha tracejada do alvo t.
export function lineWithTarget(datasets, xTitle, t) {
  const o = chartOpts(xTitle, 'Acurácia balanceada (val.)'); o.scales.x.type = 'linear';
  const xmax = Math.max(0, ...datasets.flatMap(d => d.data.map(p => p.x)));
  const target = {label: `Alvo ${nf(t, 2)}`, data: [{x: 0, y: t}, {x: xmax, y: t}], borderColor: css('--faint'), borderDash: [5, 5], pointRadius: 0, borderWidth: 1};
  return {type: 'line', data: {datasets: xmax > 0 ? [...datasets, target] : datasets}, options: o};
}

export function bars(labels, datasets, yTitle, log) {
  const o = chartOpts('', yTitle); if (log) o.scales.y.type = 'logarithmic';
  return {type: 'bar', data: {labels, datasets}, options: o};
}
