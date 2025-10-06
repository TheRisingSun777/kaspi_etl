#!/bin/zsh

# Guard against multiple sourcing
if [[ -n "${__KASPI_ENV_BOOTSTRAP_LOADED:-}" ]]; then
  return
fi
__KASPI_ENV_BOOTSTRAP_LOADED=1

kaspi_env_log() {
  # Always log to stderr so callers can safely capture stdout
  echo "$@" >&2
}

kaspi_sha256_file() {
  local target="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$target" | awk '{print $1}'
    return
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$target" | awk '{print $1}'
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$target" <<'PY'
import hashlib
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
    return
  fi
  kaspi_env_log "Unable to compute sha256 (no shasum/sha256sum/python3)"
  return 1
}

kaspi_sha256_string() {
  local value="$1"
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$value" | shasum -a 256 | awk '{print $1}'
    return
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$value" | sha256sum | awk '{print $1}'
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$value" <<'PY'
import hashlib
import sys
print(hashlib.sha256(sys.argv[1].encode()).hexdigest())
PY
    return
  fi
  kaspi_env_log "Unable to compute sha256 for string"
  return 1
}

kaspi_requirements_hash() {
  local requirements_file="$1"
  if [[ ! -f "$requirements_file" ]]; then
    kaspi_env_log "Requirements file not found: $requirements_file"
    return 1
  fi
  kaspi_sha256_file "$requirements_file"
}

kaspi_cache_dir() {
  echo "${REPO_ROOT}/.cache/kaspi"
}

kaspi_requirements_sentinel() {
  local python_bin="$1"
  local requirements_file="$2"
  local cache_root
  cache_root="$(kaspi_cache_dir)"
  local python_hash
  python_hash="$(kaspi_sha256_string "$python_bin")" || return 1
  python_hash="${python_hash:0:16}"
  local req_hash
  req_hash="$(kaspi_requirements_hash "$requirements_file")" || return 1
  echo "$cache_root/requirements_${python_hash}.sha256"
}

kaspi_verify_imports() {
  local python_bin="$1"
  local script
  script=$'import importlib\nmodules = ["pandas", "openpyxl", "xlwings", "dateutil"]\nmissing = []\nfor name in modules:\n    try:\n        importlib.import_module(name)\n    except Exception as exc:  # noqa: PERF203 - diagnostics only\n        missing.append(f"{name}: {exc}")\nif missing:\n    raise SystemExit("; ".join(missing))\n'
  local output
  output="$("$python_bin" -c "$script" 2>&1)"
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    kaspi_env_log "Python module check failed for $python_bin: $output"
    return 1
  fi
  return 0
}

kaspi_install_requirements() {
  local python_bin="$1"
  local requirements_file="$2"
  local cache_root
  cache_root="$(kaspi_cache_dir)"
  mkdir -p "$cache_root"
  kaspi_env_log "📦 Installing Python dependencies via $python_bin"
  PIP_DISABLE_PIP_VERSION_CHECK=1 "$python_bin" -m pip install --upgrade pip >/dev/null
  PIP_DISABLE_PIP_VERSION_CHECK=1 "$python_bin" -m pip install -r "$requirements_file" >&2
  kaspi_verify_imports "$python_bin" || return 1
  local req_hash
  req_hash="$(kaspi_requirements_hash "$requirements_file")" || return 1
  local sentinel
  sentinel="$(kaspi_requirements_sentinel "$python_bin" "$requirements_file")" || return 1
  echo "$req_hash" > "$sentinel"
}

kaspi_ensure_requirements() {
  local python_bin="$1"
  local requirements_file="$2"
  local sentinel
  sentinel="$(kaspi_requirements_sentinel "$python_bin" "$requirements_file")" || return 1
  local req_hash
  req_hash="$(kaspi_requirements_hash "$requirements_file")" || return 1
  local current_hash=""
  if [[ -f "$sentinel" ]]; then
    current_hash="$(<"$sentinel")"
  fi
  if [[ "$current_hash" != "$req_hash" ]] || ! kaspi_verify_imports "$python_bin"; then
    kaspi_install_requirements "$python_bin" "$requirements_file"
  fi
}

kaspi_select_python() {
  local requirements_file="$1"
  local override="${KASPI_PYTHON_BIN:-${PYTHON_BIN:-}}"
  local repo_venv_py="${REPO_ROOT}/venv/bin/python"
  local bootstrap_python=""
  if [[ ! -f "$requirements_file" ]]; then
    kaspi_env_log "Requirements file missing: $requirements_file"
    if [[ -n "$override" ]]; then
      echo "$override"
      return 0
    fi
    bootstrap_python="$(command -v python3 || true)"
    if [[ -z "$bootstrap_python" ]]; then
      kaspi_env_log "Unable to locate python3 interpreter"
      return 1
    fi
    echo "$bootstrap_python"
    return 0
  fi
  if [[ -n "$override" ]]; then
    if [[ ! -x "$override" ]]; then
      kaspi_env_log "Provided python binary is not executable: $override"
      return 1
    fi
    kaspi_ensure_requirements "$override" "$requirements_file"
    echo "$override"
    return 0
  fi

  if [[ -x "$repo_venv_py" ]]; then
    bootstrap_python="$repo_venv_py"
  else
    bootstrap_python="$(command -v python3 || true)"
    if [[ -z "$bootstrap_python" ]]; then
      kaspi_env_log "Unable to locate python3 for virtualenv creation"
      return 1
    fi
    kaspi_env_log "🐍 Creating project virtualenv at ${REPO_ROOT}/venv"
    "$bootstrap_python" -m venv "${REPO_ROOT}/venv"
    bootstrap_python="$repo_venv_py"
  fi

  kaspi_ensure_requirements "$bootstrap_python" "$requirements_file"
  echo "$bootstrap_python"
}
