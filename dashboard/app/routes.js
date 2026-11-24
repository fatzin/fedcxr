// Telas e formato dos hashes: #/<tela>; #/run/<grade>/<execução> abre uma execução e /replay no fim, a simulação dela.

export const VIEWS = [
  {id: 'overview', group: 'Monitorar', name: 'Visão geral', usesGrid: true},
  {id: 'runs', group: 'Monitorar', name: 'Execuções', usesGrid: true},
  {id: 'live', group: 'Monitorar', name: 'Treino ao vivo', usesGrid: true},
  {id: 'hyp', group: 'Analisar', name: 'Hipóteses', usesGrid: true},
  {id: 'data', group: 'Analisar', name: 'Dados', usesGrid: true},
  {id: 'infra', group: 'Sistema', name: 'Infraestrutura', usesGrid: false},
  {id: 'glossary', group: 'Sistema', name: 'Glossário', usesGrid: false},
];
const HOME = 'overview';

export const viewOf = id => VIEWS.find(v => v.id === id);

export const viewHash = id => `#/${id}`;
export const runHash = (grid, name, replay = false) =>
  `#/run/${encodeURIComponent(grid)}/${encodeURIComponent(name)}${replay ? '/replay' : ''}`;

// {view, deep}: deep = {grid, name, replay} quando o hash abre uma execução.
export function parseHash(hash) {
  const m = hash.match(/^#\/run\/([^/]+)\/([^/]+?)(\/replay)?$/);
  if (m) {
    try {
      return {view: 'live', deep: {grid: decodeURIComponent(m[1]), name: decodeURIComponent(m[2]), replay: !!m[3]}};
    } catch (e) {
      if (!(e instanceof URIError)) throw e;
      return {view: HOME, deep: null};
    }
  }
  const id = (hash.match(/^#\/(\w+)/) || [])[1];
  return {view: viewOf(id) ? id : HOME, deep: null};
}

// Mesma tela e mesma execução: trocar só o /replay não volta a página para o topo.
export const samePage = (a, b) => a.view === b.view && a.deep?.grid === b.deep?.grid && a.deep?.name === b.deep?.name;
