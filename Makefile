.PHONY: default venv-dev build install tag
.PHONY: test lint dist dist-upload dist-upload-gitlab-ci clean

ifeq ($(OS),Windows_NT)     # is Windows_NT on XP, 2000, 7, Vista, 10...
    RM := echo y | del
    RM_DIR := rmdir /S /Q
    VENV_PY_VER := 3
    ACTIVATE := .\venv\Scripts\activate.bat
    DEACTIVATE := deactivate.bat
    PYTHON := python
    PIP := pip
else
	RM := rm -f ./
	RM_DIR := rm -rf ./
    detected_OS := $(shell uname)  # same as "uname -s"
    VENV_PY_VER := python3
    ACTIVATE := . ./venv/bin/activate
    DEACTIVATE := deactivate
    PYTHON := python
    PIP := pip
endif

default: test lint dist

venv: #
	virtualenv -p $(VENV_PY_VER) venv
	$(ACTIVATE) && $(PIP) install -r requirements.txt && $(DEACTIVATE)

venv-dev:
	virtualenv -p $(VENV_PY_VER) venv
	$(ACTIVATE) && $(PIP) install -r requirements-dev.txt && $(DEACTIVATE)

test: venv-dev
	$(ACTIVATE) && python -m pytest --cov gradeprimecommonlib --no-cov-on-fail --cov-fail-under=94 --cov-report=xml:coverage.xml --cov-report=html --cov-branch

lint: venv-dev
	echo "Linting gradeprimecommonlib and tests directories..."
	$(ACTIVATE) && flake8 .
	echo "Complete"

start: 
	$(ACTIVATE) && \
	DB_HOST=localhost \
	$(PYTHON) app.py

support:
	docker-compose up db

run:
	docker-compose up --build

clean:
	- docker-compose down
