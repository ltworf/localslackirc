all:
	@echo Nothing to do

.PHONY: lint
lint:
	mypy --config-file mypy.conf irc.py
