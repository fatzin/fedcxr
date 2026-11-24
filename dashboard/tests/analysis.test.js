import assert from 'node:assert/strict';
import {test} from 'node:test';
import {gridProgress, groupsOf, hit, insightCards, meanCurve, meanToTarget, pickSeries} from '../app/analysis.js';
import {byHet, chooseGrid, chooseRun, gpuOfRun, guardStats, hName, mName, secLeft, tempLevel} from '../app/domain.js';

const rows = (accs, bytesPerRound = 10) => accs.map((a, i) => ({round: i + 1, val_bacc: a, cum_bytes: bytesPerRound * (i + 1), sec: 2}));
const run = (method, het, seed, accs, extra = {}) =>
  ({name: `${method}_${het}_s${seed}`, method, het, seed, lr: .003, status: 'done', rows: rows(accs, method.includes('lora') ? 1 : 10), max_rounds: accs.length, ...extra});

test('rodadas e bytes até o alvo: a primeira rodada que atinge (igual ao alvo conta)', () => {
  assert.deepEqual(hit(rows([.5, .7, .8, .9]), .75), {R: 3, C: 30});
  assert.deepEqual(hit(rows([.5, .75]), .75), {R: 2, C: 20});
  assert.equal(hit(rows([.5, .6]), .75), null);
});

test('agrupa por método e nível, do IID ao mais heterogêneo, e separa o lr só quando a grade varia o lr', () => {
  const rs = [run('fedavg-full', 'α=0.1', 0, [.5]), run('fedavg-full', 'IID', 0, [.5]), run('fedavg-full', 'IID', 1, [.5]), run('fedavg-lora', 'IID', 0, [.5])];
  assert.deepEqual(groupsOf(rs).map(g => [g.series, g.het, g.runs.length]),
    [['FedAvg', 'IID', 2], ['FedAvg', 'α=0.1', 1], ['FedAvg + LoRA', 'IID', 1]]);
  const lrs = groupsOf([run('fedavg-full', 'IID', 0, [.5]), run('fedavg-full', 'IID', 0, [.5], {lr: .01})]);
  assert.deepEqual(lrs.map(g => g.series), ['FedAvg · lr 0,003', 'FedAvg · lr 0,01']);
});

test('média até o alvo conta só as seeds concluídas que atingiram', () => {
  const [g] = groupsOf([run('fedavg-full', 'IID', 0, [.8]), run('fedavg-full', 'IID', 1, [.5, .8]), run('fedavg-full', 'IID', 2, [.5, .5]),
    run('fedavg-full', 'IID', 3, [.9], {status: 'running'})]);
  assert.deepEqual(meanToTarget(g, .75), {R: 1.5, C: 15});
  assert.equal(meanToTarget(g, .95), null);
});

test('curva média vai até a rodada que todas as seeds têm', () => {
  const [g] = groupsOf([run('fedavg-full', 'IID', 0, [.4, .6, .8]), run('fedavg-full', 'IID', 1, [.6, .8])]);
  assert.deepEqual(meanCurve(g, 'round'), [{x: 1, y: .5}, {x: 2, y: .7}]);
});

test('série das curvas: a salva se existe nesta grade, senão o FedAvg completo, senão a primeira', () => {
  const gs = groupsOf([run('fedavg-lora', 'IID', 0, [.5]), run('fedavg-full', 'IID', 0, [.5]), run('scaffold-full', 'IID', 0, [.5])]);
  assert.equal(pickSeries(gs, 'SCAFFOLD'), 'SCAFFOLD');
  assert.equal(pickSeries(gs, 'FedProx'), 'FedAvg');
  assert.equal(pickSeries(groupsOf([run('scaffold-full', 'IID', 0, [.5])]), null), 'SCAFFOLD');
  assert.equal(pickSeries([], 'x'), null);
});

test('cartões H1 e H2: nível mais heterogêneo contra IID, e FedAvg completo contra FedAvg + LoRA', () => {
  const gs = groupsOf([
    run('fedavg-full', 'IID', 0, [.8]), run('fedavg-full', 'α=0.5', 0, [.5, .8]), run('fedavg-full', 'α=0.1', 0, [.5, .6, .8]),
    run('fedavg-lora', 'α=0.1', 0, [.5, .8]), run('fedavg-lora', 'IID', 0, [.5]),
    run('fedprox-full', 'IID', 0, [.8]), run('fedprox-full', 'α=0.1', 0, [.5, .5, .5, .8]), run('fedprox-lora', 'α=0.1', 0, [.8])]);
  const [h1, h2, miss] = insightCards(gs, .75, 'FedAvg');
  assert.equal(h1[1], '3,00×');
  assert.match(h1[2], /α = 0,1/);
  assert.equal(h2[1], '15×');
  assert.equal(miss[1], '1');
  assert.equal(insightCards(gs, .75, 'FedProx')[0][1], '4,00×');
  assert.equal(insightCards([], .75, null)[0][1], 'n/d');
});

test('andamento da grade: fila, tempo por execução e tempo restante com as GPUs em paralelo', () => {
  const done = run('fedavg-full', 'IID', 0, [.8], {summary: {wall_sec: 100, test_bacc: .7}});
  const going = run('fedavg-full', 'IID', 1, [.5, .6], {status: 'running', max_rounds: 10});
  const p = gridProgress([done, going], 4, 2);
  assert.equal(p.pending, 2);
  assert.equal(p.secPerRun, 100);
  assert.equal(secLeft(going), 16);
  assert.equal(p.eta, (2 * 100 + 16) / 2);
  assert.equal(p.best, done);
  const onlyGoing = gridProgress([going], 3, 1);
  assert.equal(onlyGoing.secPerRun, 2 * 10);
  assert.equal(onlyGoing.eta, 2 * 20 + 16);
});

test('grade mostrada: a escolhida fica; sem escolha, vai para a que está rodando', () => {
  const g = (grid, status, updated) => ({grid, runs: [{status, updated}]});
  const grids = [g('a', 'done', 10), g('b', 'running', 20)];
  assert.equal(chooseGrid(grids, 'a', true), 'a');
  assert.equal(chooseGrid(grids, 'a', false), 'b');
  assert.equal(chooseGrid([g('a', 'done', 10), g('c', 'done', 20)], null, false), 'c');
  assert.equal(chooseGrid([g('a', 'done', 10), g('c', 'done', 20)], 'a', false), 'a');
  assert.equal(chooseGrid([], 'a', true), null);
});

test('execução mostrada: a escolhida, senão a que treina, a em andamento ou a mais recente', () => {
  const r = (name, status, updated) => ({name, status, updated});
  assert.equal(chooseRun([r('a', 'done', 1), r('b', 'running', 0)], 'a', true), 'a');
  assert.equal(chooseRun([r('a', 'done', 1), r('b', 'running', 0)], 'a', false), 'b');
  assert.equal(chooseRun([r('a', 'done', 1), r('b', 'paused', 0)], null, false), 'b');
  assert.equal(chooseRun([r('a', 'paused', 1), r('b', 'running', 0)], null, false), 'b');
  assert.equal(chooseRun([r('a', 'done', 1), r('b', 'done', 3)], 'sumiu', true), 'b');
});

test('GPU da execução pelo pid ou pelo barramento gravado', () => {
  const data = {gpus: [{bus: '00000000:01:00.0'}, {bus: '00000000:02:00.0'}], procs: [{pid: 7, bus: '00000000:02:00.0'}]};
  assert.equal(gpuOfRun(data, {pid: 7}), data.gpus[1]);
  assert.equal(gpuOfRun(data, {pid: 8, gpu_bus: '0000:01:00.0'}), data.gpus[0]);
  assert.equal(gpuOfRun(data, {pid: null}), null);
});

test('temperatura: alerta a partir de 80 °C e crítico a 3 °C do limite de pausa', () => {
  assert.equal(tempLevel(70, 88), '');
  assert.equal(tempLevel(80, 88), 'warn');
  assert.equal(tempLevel(85, 88), 'bad');
});

test('pausas da proteção térmica: contagens e tempo pausado, inclusive a pausa em aberto', () => {
  const now = 100_000, ev = (kind, t, gpu = 0) => ({kind, t: now - t, gpu});
  const st = guardStats({events: [ev('pause', 7200), ev('resume', 7000), ev('pause', 600, 1), ev('info', 10)]}, now);
  assert.deepEqual(st, {p1h: 1, p24: 2, pausedSec: 200 + 600, openGpus: [1]});
  const long = guardStats({events: [ev('pause', 30 * 3600), ev('resume', 3600)]}, now);
  assert.equal(long.pausedSec, 23 * 3600);
});

test('nomes de método e nível a partir das chaves do backend', () => {
  assert.equal(mName('fedavg-lora'), 'FedAvg + LoRA');
  assert.equal(mName('fedprox-full-mu0.001'), 'FedProx · μ 0,001');
  assert.equal(mName('fedavg-lora-r16'), 'FedAvg + LoRA · r 16');
  assert.equal(mName('nova'), 'nova');
  assert.equal(hName('α=0.1'), 'α = 0,1 · extrema');
  assert.equal(hName('α=0.7'), 'α = 0,7');
  assert.deepEqual(['α=0.1', 'IID', 'α=1.0', 'α=0.3'].sort(byHet), ['IID', 'α=1.0', 'α=0.3', 'α=0.1']);
});
