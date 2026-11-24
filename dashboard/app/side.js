// Barra lateral: no desktop fica aberta ou recolhida (preferência salva); no celular é uma gaveta que começa fechada.
import {computed, signal} from '@preact/signals';
import {persisted} from './prefs.js';

const narrowQuery = matchMedia('(max-width: 640px)');
const narrow = signal(narrowQuery.matches);
const pinned = persisted('fedcxr-side', saved => saved ?? 1);  // 1 aberta, 0 recolhida
const drawer = signal(false);

export const sideOpen = computed(() => narrow.value ? drawer.value : pinned.value !== 0);
export function setSide(open) {
  if (narrow.peek()) drawer.value = open; else pinned.value = open ? 1 : 0;
}
export const closeDrawer = () => { drawer.value = false; };

narrowQuery.addEventListener('change', e => { drawer.value = false; narrow.value = e.matches; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
