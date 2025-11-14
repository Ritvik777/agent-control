SHELL := /bin/bash

ALEMBIC := uv run --with alembic alembic -c alembic.ini

MSG ?= update
UP ?= head
DOWN ?= -1
SHOW ?= head
STAMP ?= head

.PHONY: help alembic-migrate alembic-revision alembic-upgrade alembic-downgrade alembic-current alembic-history alembic-heads alembic-show alembic-stamp

help:
	@echo "Available targets:"
	@echo "  alembic-migrate MSG='message'  - autogenerate alembic revision"
	@echo "  alembic-revision MSG='message' - create empty alembic revision"
	@echo "  alembic-upgrade UP=head        - upgrade to revision"
	@echo "  alembic-downgrade DOWN=-1      - downgrade to revision"
	@echo "  alembic-current                - show current revision"
	@echo "  alembic-history                - show migration history"
	@echo "  alembic-heads                  - show heads"
	@echo "  alembic-show SHOW=<rev>        - show revision detail"
	@echo "  alembic-stamp STAMP=<rev>      - set head without running migrations"

alembic-migrate:
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

alembic-revision:
	$(ALEMBIC) revision -m "$(MSG)"

alembic-upgrade:
	$(ALEMBIC) upgrade $(UP)

alembic-downgrade:
	$(ALEMBIC) downgrade $(DOWN)

alembic-current:
	$(ALEMBIC) current

alembic-history:
	$(ALEMBIC) history

alembic-heads:
	$(ALEMBIC) heads

alembic-show:
	$(ALEMBIC) show $(SHOW)

alembic-stamp:
	$(ALEMBIC) stamp $(STAMP)
