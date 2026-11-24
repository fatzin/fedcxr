// Execuções: todas as execuções da grade numa tabela.
import {html} from 'htm/preact';
import {RunTable} from '../components/RunTable.js';
import {data, runs} from '../state.js';

export const Runs = () => html`<section class="view"><${RunTable} runs=${data.value ? runs.value : null} /></section>`;
