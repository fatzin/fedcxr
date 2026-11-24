import assert from 'node:assert/strict';
import {test} from 'node:test';
import {NA, ago, bytes, dur, lrTxt, nf, plural} from '../app/format.js';

test('valor ausente ou não finito vira n/d', () => {
  assert.equal(NA, 'n/d');
  for (const x of [null, undefined, NaN, Infinity]) assert.equal(nf(x), 'n/d');
  assert.equal(bytes(null), 'n/d');
  for (const s of [0, -5, NaN, Infinity]) assert.equal(dur(s), 'n/d');
});

test('números em pt-BR, com vírgula decimal e ponto de milhar', () => {
  assert.equal(nf(0.75), '0,75');
  assert.equal(nf(1234.5, 1), '1.234,5');
  assert.equal(nf(4706, 0), '4.706');
  assert.equal(lrTxt(0.003), '0,003');
});

test('bytes em MB até 1 GB, com uma casa abaixo de 100 MB', () => {
  assert.equal(bytes(1734247980), '1,7 GB');
  assert.equal(bytes(250e6), '250 MB');
  assert.equal(bytes(12.34e6), '12,3 MB');
});

test('durações em s, min e h', () => {
  assert.equal(dur(30), '30 s');
  assert.equal(dur(180), '3 min');
  assert.equal(dur(5400), '1,5 h');
});

test('tempo relativo', () => {
  const now = 1_800_000_000;
  assert.equal(ago(now - 10, now), 'agora');
  assert.equal(ago(now - 600, now), 'há 10 min');
  assert.equal(ago(now - 7200, now), 'há 2 h');
});

test('plural só para quantidade diferente de 1', () => {
  assert.equal(plural(1, 'GPU'), 'GPU');
  assert.equal(plural(0, 'GPU'), 'GPUs');
  assert.equal(plural(3, 'seed'), 'seeds');
});
