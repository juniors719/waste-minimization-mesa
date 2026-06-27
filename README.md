# waste-minimization-mesa

Base executável de uma simulação de minimização de desperdício no varejo usando Mesa, SQLite e agentes especializados para análise, fornecedor, precificação e consumo.

## Estrutura

- `src/waste_minimization_mesa/db.py`: camada SQLite com o produto do catálogo.
- `src/waste_minimization_mesa/agents.py`: agentes de análise, fornecedor, inventário, precificação e consumidor.
- `src/waste_minimization_mesa/model.py`: orquestra os ticks diários da simulação.
- `src/waste_minimization_mesa/cli.py`: interface de linha de comando.

## Como rodar

```bash
pip install -e .
python -m waste_minimization_mesa --days 10
```

Se você preferir instalar as dependências diretamente:

```bash
pip install -r requirements.txt
python -m waste_minimization_mesa --days 10
```

O agente de precificação usa uma heurística orientada a risco, custo e margem mínima. Isso deixa os experimentos mais reprodutíveis e evita depender de um LLM local.

Para comparar os cenários sem desconto e com desconto:

```bash
python -m waste_minimization_mesa --compare --days 10
```

Por padrão, a simulação faz reposição orientada por demanda. Você pode ajustar isso com `--restock-strategy`, `--restock-interval` e `--restock-threshold`.
