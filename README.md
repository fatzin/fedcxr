# FedCXR

Heterogeneidade de dados e custo total de comunicação no Aprendizado Federado (FL) em radiografias de tórax.

Este repositório tem o código, os logs das 199 execuções e os scripts que geram as tabelas e figuras do
artigo experimental que continua a revisão "Heterogeneidade de Dados no Federated Learning Aplicado a
Imagens Médicas". O experimento simula dez hospitais que treinam juntos um ViT-S pré-treinado por 100 rodadas,
na base de pneumonia pediátrica de Kermany et al. (normal, bacteriana e viral).

## Resultados em uma tela

O alvo é acurácia balanceada de 0,75 na validação, e os valores são médias entre seeds. Todos os números
saem de `scripts/paper_figures.py`, lido a partir de `runs_final/`.

| | Resultado |
|---|---|
| H1, heterogeneidade de rótulos | O custo fica estável até α = 0,15 (FedAvg: 4 a 7 rodadas) e salta em α = 0,1: 30,6 rodadas e 53,1 GB, contra 8,7 GB no IID. |
| H2, FedProx | Com μ entre 0,001 e 0,1, as rodadas e os bytes ficam no nível do FedAvg. |
| H2, LoRA | Não reduz as rodadas, mas envia 96 vezes menos bytes por rodada (0,58 GB até o alvo em α = 0,1). Em α = 0,1 o alvo 0,75 está no teto do LoRA; com alvo 0,72 sustentado por 3 rodadas, ainda envia cerca de 80 vezes menos que o FedAvg. |
| H2, SCAFFOLD | Na implementação principal (modelo ponderado pelo tamanho do cliente, variáveis de controle com média uniforme), nenhuma das 5 seeds atinge o alvo em α = 0,1, e duas colapsam numa única classe. Quando as variáveis de controle também são ponderadas pelo tamanho, o colapso some: em 10 seeds atinge sempre o alvo e chega antes do FedAvg em 8 delas (15,1 rodadas a menos em média; o IC95%, de -0,8 a 31,1, ainda inclui zero). Em bytes continua mais caro, porque cada mensagem tem o dobro do tamanho. |
| H3, heterogeneidade de aquisição | As rodadas tendem a aumentar, mas com três seeds a diferença não é significativa. A harmonização por histograma não muda nada que dê para medir. |

## O que é medido

- **R**: rodadas até o alvo. É calculado depois, a partir do log de todas as rodadas, então serve para qualquer alvo.
  No critério sustentado, o alvo precisa se manter por 3 rodadas seguidas.
- **C_total**: bytes realmente serializados (`torch.save` dos tensores que trafegam), somados até R.
  No SCAFFOLD, inclui as variáveis de controle.
- **Heterogeneidade realizada**: KL médio entre a distribuição de rótulos de cada cliente e a do treino,
  e o coeficiente de variação dos tamanhos dos clientes (CV_N).
- **Teste**: acurácia balanceada, F1 por classe e macro, AUC macro.

O FL é simulado num único processo. Cada cliente é uma fatia dos dados, e os clientes treinam um depois do outro
no mesmo modelo. Nada passa pela rede: a comunicação é medida pelo tamanho exato das mensagens.

## Instalação

Python 3.12. As versões em `requirements.txt` são as usadas no artigo.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Em GPU NVIDIA, instale antes o torch da sua versão de CUDA:

```bash
.venv/bin/pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
```

Sem GPU NVIDIA, o código roda na CPU. Isso basta para os testes e para a conferência abaixo, que usa dados
sintéticos e um ViT bem pequeno e termina em menos de um minuto num notebook:

```bash
.venv/bin/python scripts/run_grid.py --grid smoke --runs runs_smoke \
    --extra data.synthetic=true model.name=vit_tiny_patch16_224 model.pretrained=false
```

As execuções do artigo usam o Kermany real e uma GPU NVIDIA.

## Testes

```bash
.venv/bin/python -m pytest -q   # cerca de 40 s na CPU, não precisa do Kermany
node --test 'dashboard/tests/*.test.js'   # lógica do dashboard (rotas, replay, comandos, formatação, contas)
```

| Arquivo | O que confere |
|---|---|
| `test_paper.py` | As tabelas geradas a partir de `runs_final/` são idênticas às de `tests/golden/tabelas`. |
| `test_training.py` | Todos os métodos e variantes treinam; quatro treinos sintéticos reproduzem os números de `tests/golden/sintetico.json`. |
| `test_fl.py` | Os pesos de agregação de cada variante do SCAFFOLD. |
| `test_config.py` | Overrides, nomes das execuções e que `paper` gera exatamente os 199 diretórios de `runs_final/`. |
| `test_data.py`, `test_models.py` | Partições, perfis de aquisição, tamanho das mensagens e LoRA. |
| `test_dashboard.py` | A API do dashboard e a leitura do estado da proteção térmica. |
| `dashboard/tests/*.test.js` | Rotas por hash, replay, comandos de Local/Colab/Modal, formatação e contas das hipóteses (só Node, sem pacotes). |

Quando uma mudança nos números for intencional, regrave as referências e confira o diff no git:

```bash
.venv/bin/python scripts/paper_figures.py --runs runs_final --out /tmp/fedcxr && cp /tmp/fedcxr/tabelas/* tests/golden/tabelas/
PYTHONPATH=. .venv/bin/python tests/test_training.py
```

O estilo do código segue a configuração do ruff em `pyproject.toml` (`pip install ruff`, depois `ruff check .`).

## Dados

Kermany, Zhang e Goldbaum (2018), Mendeley Data, doi:10.17632/rscbjbr9sj.2, licença CC BY 4.0.
O script baixa o ZIP (1,2 GB), confere o SHA-256 e gera um tensor único 224x224:

```bash
.venv/bin/python scripts/prepare_data.py --download
```

O conjunto de teste oficial fica como está. A validação (10%) é tirada do treino, separada por paciente para
que o mesmo paciente não apareça nos dois.

## Três formas de rodar

As grades estão em `fedcxr/grids.py` e são as mesmas nos três modos.
`python scripts/run_grid.py --list` mostra todas, e `paper` reúne as 9 grades do artigo (199 execuções).
Execuções que já têm `summary.json` são puladas, então dá para interromper e retomar em qualquer modo.

### 1. Máquina com GPU própria

```bash
# uma execução
.venv/bin/python -m fedcxr.train --set partition.scheme=dirichlet partition.alpha=0.1 fl.method=scaffold fl.scaffold_variant=cweighted fl.lr=0.003 seed=1

# uma grade: duas GPUs, quatro execuções simultâneas em cada (o ViT-S cabe várias)
.venv/bin/python scripts/run_grid.py --grid h2 --gpus 0,1 --per-gpu 4

# o artigo inteiro
.venv/bin/python scripts/run_grid.py --grid paper --gpus 0,1 --per-gpu 4
```

Se a GPU passar de um limite de temperatura, `scripts/thermal_guard.py` pausa as execuções e retoma quando
ela esfria:

```bash
nohup .venv/bin/python scripts/thermal_guard.py --hot 88 --cool 75 >> thermal_guard.log 2>&1 &
```

O dashboard lê o estado dela em `thermal_guard.pid`, gravado quando ela inicia, e em `thermal_guard.log`.

### 2. Google Colab

Abra [`notebooks/colab.ipynb`](https://colab.research.google.com/github/fatzin/fedcxr/blob/main/notebooks/colab.ipynb) no Colab com uma GPU. O notebook clona o repositório, baixa os dados,
roda uma execução ou uma grade pequena e gera a análise. Como a T4 não tem bf16, ele usa `train.amp=fp16`.

### 3. Modal

```bash
pip install -r requirements-modal.txt
modal setup                                   # login, feito por você
modal run modal_run.py::prepare               # baixa e prepara os dados no Volume
modal run modal_run.py::grid --name sens --k 3
```

Para grades longas, implante o app e dispare as grades sem depender da máquina local ligada:

```bash
modal deploy modal_run.py
python modal_run.py paper 8   # 8 execuções simultâneas por GPU
```

Os resultados ficam no Volume `fedcxr-vol` e são baixados com `modal volume get`.

## Reproduzir as tabelas e figuras do artigo

`runs_final/` traz os logs das 199 execuções do artigo (configurações, métricas por rodada e resumos,
sem checkpoints). A partir deles:

```bash
.venv/bin/python scripts/paper_figures.py --runs runs_final --out saida_artigo
.venv/bin/python scripts/analyze.py --runs runs_final --grid h2 --targets 0.75
```

`paper_figures.py` grava `tabelas/*.tex`, incluindo as macros com cada número citado no texto, e `figuras/*.pdf`.
As tabelas publicadas ficam no repositório do artigo e são as mesmas de `tests/golden/tabelas`, que
`tests/test_paper.py` compara com a saída a cada execução dos testes.
`analyze.py` só imprime a tabela. Com `--out <pasta>`, grava também a tabela, um JSON e as curvas.

Para refazer tudo do zero, rode a grade `paper` num dos três modos e aponte `--runs` para a saída.
A soma das durações das 199 execuções é de 66 horas (de 8 a 28 minutos cada). Como várias rodam ao
mesmo tempo na mesma GPU, o tempo de relógio fica bem menor. A grade `h2` sozinha soma 24 horas.

As seeds fixam a partição, os perfis de aquisição, a inicialização e a ordem dos lotes. Com o mesmo hardware e
software, a mesma seed dá curvas idênticas: as execuções repetidas entre duas grades do artigo saíram iguais
bit a bit, mesmo rodando em máquinas diferentes com o mesmo modelo de GPU. Em outra GPU ou outra versão do
PyTorch, os números podem mudar nas últimas casas decimais. Na CPU, `test_training.py` confere isso a cada execução.

## Dashboard

Painel em Preact, sem etapa de build: o próprio `server.py` serve a página e as bibliotecas, guardadas em
`dashboard/vendor/`, então ele funciona sem internet. Mostra as execuções ao vivo (rodada, acurácia,
temperatura e clock de cada GPU) e compara configurações pelo R e pelo C_total, com o alvo ajustável na tela.

```bash
.venv/bin/python dashboard/server.py --host 127.0.0.1 --runs runs_final   # resultados do artigo
bash scripts/serve_dashboard.sh --host 127.0.0.1                          # em segundo plano, lendo runs/
```

Abra `http://127.0.0.1:8050`. Sem `--host`, o servidor usa o IP da máquina no Tailscale, se houver, para ser
acessado de outro computador da mesma rede Tailscale; sem Tailscale, fica em `127.0.0.1`.

- Cada execução tem um endereço próprio, `#/run/<grade>/<execução>`. Com `/replay` no fim, o painel
  reproduz o treino rodada a rodada a partir dos logs gravados, sem treinar nada.
- Em Infraestrutura, o cartão Configurar treino monta o comando para rodar uma grade na máquina local,
  no Colab ou no Modal. Ele só mostra o comando; não dispara nada.

## Estrutura

```
configs/base.yaml        configuração base; qualquer campo pode ser sobrescrito com --set a.b=valor
fedcxr/                  dados, partições, perfis de aquisição, modelos, FedAvg/FedProx/SCAFFOLD, métricas
fedcxr/grids.py          definição das grades do artigo
fedcxr/runlog.py         formato dos arquivos de cada execução (gravação e leitura)
scripts/run_grid.py      execução local das grades
scripts/paper_figures.py tabelas, figuras e números do artigo
scripts/analyze.py       resumo rápido de uma grade
scripts/prepare_data.py  download e preparação do Kermany
scripts/thermal_guard.py proteção térmica das GPUs (pausa e retoma os treinos)
scripts/serve_dashboard.sh  sobe o dashboard em segundo plano
modal_run.py             execução no Modal
notebooks/colab.ipynb    execução no Colab
dashboard/               painel de acompanhamento
runs_final/              logs das execuções do artigo
tests/                   testes (treino sintético, grades contra runs_final/, tabelas do artigo)
```

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados de Kermany et al. seguem a licença CC BY 4.0 do Mendeley Data
e não são redistribuídos aqui.
