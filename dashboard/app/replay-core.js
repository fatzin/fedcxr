// Simulação de uma execução gravada, rodada a rodada. Estado imutável: cada função devolve um estado novo.
// k vai de 1 ao número de linhas; a parte fracionária de k é o quanto já andou rumo à próxima rodada.
import {hitIndex} from './analysis.js';

export const SPEEDS = [['2', '1×'], ['6', '3×'], ['15', '8×']];  // [rodadas por segundo, rótulo]
export const DEFAULT_SPEED = '6';
const MAX_STEP_MS = 100;  // um quadro atrasado (aba em segundo plano) não pula rodadas

// id: identifica a execução (o replay de outra execução é outro replay)
export function createReplay(id, rows, target, {k = 1, playing = true} = {}) {
  const i = hitIndex(rows, target);
  return {id, rows, target, k: clampK(rows, k), playing, hit: i < 0 ? null : {k: i + 1, round: rows[i].round}, flashAt: 0};
}

const clampK = (rows, k) => Math.max(1, Math.min(rows.length, k));
const ended = rp => rp.k >= rp.rows.length;
export const reachedTarget = rp => rp.hit != null && rp.k >= rp.hit.k;

// flashAt marca o instante em que a reprodução cruzou o alvo (não muda ao arrastar a barra).
export function advance(rp, dtMs, roundsPerSec, now) {
  if (!rp.playing) return rp;
  const k = Math.min(rp.rows.length, rp.k + roundsPerSec * Math.min(dtMs, MAX_STEP_MS) / 1000);
  const crossed = rp.hit != null && rp.k < rp.hit.k && k >= rp.hit.k;
  return {...rp, k, playing: k < rp.rows.length, flashAt: crossed ? now : rp.flashAt};
}

export const seek = (rp, k) => ({...rp, k: clampK(rp.rows, k)});
export const pause = rp => ({...rp, playing: false});
// no fim, reproduzir recomeça da primeira rodada
export const togglePlaying = rp => rp.playing ? pause(rp)
  : ended(rp) ? {...rp, k: 1, playing: true, flashAt: 0} : {...rp, playing: true};

// A execução como aparece em k, com um ponto interpolado (ghost) entre rodadas para a curva andar suave.
export function frameOf(run, rp) {
  const n = Math.floor(rp.k), rows = rp.rows.slice(0, n), cur = rows.at(-1), next = rp.rows[n], frac = rp.k - n;
  let ghost = null;
  if (frac > 0 && next) {
    const num = x => typeof x === 'number';
    ghost = Object.fromEntries(Object.keys(cur).map(key => [key, num(cur[key]) && num(next[key]) ? cur[key] + (next[key] - cur[key]) * frac : undefined]));
  }
  const done = n >= rp.rows.length;
  // sem client_stats nas linhas (/api/run indisponível), a tabela de hospitais fica só com a partição
  return {...run, rows, ghost, summary: done ? run.summary : null, client_stats: cur?.client_stats ?? null};
}
