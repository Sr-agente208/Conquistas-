.PHONY: help install browsers login run dry status site panel test lint format doctor clean

help:
	@echo "install  - cria .venv, instala o pacote e o Chromium"
	@echo "login    - login manual (salva a sessão)"
	@echo "dry      - simulação das tarefas do dia"
	@echo "run      - executa as tarefas do dia"
	@echo "status   - saldo e resumo de hoje"
	@echo "test     - pytest"
	@echo "lint     - ruff check"
	@echo "site     - serve o site local em http://localhost:8000"
	@echo "panel    - abre o painel web (estilo Zunder)"
	@echo "format   - ruff format"

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/playwright install chromium

browsers:
	.venv/bin/playwright install chromium

login:
	.venv/bin/conquistas login

dry:
	.venv/bin/conquistas run --dry-run

run:
	.venv/bin/conquistas run

status:
	.venv/bin/conquistas status

site:
	python3 -m http.server 8000 --directory docs

panel:
	.venv/bin/conquistas serve

doctor:
	.venv/bin/conquistas doctor

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
