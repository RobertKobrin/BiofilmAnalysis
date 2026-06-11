PYTHON ?= python3
VENV_PYTHON = .venv/bin/python

.PHONY: setup run desktop-icon demo-data test

setup:
	scripts/setup_environment.sh

run:
	scripts/run_app.sh

desktop-icon:
	scripts/install_desktop_launcher.sh

demo-data:
	@if [ -x "$(VENV_PYTHON)" ]; then \
		$(VENV_PYTHON) scripts/generate_demo_stack.py; \
	else \
		$(PYTHON) scripts/generate_demo_stack.py; \
	fi

test:
	@if [ -x "$(VENV_PYTHON)" ]; then \
		$(VENV_PYTHON) -m pytest; \
	else \
		$(PYTHON) -m pytest; \
	fi
