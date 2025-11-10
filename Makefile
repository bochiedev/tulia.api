.PHONY: help install migrate test run celery-worker celery-beat shell clean docker-up docker-down

help:
	@echo "Tulia AI - Available Commands"
	@echo "=============================="
	@echo "install          Install dependencies"
	@echo "migrate          Run database migrations"
	@echo "makemigrations   Create new migrations"
	@echo "test             Run tests"
	@echo "test-cov         Run tests with coverage"
	@echo "run              Run development server"
	@echo "celery-worker    Run Celery worker"
	@echo "celery-beat      Run Celery beat scheduler"
	@echo "shell            Open Django shell"
	@echo "clean            Remove Python cache files"
	@echo "docker-up        Start Docker services"
	@echo "docker-down      Stop Docker services"
	@echo "docker-logs      View Docker logs"
	@echo "lint             Run code linting"
	@echo "format           Format code with black"

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

test:
	pytest

test-cov:
	pytest --cov=apps --cov-report=html --cov-report=term

run:
	python manage.py runserver

celery-worker:
	celery -A config worker -l info -Q default,integrations,analytics,messaging,bot

celery-beat:
	celery -A config beat -l info

shell:
	python manage.py shell

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache htmlcov .coverage

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-migrate:
	docker-compose exec web python manage.py migrate

docker-shell:
	docker-compose exec web python manage.py shell

lint:
	flake8 apps config

format:
	black apps config
