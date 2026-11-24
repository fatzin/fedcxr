// Comandos para rodar uma grade em cada ambiente (Local, Colab, Modal), a partir do /api/launch-info. Não executa nada.

export const TARGETS = [['local', 'Local'], ['colab', 'Colab'], ['modal', 'Modal']];
export const MODAL_MODES = [['run', 'Acompanhar daqui'], ['deploy', 'Implantado']];
export const DEFAULT_PREFS = {target: 'local', grid: 'h2', mode: 'run', per: {}, gpus: null, dry: false};
const GRID_NOTES = {paper: 'artigo', smoke: 'teste rápido'};
// alvo salvo que não existe mais (preferência antiga) volta para o padrão
export const validTarget = t => TARGETS.some(([id]) => id === t) ? t : DEFAULT_PREFS.target;

// Grades do launch-info mais a "paper" (todas as do artigo), com o número de execuções.
const gridOptions = info => [...info.grids.map(g => ({name: g.name, runs: g.runs})), {name: 'paper', runs: info.paper.runs}]
  .map(g => ({...g, label: `${g.name} · ${g.runs}${GRID_NOTES[g.name] ? ` (${GRID_NOTES[g.name]})` : ''}`}));

// Sem nvidia-smi nesta máquina, oferece a GPU 0.
const gpuOptions = gpus => gpus.length ? gpus.map(g => ({id: String(g.index), name: g.name})) : [{id: '0', name: 'GPU'}];

// prefs: o que a pessoa escolheu (formato de DEFAULT_PREFS); gpus: as de /api/state; guardAlive: a proteção térmica roda.
// Devolve também as GPUs para escolher ([{id, name}]), os passos ([rótulo, comando]) e as notas ({text, warn?, href?}).
export function launchPlan(info, prefs, gpus, guardAlive) {
  const target = validTarget(prefs.target);
  const grids = gridOptions(info), grid = grids.some(g => g.name === prefs.grid) ? prefs.grid : DEFAULT_PREFS.grid;
  const runs = grids.find(g => g.name === grid)?.runs;
  const gpuOpts = gpuOptions(gpus), ids = gpuOpts.map(g => g.id), chosen = (prefs.gpus || ids).filter(id => ids.includes(id));
  const gpuSel = chosen.length ? chosen : [ids[0]];
  const per = prefs.per?.[target] || info[target].default_k;
  const gd = info.guard_defaults, steps = [], notes = [];
  if (runs) notes.push({text: `${runs} execuções na grade`});
  if (target === 'local') {
    steps.push(['Terminal, na pasta do repositório', `.venv/bin/python scripts/run_grid.py --grid ${grid} --gpus ${gpuSel.join(',')} --per-gpu ${per}${prefs.dry ? ' --dry-run' : ''}`]);
    if (!guardAlive) steps.push(['Proteção térmica (desligada)', `nohup .venv/bin/python scripts/thermal_guard.py --hot ${gd.hot} --cool ${gd.cool} >> thermal_guard.log 2>&1 &`]);
    notes.push({text: `${gpuSel.length * per} execuções ao mesmo tempo`});
  } else if (target === 'colab') {
    steps.push(['Célula do notebook, depois das células de instalação e dados', `!python scripts/run_grid.py --grid ${grid} --gpus 0 --per-gpu ${per} --extra train.amp=fp16 train.save_model=false`]);
    notes.push({text: 'Abrir notebook no Colab ↗', href: info.colab.url});
    if (runs > info.colab.max_runs) notes.push({text: 'Não cabe numa sessão do Colab. Divida em várias sessões.', warn: true});
  } else {
    steps.push(['Primeira vez', 'pip install -r requirements-modal.txt\nmodal setup\nmodal run modal_run.py::prepare'],
      prefs.mode === 'run' ? ['Rodar a grade', `modal run modal_run.py::grid --name ${grid} --k ${per}`]
        : ['Implantar e disparar', `modal deploy modal_run.py\npython modal_run.py ${grid} ${per}`]);
    notes.push({text: `Resultados no Volume ${info.modal.volume}`}, {text: 'Usa créditos do Modal', warn: true});
  }
  notes.push({text: 'Execuções concluídas são puladas'});
  return {target, grids, grid, gpus: gpuOpts, gpuSel, per, steps, notes};
}
