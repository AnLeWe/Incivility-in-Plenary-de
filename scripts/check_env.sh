#!/bin/sh
# Verify system-level tools this project needs are on PATH. Run after cloning
# on a new machine, before following the README setup steps.

status=0

check() {
    name="$1"
    cmd="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" --version 2>&1 | head -1)
        printf "  ok    %-8s %s\n" "$name" "$version"
    else
        printf "  MISSING %-8s not found on PATH\n" "$name"
        status=1
    fi
}

echo "Checking required tools..."
check "uv" uv
check "R" Rscript
check "quarto" quarto
check "git" git

if [ -z "$DATA_ROOT" ]; then
    echo "  MISSING DATA_ROOT env var not set (see .env.example / .Renviron.example)"
    status=1
else
    if [ -d "$DATA_ROOT" ]; then
        echo "  ok      DATA_ROOT=$DATA_ROOT"
    else
        echo "  MISSING DATA_ROOT=$DATA_ROOT does not exist (Drive not synced yet?)"
        status=1
    fi
fi

exit $status
