.PHONY: setup run1 run2 run3

setup:
	uv sync

run1:
	python3 ./src/1lab/main.py

run2:
	python3 ./src/2lab/main.py

run3:
	python3 ./src/3lab/main.py