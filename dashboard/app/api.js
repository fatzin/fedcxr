// Rotas JSON do dashboard/server.py.

async function getJSON(url) {
  const res = await fetch(url, {cache: 'no-store'});
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

export const fetchState = () => getJSON('/api/state');
export const fetchLaunchInfo = () => getJSON('/api/launch-info');
// todas as linhas do rounds.jsonl, com client_stats de cada rodada (o /api/state só traz o da última)
export const fetchRunRows = (grid, run) =>
  getJSON(`/api/run?grid=${encodeURIComponent(grid)}&run=${encodeURIComponent(run)}`).then(body => body.rows);
