.PHONY: install run evaluate

install:
	pip install -r requirements.txt

run:
	python -m pipeline

evaluate:
	python -m pipeline.evaluate.sample
	python -m pipeline.evaluate.score
