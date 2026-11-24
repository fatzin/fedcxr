"""Padrões dos comandos de execução (máquina própria, Colab e Modal), num só lugar: modal_run.py usa os do Modal
e o dashboard mostra todos.

Só biblioteca padrão, para o cliente local do Modal (que só instala requirements-modal.txt) importar.
"""
LOCAL_DEFAULT_K = 4  # execuções simultâneas por GPU na máquina própria
COLAB_DEFAULT_K = 2  # execuções simultâneas na T4 do Colab
COLAB_MAX_RUNS = 40  # grades maiores que isso não cabem numa sessão do Colab
COLAB_NOTEBOOK_URL = "https://colab.research.google.com/github/fatzin/fedcxr/blob/main/notebooks/colab.ipynb"
MODAL_VOLUME = "fedcxr-vol"
MODAL_DEFAULT_K = 6  # execuções simultâneas por GPU no Modal
