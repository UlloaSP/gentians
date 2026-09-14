#!/usr/bin/env bash
set -uo pipefail

ilasp=${ILASP_BIN:-/mnt/c/tmp/ILASP}
task=${ILASP_TASK:-benchmarks/ilasp/5queens.las}
runtime=${ILASP_PYTHON_RUNTIME:-/tmp/ilasp-python310/root/usr}
timeout_seconds=${ILASP_TIMEOUT_SECONDS:-180}
output=${ILASP_OUTPUT:-.benchmarks/experiments/ilasp-5queens}

if [[ ! -x "$ilasp" ]]; then
    printf "ILASP executable not found: %s\n" "$ilasp" >&2
    exit 2
fi
if [[ ! -f "$task" ]]; then
    printf "ILASP task not found: %s\n" "$task" >&2
    exit 2
fi
if [[ ! -f "$runtime/lib/x86_64-linux-gnu/libpython3.10.so.1.0" ]]; then
    printf "Python 3.10 runtime not found: %s\n" "$runtime" >&2
    exit 2
fi

mkdir -p "$output"
printf "version\tstatus\twall_seconds\n" > "$output/timings.tsv"

for version in 2 2i 3 4; do
    started=$(date +%s%N)
    LD_LIBRARY_PATH="$runtime/lib/x86_64-linux-gnu" PYTHONHOME="$runtime" \
        timeout --signal=INT --kill-after=5s "${timeout_seconds}s" \
        "$ilasp" "--version=$version" -ml=5 "$task" \
        > "$output/version-$version.out" 2> "$output/version-$version.err"
    status=$?
    finished=$(date +%s%N)
    wall_seconds=$(awk "BEGIN { printf \"%.6f\", ($finished-$started)/1000000000 }")
    printf "%s\t%s\t%s\n" "$version" "$status" "$wall_seconds" \
        >> "$output/timings.tsv"
done

cat "$output/timings.tsv"
