PYTHON ?= python

.PHONY: install run test clean

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

test:
	pytest -v

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage
	rm -f taskflow.db *.db-journal


migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "schema change"
