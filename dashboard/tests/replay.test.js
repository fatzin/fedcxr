import assert from 'node:assert/strict';
import {test} from 'node:test';
import {advance, createReplay, frameOf, pause, reachedTarget, seek, togglePlaying} from '../app/replay-core.js';

const rows = Array.from({length: 10}, (_, i) => ({round: i + 1, val_bacc: .3 + .05 * i, val_loss: 1 - .05 * i, train_loss: null, cos_mean: .5, client_stats: [{id: i}]}));
const run = {name: 'x', rows, status: 'done', summary: {test_bacc: .7}, client_stats: [{id: 'fim'}]};

test('o alvo é a primeira rodada com acurácia >= alvo; sem ela, não há alvo', () => {
  assert.deepEqual(createReplay('x', rows, .5).hit, {k: 5, round: 5});
  assert.equal(createReplay('x', rows, .99).hit, null);
});

test('anda na velocidade pedida e limita o passo de um quadro atrasado', () => {
  const rp = createReplay('x', rows, .5);
  assert.equal(advance(rp, 500, 6, 0).k, 1 + 6 * .1);  // 500 ms contam como 100 ms
  assert.equal(advance(rp, 50, 2, 0).k, 1.1);
  assert.equal(advance(pause(rp), 50, 2, 0).k, 1);
});

test('para no fim, e reproduzir no fim recomeça da primeira rodada', () => {
  let rp = seek(createReplay('x', rows, .5), 9.9);
  rp = advance(rp, 100, 15, 0);
  assert.equal(rp.k, 10);
  assert.equal(rp.playing, false);
  rp = togglePlaying(rp);
  assert.equal(rp.k, 1);
  assert.equal(rp.playing, true);
});

test('o KPI pisca uma vez, só quando a reprodução cruza o alvo', () => {
  let rp = seek(createReplay('x', rows, .5), 4.9);
  rp = advance(rp, 50, 6, 1234);
  assert.equal(rp.flashAt, 1234);
  assert.ok(reachedTarget(rp));
  assert.equal(advance(rp, 50, 6, 9999).flashAt, 1234);
  const jumped = seek(createReplay('x', rows, .5), 8);
  assert.ok(reachedTarget(jumped));
  assert.equal(jumped.flashAt, 0);
});

test('arrastar fica entre a primeira e a última rodada', () => {
  const rp = createReplay('x', rows, .5);
  assert.equal(seek(rp, 0).k, 1);
  assert.equal(seek(rp, 50).k, 10);
  assert.equal(createReplay('x', rows, .5, {k: 0}).k, 1);
});

test('o quadro mostra as rodadas até k e um ponto interpolado até a próxima', () => {
  const f = frameOf(run, seek(createReplay('x', rows, .5), 3.5));
  assert.equal(f.rows.length, 3);
  assert.equal(f.summary, null);
  assert.deepEqual(f.client_stats, [{id: 2}]);
  assert.equal(f.ghost.round, 3.5);
  assert.ok(Math.abs(f.ghost.val_bacc - .425) < 1e-12);
  assert.equal(f.ghost.train_loss, undefined);
});

test('no fim o quadro é a execução concluída, sem ponto interpolado', () => {
  const f = frameOf(run, seek(createReplay('x', rows, .5), 10));
  assert.equal(f.rows.length, 10);
  assert.equal(f.ghost, null);
  assert.deepEqual(f.summary, run.summary);
});

test('sem client_stats nas linhas, o quadro não usa os números da última rodada', () => {
  const bare = rows.map(({client_stats, ...r}) => r);
  assert.equal(frameOf(run, seek(createReplay('x', bare, .5), 3)).client_stats, null);
});
