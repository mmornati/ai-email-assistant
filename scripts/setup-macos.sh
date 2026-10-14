#!/usr/bin/env bash
# Configure AI Mail Assistant from zero on macOS.
#
# Installs the CLIs with Homebrew, creates private local files, walks through
# Google Cloud / Google Workspace / Copilot authentication, and verifies the
# install with the offline tests and a model-free, read-only dry run.
#
# It never modifies mail, never enables --apply, and never installs a schedule.
# Every step is idempotent: re-run it at any time to repair or verify a setup.
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
SKIP_COPILOT=0
SKIP_VERIFY=0
GCP_PROJECT=""

usage() {
  cat <<EOF
Usage: scripts/setup-macos.sh [options]

Options:
  -y, --yes            Answer yes to every prompt (still opens browser logins)
  -n, --dry-run        Print the commands that would run; change nothing
      --project ID     Use an existing Google Cloud project for gws auth setup
      --skip-auth      Install tools and local files only; no logins
      --skip-copilot   Do not install or log in to the Copilot CLI
                       (model-free use only: runner.py --no-model)
      --skip-verify    Do not run the tests or the read-only dry run
  -h, --help           Show this help

Nothing here modifies mail, enables --apply, or installs the schedule.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    --project) GCP_PROJECT="${2:?--project requires a value}"; shift ;;
    --skip-auth) SKIP_AUTH=1 ;;
    --skip-copilot) SKIP_COPILOT=1 ;;
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
PYTHON=""
for candidate in python3 "$(brew --prefix 2>/dev/null)/bin/python3"; do
  if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
    PYTHON="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  warn "no Python 3.$MIN_PY_MINOR+ found (macOS ships 3.9); installing $BREW_PYTHON"
  run brew install "$BREW_PYTHON"
  PYTHON="$(brew --prefix "$BREW_PYTHON" 2>/dev/null || echo /opt/homebrew/opt/$BREW_PYTHON)/bin/python3"
fi
if [[ $DRY_RUN -eq 0 ]]; then
  python_ok "$PYTHON" || die "$PYTHON is not Python 3.$MIN_PY_MINOR+"
fi
ok "$PYTHON"

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
if [[ $SKIP_COPILOT -eq 0 ]]; then
  brew_install --cask copilot-cli copilot "GitHub Copilot CLI"
else
  warn "skipping Copilot CLI: only model-free runs (runner.py --no-model) will work"
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
  run cp rules.example.json rules.json
  ok "created rules.json from the starter rules (no cleanup actions enabled)"
fi

# --- 5. Authentication --------------------------------------------------------------
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

  if [[ $SKIP_COPILOT -eq 0 ]]; then
    step "GitHub Copilot CLI"
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
  1. Personalize rules (read-only discovery, you approve every rule):
       open this folder in Copilot and ask it to use the mail-setup skill
  2. Review rules.json and classifier.json (models, limits).
  3. Paid classification, still a dry run:   $PYTHON runner.py
  4. Apply for real after reviewing state/:   $PYTHON runner.py --apply
  5. Optional hourly weekday schedule:        $PYTHON schedule.py render
                                              $PYTHON schedule.py install
EOF
