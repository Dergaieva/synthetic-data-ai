.PHONY: install check test format run

install:
	python -m pip install -e ".[dev]"

check:
	ruff check .
	ruff format --check .
	mypy src
	pytest

test:
	pytest

format:
	ruff check --fix .
	ruff format .

run:
	streamlit run app.py

