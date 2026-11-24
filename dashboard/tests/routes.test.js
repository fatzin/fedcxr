import assert from 'node:assert/strict';
import {test} from 'node:test';
import {VIEWS, parseHash, runHash, samePage, viewHash} from '../app/routes.js';

test('cada tela tem o próprio hash, e hash desconhecido ou vazio cai na visão geral', () => {
  for (const v of VIEWS) assert.deepEqual(parseHash(viewHash(v.id)), {view: v.id, deep: null});
  for (const h of ['', '#', '#/', '#/nada', '#/run', '#/run/h2']) assert.deepEqual(parseHash(h), {view: 'overview', deep: null});
});

test('hash de execução abre a tela ao vivo, com ou sem /replay', () => {
  assert.deepEqual(parseHash('#/run/h2/fedavg-full_iid_s0'), {view: 'live', deep: {grid: 'h2', name: 'fedavg-full_iid_s0', replay: false}});
  assert.deepEqual(parseHash('#/run/h2/fedavg-full_iid_s0/replay').deep, {grid: 'h2', name: 'fedavg-full_iid_s0', replay: true});
});

test('runHash e parseHash são inversos, inclusive com caracteres especiais', () => {
  for (const [g, n] of [['h2', 'a_b'], ['abl mu', 'fedprox-mu0.01/x'], ['α', 'replay']]) {
    for (const replay of [false, true]) assert.deepEqual(parseHash(runHash(g, n, replay)).deep, {grid: g, name: n, replay});
  }
});

test('hash com escape inválido não quebra a página', () => {
  assert.deepEqual(parseHash('#/run/h2/%E0%A4%A'), {view: 'overview', deep: null});
});

test('ligar ou desligar o replay da mesma execução continua na mesma página', () => {
  const a = parseHash(runHash('h2', 'x')), b = parseHash(runHash('h2', 'x', true));
  assert.ok(samePage(a, b));
  assert.ok(!samePage(a, parseHash(runHash('h2', 'y'))));
  assert.ok(!samePage(parseHash('#/runs'), parseHash('#/hyp')));
});
