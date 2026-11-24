// Glossário dos termos usados no painel.
import {html} from 'htm/preact';

export const Glossary = () => html`<section class="view">
  <div class="card"><dl class="gloss">
    <dt>Cliente / hospital</dt><dd>Participante do FL. Aqui são 10 hospitais simulados no mesmo PC, cada um com uma fatia das 4.706 radiografias de treino. Treinam um de cada vez na GPU; o resultado é o mesmo de treinarem em paralelo.</dd>
    <dt>Rodada</dt><dd>Ciclo em que o servidor envia o modelo, cada hospital treina uma época nos seus dados e devolve a atualização, e o servidor faz a média.</dd>
    <dt>Grade</dt><dd>Conjunto de execuções de um experimento (por exemplo h2: 4 métodos × 5 níveis × 3 seeds).</dd>
    <dt>IID</dt><dd>Todos os hospitais têm a mesma mistura de diagnósticos. É a referência sem heterogeneidade.</dd>
    <dt>α (Dirichlet)</dt><dd>Controla a heterogeneidade de rótulos: 1,0 leve, 0,5 moderada, 0,3 e 0,2 forte, 0,15 muito forte e 0,1 extrema (cada hospital quase com uma só classe).</dd>
    <dt>Acurácia balanceada</dt><dd>Média das acurácias de cada classe. 0,33 é chute; 1 é perfeito. Não é inflada pela classe mais comum.</dd>
    <dt>R</dt><dd>Número de rodadas até a acurácia de validação atingir o alvo escolhido.</dd>
    <dt>C<sub>total</sub></dt><dd>Total de bytes trafegados até R, medido pelo tamanho real das mensagens. O SCAFFOLD manda o dobro por rodada; o LoRA manda só os adaptadores.</dd>
    <dt>FedAvg · FedProx · SCAFFOLD</dt><dd>FedAvg faz a média simples. FedProx penaliza o quanto o hospital se afasta do modelo global. SCAFFOLD corrige a direção do gradiente com <i>control variates</i>.</dd>
    <dt>LoRA</dt><dd>Treina e envia só adaptadores de baixo posto nas camadas de atenção, mais a cabeça de classificação; o resto da rede fica congelado.</dd>
    <dt>KL</dt><dd>Divergência entre a mistura de diagnósticos de um hospital e a do conjunto todo. Mede a heterogeneidade que de fato saiu da partição.</dd>
    <dt>Alinhamento (cosseno)</dt><dd>O quanto a atualização de um hospital aponta na mesma direção da média. Valores baixos indicam <i>client drift</i>.</dd>
    <dt>Seed</dt><dd>Semente aleatória. Cada configuração roda com 3 seeds para medir a variação.</dd>
    <dt>Limitada por energia / calor</dt><dd>A placa reduziu o clock por bater no teto de consumo (normal sob carga) ou por temperatura (thermal throttling).</dd>
    <dt>Proteção térmica</dt><dd>Pausa o treino de uma placa quando ela passa do limite de temperatura e retoma quando esfria. A execução aparece como "Pausada · calor".</dd>
  </dl></div></section>`;
