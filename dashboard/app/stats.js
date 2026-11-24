// Média e desvio padrão (populacional) de uma lista de números.
export const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
export const std = a => { const m = mean(a); return Math.sqrt(mean(a.map(x => (x - m) ** 2))); };
