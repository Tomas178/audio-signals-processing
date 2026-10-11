.PHONY: setup run1 run2 run3 test1 test2 signals2 report2

setup:
	uv sync

run1:
	uv run python ./src/1lab/main.py

run2:
	uv run python ./src/2lab/main.py

run3:
	uv run python ./src/3lab/main.py

test1:
	cd src/1lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

test2:
	cd src/2lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

signals2:
	cd src/2lab && uv run python -m scripts.make_signals

report2:
	cd src/2lab && uv run python -m scripts.report