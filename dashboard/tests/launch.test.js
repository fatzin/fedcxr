import assert from 'node:assert/strict';
import {test} from 'node:test';
import {DEFAULT_PREFS, launchPlan} from '../app/launch-plan.js';

// formato do /api/launch-info
const info = {grids: [{name: 'smoke', runs: 8}, {name: 'h2', runs: 68}, {name: 'sens', runs: 3}], paper: {grids: ['h2', 'sens'], runs: 71},
  guard_defaults: {hot: 88, cool: 75}, modal: {volume: 'vol', default_k: 6}, local: {default_k: 4},
  colab: {url: 'https://colab.example/nb', default_k: 2, max_runs: 40}};
const gpus = [{index: 0, name: 'A'}, {index: 1, name: 'B'}];
const plan = (prefs, g = gpus, alive = true) => launchPlan(info, {...DEFAULT_PREFS, ...prefs}, g, alive);
const texts = p => p.notes.map(n => n.text);

test('local: todas as GPUs, padrão de execuções por GPU do servidor e o total simultâneo', () => {
  const p = plan({grid: 'h2'});
  assert.deepEqual(p.steps, [['Terminal, na pasta do repositório', '.venv/bin/python scripts/run_grid.py --grid h2 --gpus 0,1 --per-gpu 4']]);
  assert.deepEqual(texts(p), ['68 execuções na grade', '8 execuções ao mesmo tempo', 'Execuções concluídas são puladas']);
});

test('local: GPUs escolhidas, dry run e comando da proteção térmica quando ela está desligada', () => {
  const p = plan({gpus: ['1'], per: {local: 3}, dry: true}, gpus, false);
  assert.equal(p.steps[0][1], '.venv/bin/python scripts/run_grid.py --grid h2 --gpus 1 --per-gpu 3 --dry-run');
  assert.equal(p.steps[1][1], 'nohup .venv/bin/python scripts/thermal_guard.py --hot 88 --cool 75 >> thermal_guard.log 2>&1 &');
});

test('local: GPU salva que não existe mais cai na primeira; sem nvidia-smi oferece a GPU 0', () => {
  assert.deepEqual(plan({gpus: ['7']}).gpuSel, ['0']);
  const p = plan({}, []);
  assert.deepEqual(p.gpus, [{id: '0', name: 'GPU'}]);
  assert.match(p.steps[0][1], /--gpus 0 /);
});

test('colab: padrão do servidor, link do notebook e aviso quando a grade não cabe numa sessão', () => {
  const small = plan({target: 'colab', grid: 'sens'});
  assert.equal(small.steps[0][1], '!python scripts/run_grid.py --grid sens --gpus 0 --per-gpu 2 --extra train.amp=fp16 train.save_model=false');
  assert.deepEqual(small.notes[1], {text: 'Abrir notebook no Colab ↗', href: 'https://colab.example/nb'});
  assert.ok(!small.notes.some(n => n.warn));
  assert.ok(plan({target: 'colab', grid: 'paper'}).notes.some(n => n.warn));
  assert.ok(plan({target: 'colab', grid: 'h2'}).notes.some(n => n.warn));
});

test('modal: acompanhar daqui ou implantado, com o volume e o padrão do servidor', () => {
  const run = plan({target: 'modal', grid: 'smoke'});
  assert.deepEqual(run.steps.map(s => s[0]), ['Primeira vez', 'Rodar a grade']);
  assert.equal(run.steps[1][1], 'modal run modal_run.py::grid --name smoke --k 6');
  assert.deepEqual(texts(run), ['8 execuções na grade', 'Resultados no Volume vol', 'Usa créditos do Modal', 'Execuções concluídas são puladas']);
  const deploy = plan({target: 'modal', mode: 'deploy', grid: 'smoke', per: {modal: 9}});
  assert.equal(deploy.steps[1][1], 'modal deploy modal_run.py\npython modal_run.py smoke 9');
});

test('grade salva que não existe volta para o padrão; a lista inclui paper com a contagem do artigo', () => {
  const p = plan({grid: 'sumiu'});
  assert.equal(p.grid, 'h2');
  assert.deepEqual(p.grids.map(g => g.label), ['smoke · 8 (teste rápido)', 'h2 · 68', 'sens · 3', 'paper · 71 (artigo)']);
});

test('ambiente salvo que não existe mais volta para Local', () => {
  const p = plan({target: 'kaggle', per: undefined});
  assert.equal(p.target, 'local');
  assert.match(p.steps[0][1], /--per-gpu 4$/);
});
