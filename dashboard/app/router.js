// Rota atual a partir do hash da página; um hash de execução escolhe a grade e a execução.
import {batch, signal} from '@preact/signals';
import {parseHash, runHash, samePage} from './routes.js';
import {grid, pickRun} from './state.js';

export const route = signal(parseHash(''));

function follow() {
  const prev = route.value, next = parseHash(location.hash), deep = next.deep;
  batch(() => {
    if (deep) pickRun(deep.grid, deep.name);
    route.value = next;
  });
  if (!samePage(prev, next)) scrollTo({top: 0});
}

export function startRouter() {
  addEventListener('hashchange', follow);
  follow();
}

export const go = hash => { location.hash = hash; };
export const openRun = (name, replay = false) => go(runHash(grid.value, name, replay));
