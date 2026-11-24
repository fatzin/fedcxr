// Textos de números, tamanhos, tempos e datas em pt-BR.

// marcador de valor ausente (sem travessão em lugar nenhum do painel)
export const NA = 'n/d';

export const nf = (x, d = 2) => x == null || !isFinite(x) ? NA
  : Number(x).toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
export const dur = s => !isFinite(s) || s <= 0 ? NA : s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${nf(s / 3600, 1)} h`;
export const bytes = b => b == null ? NA : b >= 1e9 ? `${nf(b / 1e9, 1)} GB` : `${nf(b / 1e6, b >= 1e8 ? 0 : 1)} MB`;
export const lrTxt = lr => String(lr).replace('.', ',');
export const gpuShort = n => (n || '').replace('NVIDIA GeForce ', '');
export const plural = (n, word) => n === 1 ? word : `${word}s`;

export const clock = t => new Date(t * 1000).toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
export const dateTime = t => new Date(t * 1000).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
export const ago = (t, now) => {
  const s = now - t;
  return s < 60 ? 'agora' : s < 3600 ? `há ${Math.round(s / 60)} min` : s < 86400 ? `há ${nf(s / 3600, 0)} h`
    : new Date(t * 1000).toLocaleDateString('pt-BR');
};
