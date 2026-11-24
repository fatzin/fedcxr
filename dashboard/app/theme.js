// Cores do tema lidas dos tokens CSS, para o Chart.js (que desenha em canvas e não lê var(--x)).
export const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
