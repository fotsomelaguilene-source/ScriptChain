# ScriptChain starter -- Lab 2 applied to the project.
# Usage:  make install | test | test-script | test-mark | run-script | run-mark | demo | lint | clean
#         make test-script M=m1      (one milestone: m1 m2 m3 m4 m5 contract)
PY ?= python
PYTEST = $(PY) -m pytest -q --tb=short
ifdef M
MARKER = -m $(M)
endif

.PHONY: install test test-script test-mark run-script run-mark demo token lint clean

install:
	$(PY) -m pip install -r requirements.txt

test: test-script test-mark

test-script:
	cd services/script && $(PYTEST) $(MARKER)

test-mark:
	cd services/mark && $(PYTEST) $(MARKER)

run-script:
	cd services/script && $(PY) -m app

run-mark:
	cd services/mark && $(PY) -m app

demo:
	$(PY) tools/e2e_demo.py

token:
	$(PY) tools/make_token.py --list

lint:
	$(PY) -m compileall -q services tools
	@$(PY) -c "import pyflakes" 2>/dev/null && $(PY) -m pyflakes services tools || echo "pyflakes not installed (optional)"

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
	rm -rf .pytest_cache services/*/.pytest_cache
