# AI Mail Assistant: one entry point for setup and everyday commands.
# Run `make` or `make help` for the list. Every mailbox-changing target says so.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# First Python 3.10+ found (macOS ships 3.9). Override with `make PYTHON=/path/to/python3`.
ifeq ($(origin PYTHON),undefined)
PYTHON := $(shell for p in python3 python3.13 python3.12 python3.11 python3.10 \
	"$$(brew --prefix 2>/dev/null)/bin/python3"; do \
	command -v "$$p" >/dev/null 2>&1 && "$$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null \
	&& { command -v "$$p"; break; }; done)
endif

SETUP := scripts/setup-macos.sh

.PHONY: help setup setup-preview doctor test lint \
	preview classify apply review retry-review usage summary \
	discover rules-preview \
	schedule-render schedule-install schedule-status schedule-uninstall \
	share demo check-python

##@ Install and configure

setup: ## Install CLIs, create private config, log in, verify (safe to re-run)
	@bash $(SETUP)

setup-preview: ## Print every command `make setup` would run; change nothing
	@bash $(SETUP) --dry-run

doctor: ## Health check: what is installed, authorized and scheduled
	@bash $(SETUP) --check

##@ Daily use (dry run unless the target says otherwise)

preview: check-python ## Rules + cache only: reads mail metadata, no model, no changes
	@$(PYTHON) runner.py --no-model; status=$$?; [[ $$status -eq 0 || $$status -eq 2 ]]

classify: check-python ## Paid classification of untagged mail, still a dry run
	@$(PYTHON) runner.py; status=$$?; [[ $$status -eq 0 || $$status -eq 2 ]]

apply: check-python ## CHANGES MAIL: labels, tasks and configured actions
	@read -r -p "Apply labels, tasks and actions to your mailbox? [y/N] " reply; [[ "$$reply" =~ ^[Yy] ]]
	@$(PYTHON) runner.py --apply; status=$$?; [[ $$status -eq 0 || $$status -eq 2 ]]

review: check-python ## Preview the combined plan from the last dry run
	@$(PYTHON) triage.py apply-plan

retry-review: check-python ## Paid retry of mail held for review, dry run
	@$(PYTHON) runner.py --retry-review; status=$$?; [[ $$status -eq 0 || $$status -eq 2 ]]

summary: ## Show the last run's summary
	@cat state/summary.json 2>/dev/null || echo "No summary yet: run 'make preview' first."

usage: check-python ## Model calls, tokens and characters recorded so far
	@$(PYTHON) runner.py --usage-report

##@ Personalized rules

discover: check-python ## Read-only sender discovery (last 30 days, at most 200 messages)
	@$(PYTHON) mail_setup.py discover

rules-preview: check-python ## Preview rules selected by the mail-setup skill
	@$(PYTHON) mail_setup.py preview

##@ Hourly weekday schedule (macOS launchd)

schedule-render: check-python ## Show the job definition; installs nothing
	@$(PYTHON) schedule.py render

schedule-install: check-python ## Install the schedule (future runs use --apply)
	@$(PYTHON) schedule.py install

schedule-status: check-python ## Registered job and last exit code
	@$(PYTHON) schedule.py status

schedule-uninstall: check-python ## Remove the schedule; mail is untouched
	@$(PYTHON) schedule.py uninstall

##@ Development

demo: check-python ## Run the real engine on an invented mailbox: no account, no model, no changes
	@$(PYTHON) demo/run_demo.py

test: check-python ## Offline test suite (no mailbox, no model calls)
	@$(PYTHON) -m unittest discover -q -s tests -t .

lint: check-python ## ShellCheck and byte-compile
	@shellcheck scripts/*.sh
	@$(PYTHON) -m compileall -q -x '/\.venv' .

share: check-python ## Build dist/ai-mail-assistant.zip without private data
	@$(PYTHON) tools/share.py

check-python:
	@[[ -n "$(PYTHON)" ]] || { echo "Python 3.10+ not found: run 'make setup' or pass PYTHON=/path/to/python3" >&2; exit 1; }

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mAI Mail Assistant\033[0m  ·  make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo
