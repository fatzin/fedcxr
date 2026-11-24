// Preferências salvas no localStorage do navegador.
import {effect, signal} from '@preact/signals';

// localStorage lança em modo privado ou com o armazenamento bloqueado; aí as preferências só não são salvas.
function load(key) {
  try { return JSON.parse(localStorage.getItem(key) ?? 'null'); } catch (e) { return null; }
}

// Signal gravado a cada mudança; fromSaved recebe o valor salvo (null se não há) e devolve o valor inicial.
export function persisted(key, fromSaved) {
  const s = signal(fromSaved(load(key)));
  effect(() => {
    const value = JSON.stringify(s.value);
    try { localStorage.setItem(key, value); } catch (e) { /* ver load */ }
  });
  return s;
}
