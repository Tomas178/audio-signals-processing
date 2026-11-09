.PHONY: setup run1 run2 run3 run4 test1 test2 signals2 report2 report3 report4

setup:
	uv sync

run1:
	uv run python ./src/1lab/main.py

run2:
	uv run python ./src/2lab/main.py

run3:
	uv run python ./src/3lab/main.py

run4:
	uv run python ./src/4lab/main.py

test1:
	cd src/1lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

test2:
	cd src/2lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

signals2:
	cd src/2lab && uv run python -m scripts.make_signals

report2:
	cd src/2lab && uv run python -m scripts.report

report3:
	cd src/3lab && uv run python -m scripts.report

report4:
	cd src/4lab && uv run python -m scripts.report
