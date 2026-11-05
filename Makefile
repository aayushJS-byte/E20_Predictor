PY ?= .venv/bin/python

.PHONY: all data layer-a layer-b validate meta test lint site preview legacy clean

all: data layer-a layer-b validate meta test site

data:
	$(PY) -m layer_a.load

layer-a:
	$(PY) -m layer_a.export

layer-b:
	$(PY) -m layer_b.run

validate:
	$(PY) -m validation.tolerance
	$(PY) -m validation.layer_a_full
	$(PY) -m validation.ftir
	$(PY) -m validation.layer_b_full

meta:
	$(PY) -m common.site_meta

test: lint
	$(PY) -m pytest -q
	cd site && npx vitest run

lint:
	$(PY) -m ruff check .

site:
	cd site && npm ci && npm run build

preview: site
	cd site && npx vite preview --port 4173

legacy:
	cd legacy && streamlit run app.py

clean:
	rm -rf data/processed artefacts site/dist
