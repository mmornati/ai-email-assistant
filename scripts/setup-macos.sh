#!/usr/bin/env bash
# Configure AI Mail Assistant from zero on macOS.
#
# Installs the CLIs with Homebrew, creates private local files, walks through
# Google Cloud / Google Workspace / classifier CLI (Copilot or Claude Code)
# authentication, and verifies the
# install with the offline tests and a model-free, read-only dry run.
#
# It never modifies mail, never enables --apply, and never installs a schedule.
# Every step is idempotent: re-run it at any time to repair or verify a setup.
# `--check` only inspects the installation (a "doctor") and changes nothing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIN_PY_MINOR=10
BREW_PYTHON="python@3.13"
# Least privilege: label/archive mail and manage Tasks. No send, no Drive.
GMAIL_SCOPE="https://www.googleapis.com/auth/gmail.modify"
TASKS_SCOPE="https://www.googleapis.com/auth/tasks"

ASSUME_YES=0
DRY_RUN=0
SKIP_AUTH=0
SKIP_MODEL_CLI=0
CLI=""            # copilot or claude; empty means "whatever classifier.json selects"
SKIP_VERIFY=0
CHECK_ONLY=0
GCP_PROJECT=""
TASK_LIST=""

usage() {
  cat <<EOF
Usage: scripts/setup-macos.sh [options]

Options:
  -y, --yes            Answer yes to every prompt (still opens browser logins)
  -n, --dry-run        Print the commands that would run; change nothing
  -c, --check          Health check only: report what is installed and
                       authorized, change nothing (exit 1 if incomplete)
      --project ID     Use an existing Google Cloud project for gws auth setup
      --task-list NAME Google Tasks list for a new rules.json (default: My Tasks)
      --skip-auth      Install tools and local files only; no logins
      --cli NAME       Classifier CLI to install and select in classifier.json:
                       copilot (GitHub Copilot CLI) or claude (Claude Code).
                       Default: the cli already set in classifier.json
      --no-model-cli   Do not install or log in to any classifier CLI
                       (model-free use only: runner.py --no-model)
      --skip-copilot   Same as --no-model-cli (older name)
      --skip-verify    Do not run the tests or the read-only dry run
  -h, --help           Show this help

Nothing here modifies mail, enables --apply, or installs the schedule.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    -c|--check) CHECK_ONLY=1 ;;
    --project) GCP_PROJECT="${2:?--project requires a value}"; shift ;;
    --task-list) TASK_LIST="${2:?--task-list requires a value}"; shift ;;
    --skip-auth) SKIP_AUTH=1 ;;
    --cli)
      CLI="${2:?--cli requires a value}"; shift
      [[ "$CLI" == copilot || "$CLI" == claude ]] || { echo "--cli must be copilot or claude" >&2; exit 64; } ;;
    --no-model-cli|--skip-copilot) SKIP_MODEL_CLI=1 ;;
    --skip-verify) SKIP_VERIFY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 64 ;;
  esac
  shift
done

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi

step() { printf '\n%s==> %s%s\n' "$BOLD" "$*" "$RESET"; }
ok()   { printf '%s  ✓ %s%s\n' "$GREEN" "$*" "$RESET"; }
warn() { printf '%s  ! %s%s\n' "$YELLOW" "$*" "$RESET"; }
die()  { printf '%serror: %s%s\n' "$RED" "$*" "$RESET" >&2; exit 1; }

# Run a command, or only print it in --dry-run mode.
run() {
  printf '%s  $ %s%s\n' "$DIM" "$*" "$RESET"
  if [[ $DRY_RUN -eq 0 ]]; then "$@"; fi
}

confirm() {
  [[ $ASSUME_YES -eq 1 || $DRY_RUN -eq 1 ]] && return 0
  local reply
  read -r -p "  $1 [Y/n] " reply || return 1
  [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

python_ok() {
  "$1" -c "import sys; sys.exit(0 if sys.version_info >= (3, $MIN_PY_MINOR) else 1)" 2>/dev/null
}

# Prints the first Python 3.$MIN_PY_MINOR+ interpreter on PATH or in Homebrew, or nothing.
find_python() {
  local candidate
  for candidate in python3 python3.13 python3.12 python3.11 python3.10 \
                   "$(brew --prefix 2>/dev/null)/bin/python3"; do
    if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
      command -v "$candidate"
      return
    fi
  done
}

# Prints one word per missing piece: setup, apis, login. Reads gws status JSON on stdin.
gws_missing() {
  "$PYTHON" -c '
import json, sys
try:
    s = json.load(sys.stdin)
except ValueError:
    print("setup login"); sys.exit()
missing = []
if not s.get("client_config_exists"):
    missing.append("setup")
apis = set(s.get("enabled_apis") or [])
if not {"gmail.googleapis.com", "tasks.googleapis.com"} <= apis:
    missing.append("apis")
scopes = set(s.get("scopes") or [])
gmail = {"https://www.googleapis.com/auth/gmail.modify", "https://mail.google.com/"}
if not (s.get("has_refresh_token") and scopes & gmail and "https://www.googleapis.com/auth/tasks" in scopes):
    missing.append("login")
print(" ".join(missing))
'
}

gws_status() { gws auth status 2>/dev/null || true; }

# --- Health check (--check): read-only, prints a checklist ---------------------
DOCTOR_FAILED=0
check() {  # check <required 0|1> <passed 0|1> <label> <how to fix>
  if [[ "$2" == 1 ]]; then
    printf '%s  ✓ %s%s\n' "$GREEN" "$3" "$RESET"
  elif [[ "$1" == 1 ]]; then
    printf '%s  ✗ %s%s  %s→ %s%s\n' "$RED" "$3" "$RESET" "$DIM" "$4" "$RESET"
    DOCTOR_FAILED=1
  else
    printf '%s  ○ %s%s  %s→ %s%s\n' "$YELLOW" "$3" "$RESET" "$DIM" "$4" "$RESET"
  fi
}
yes_no() { if "$@"; then echo 1; else echo 0; fi; }
has() { command -v "$1" >/dev/null 2>&1; }
private_dir() {  # GNU stat first, then BSD/macOS stat
  [[ -d "$1" && "$(stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null)" == 700 ]]
}

doctor() {
  local missing="" selected=""
  step "AI Mail Assistant health check"
  check 1 "$(yes_no test "$(uname -s)" = Darwin)" "macOS" "the setup script and schedule are macOS-only"
  check 1 "$(yes_no has brew)" "Homebrew" "install it from https://brew.sh"
  PYTHON="$(find_python)"
  check 1 "$(yes_no test -n "$PYTHON")" "Python 3.$MIN_PY_MINOR+ ${PYTHON:+($PYTHON)}" "make setup"
  check 1 "$(yes_no has gws)" "Google Workspace CLI (gws)" "brew install googleworkspace-cli"
  check 0 "$(yes_no has gcloud)" "Google Cloud CLI (first-time OAuth setup only)" "brew install --cask gcloud-cli"
  # The classifier CLI that classifier.json selects (the older flat format means copilot).
  if [[ -n "$PYTHON" ]]; then
    selected="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1])).get("cli", "copilot"))' \
      "$ROOT/classifier.json" 2>/dev/null || true)"
  fi
  if [[ "$selected" == claude ]]; then
    check 0 "$(yes_no has claude)" "Claude Code (selected classifier CLI)" "make setup, or brew install --cask claude-code"
  else
    check 0 "$(yes_no has copilot)" "GitHub Copilot CLI (selected classifier CLI)" "make setup, or brew install --cask copilot-cli"
  fi
  check 1 "$(yes_no test -f "$ROOT/rules.json")" "rules.json" "make setup (copies rules.example.json)"
  check 1 "$(yes_no private_dir "$ROOT/state")" "state/ is private (0700)" "make setup"
  if [[ -n "$PYTHON" ]] && has gws; then
    missing="$(gws_status | gws_missing)"
    check 1 "$(yes_no test -z "$missing")" "gws authorized for Gmail + Tasks${missing:+ (missing: $missing)}" "make setup"
  fi
  check 0 "$(yes_no test -f "$HOME/Library/LaunchAgents/local.ai-mail-assistant.plist")" \
    "Hourly schedule installed (optional)" "make schedule-install, after reviewing a dry run"
  echo
  if [[ $DOCTOR_FAILED -eq 0 ]]; then
    ok "ready: 'make preview' runs a read-only, model-free dry run"
  else
    warn "incomplete: run 'make setup' (idempotent, safe to re-run)"
  fi
  return "$DOCTOR_FAILED"
}

if [[ $CHECK_ONLY -eq 1 ]]; then
  doctor || exit 1
  exit 0
fi

# --- 1. Platform and Homebrew ------------------------------------------------
step "Checking platform"
[[ "$(uname -s)" == "Darwin" ]] || die "this script is for macOS; see README for other platforms"
ok "macOS $(sw_vers -productVersion 2>/dev/null || echo '')"

if ! command -v brew >/dev/null 2>&1; then
  die "Homebrew is required. Install it from https://brew.sh (review the script first), then re-run."
fi
ok "Homebrew $(brew --version | head -n1 | awk '{print $2}')"

# --- 2. Python -----------------------------------------------------------------
step "Python 3.$MIN_PY_MINOR+"
PYTHON="$(find_python)"
if [[ -z "$PYTHON" ]]; then
  warn "no Python 3.$MIN_PY_MINOR+ found (macOS ships 3.9); installing $BREW_PYTHON"
  run brew install "$BREW_PYTHON"
  PYTHON="$(brew --prefix "$BREW_PYTHON" 2>/dev/null || echo /opt/homebrew/opt/$BREW_PYTHON)/bin/python3"
fi
if [[ $DRY_RUN -eq 0 ]]; then
  python_ok "$PYTHON" || die "$PYTHON is not Python 3.$MIN_PY_MINOR+"
fi
ok "$PYTHON"

# Which classifier CLI classifier.json selects now (the older flat format means copilot).
CONFIG_CLI="$("$PYTHON" -c '
import json, sys
print(json.load(open(sys.argv[1])).get("cli", "copilot"))
' "$ROOT/classifier.json" 2>/dev/null || true)"
CLI_REQUESTED="$CLI"
CLI="${CLI:-${CONFIG_CLI:-copilot}}"
case "$CLI" in
  claude) CLI_NAME="Claude Code" ;;
  copilot) CLI_NAME="GitHub Copilot CLI" ;;
  *) die "classifier.json selects an unknown cli '$CLI'; use --cli copilot or --cli claude" ;;
esac

# --- 3. CLIs ---------------------------------------------------------------------
step "Command-line tools"
# Homebrew's "gws" formula is an unrelated git-workspace tool with the same binary name.
if brew list --formula gws >/dev/null 2>&1; then
  die "the Homebrew formula 'gws' (git workspaces) is installed and conflicts with the Google Workspace CLI. Run 'brew uninstall gws' if you do not need it, then re-run."
fi

brew_install() {  # brew_install <formula|--cask cask> <binary> <description>
  local kind=() name binary description
  if [[ "$1" == "--cask" ]]; then kind=(--cask); shift; fi
  name="$1"; binary="$2"; description="$3"
  if command -v "$binary" >/dev/null 2>&1; then
    ok "$description already installed ($(command -v "$binary"))"
  else
    # ${kind[@]+...}: macOS bash 3.2 treats an empty array as unbound under set -u
    run brew install ${kind[@]+"${kind[@]}"} "$name"
  fi
}

brew_install googleworkspace-cli gws "Google Workspace CLI (gws)"
brew_install --cask gcloud-cli gcloud "Google Cloud CLI (gcloud)"
if [[ $SKIP_MODEL_CLI -eq 1 ]]; then
  warn "skipping the classifier CLI: only model-free runs (runner.py --no-model) will work"
elif [[ "$CLI" == claude ]]; then
  brew_install --cask claude-code claude "$CLI_NAME"
else
  brew_install --cask copilot-cli copilot "$CLI_NAME"
fi

# --- 4. Private local files -------------------------------------------------------
step "Local configuration"
cd "$ROOT"
umask 077
if [[ -d state ]]; then
  run chmod 700 state
else
  run mkdir -m 700 state
fi
ok "state/ is private (owner-only)"
if [[ -f rules.json ]]; then
  ok "rules.json exists; leaving your rules untouched"
else
  if [[ -z "$TASK_LIST" && $ASSUME_YES -eq 0 && $DRY_RUN -eq 0 && -t 0 ]]; then
    read -r -p "  Google Tasks list for follow-up tasks [My Tasks]: " TASK_LIST || TASK_LIST=""
  fi
  run cp rules.example.json rules.json
  if [[ -n "$TASK_LIST" && "$TASK_LIST" != "My Tasks" ]]; then
    printf '%s  $ set tasks.list to "%s" in rules.json%s\n' "$DIM" "$TASK_LIST" "$RESET"
    # The name travels through the environment, never through the Python source.
    [[ $DRY_RUN -eq 1 ]] || TASK_LIST="$TASK_LIST" "$PYTHON" -c '
import json, os
text = open("rules.json").read()
default = "\"list\": \"My Tasks\""
assert text.count(default) == 1, "unexpected starter rules"
text = text.replace(default, "\"list\": " + json.dumps(os.environ["TASK_LIST"], ensure_ascii=False))
json.loads(text)
open("rules.json", "w").write(text)
'
  fi
  ok "created rules.json from the starter rules (no cleanup actions enabled)"
fi
if [[ -n "$CLI_REQUESTED" && "$CLI_REQUESTED" != "$CONFIG_CLI" ]]; then
  # Validates the providers block before rewriting; mail and state are untouched.
  run "$PYTHON" runner.py --select-cli "$CLI_REQUESTED"
fi
ok "classifier.json selects $CLI ($CLI_NAME)"

# --- 5. Authentication --------------------------------------------------------------
if [[ $SKIP_AUTH -eq 1 ]]; then
  step "Authentication (skipped)"
else
  step "Google Cloud CLI login (needed once to create the OAuth client)"
  if [[ $DRY_RUN -eq 0 ]] && [[ -n "$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)" ]]; then
    ok "gcloud has an active account"
  elif confirm "Open the browser to log in to Google Cloud?"; then
    run gcloud auth login
  fi

  step "Google Workspace CLI (Gmail + Tasks)"
  if [[ $DRY_RUN -eq 1 ]]; then missing="setup login"; else missing="$(gws_status | gws_missing)"; fi
  if [[ " $missing " == *" setup "* ]]; then
    echo "  gws needs a Google Cloud project with an OAuth client. 'gws auth setup' creates or"
    echo "  reuses one and enables the APIs. Follow your organization's OAuth policy."
    if confirm "Run gws auth setup now?"; then
      if [[ -n "$GCP_PROJECT" ]]; then run gws auth setup --project "$GCP_PROJECT"; else run gws auth setup; fi
    fi
    [[ $DRY_RUN -eq 1 ]] || missing="$(gws_status | gws_missing)"
  fi
  if [[ " $missing " == *" apis "* ]]; then
    project="$GCP_PROJECT"
    if [[ -z "$project" ]]; then
      project="$(gws_status | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("project_id") or "")' 2>/dev/null || true)"
    fi
    if [[ -n "$project" ]] && confirm "Enable the Gmail and Tasks APIs in project $project?"; then
      run gcloud services enable gmail.googleapis.com tasks.googleapis.com --project "$project"
    else
      warn "enable gmail.googleapis.com and tasks.googleapis.com in your gws project"
    fi
  fi
  if [[ " $missing " == *" login "* ]]; then
    echo "  Requesting only: gmail.modify (labels/archive, no sending) and tasks."
    if confirm "Open the browser to authorize gws?"; then
      run gws auth login --scopes "$GMAIL_SCOPE,$TASKS_SCOPE"
    fi
  fi
  if [[ $DRY_RUN -eq 0 ]]; then
    missing="$(gws_status | gws_missing)"
    if [[ -z "$missing" ]]; then ok "gws is authorized for Gmail and Tasks"; else warn "gws still missing: $missing"; fi
  fi

  if [[ $SKIP_MODEL_CLI -eq 1 ]]; then
    :
  elif [[ "$CLI" == claude ]]; then
    step "$CLI_NAME"
    echo "  Classification uses your Claude subscription login (providers.claude.auth in classifier.json)."
    echo "  Each call is capped by providers.claude.max_budget_usd_per_call."
    if confirm "Run claude auth login now? (skip if already logged in)"; then
      run claude auth login
    fi
  else
    step "$CLI_NAME"
    echo "  Classification uses your Copilot account and its organization model policy."
    if confirm "Run copilot login now? (skip if already logged in)"; then
      run copilot login
    fi
  fi
fi

# --- 6. Verification ------------------------------------------------------------------
if [[ $SKIP_VERIFY -eq 1 ]]; then
  step "Verification (skipped)"
else
  step "Offline tests (no mailbox access, no model calls)"
  run "$PYTHON" -m unittest discover -q -s tests -t .
  ok "tests passed"

  if [[ $SKIP_AUTH -eq 0 ]]; then
    step "Read-only, model-free dry run"
    if confirm "Preview what the starter rules would do? (reads mail metadata, changes nothing)"; then
      set +e
      run "$PYTHON" runner.py --no-model
      code=$?
      set -e
      case $code in
        0) ok "dry run finished; see state/summary.json" ;;
        2) ok "dry run finished; untagged mail awaits classification (exit 2 is expected)" ;;
        *) warn "dry run failed (exit $code); check 'gws auth status' and state/summary.json" ;;
      esac
    fi
  fi
fi

# --- 7. Next steps ----------------------------------------------------------------------
step "Done. Next steps"
cat <<EOF
  1. Health check, anytime:                   make doctor
  2. Personalize rules (read-only discovery, you approve every rule):
       open this folder in $( [[ "$CLI" == claude ]] && echo "Claude Code" || echo "Copilot" ) and ask it to use the mail-setup skill
  3. Review rules.json and classifier.json (models, limits).
  4. Paid classification, still a dry run:    make classify   ($PYTHON runner.py)
  5. Apply for real after reviewing state/:   make apply      ($PYTHON runner.py --apply)
  6. Optional hourly weekday schedule:        make schedule-install

  All commands: make help        Guide: docs/getting-started.md
EOF
