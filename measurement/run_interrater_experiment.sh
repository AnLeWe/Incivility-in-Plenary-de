#!/bin/bash
# Orchestrates the full interrater-agreement experiment: scores the fixed n=2000 sample
# with each of 5 models sequentially (one GPU, so no benefit to running models
# concurrently), waiting on in-flight downloads as needed, then computes agreement.
set -e
cd "$(dirname "$0")"

SAMPLE_FILE="pilot_sample_n2000_seed20260723.csv"
# DATA_ROOT from the environment, else from the repo's .env (as score_with_model.py does).
if [ -z "${DATA_ROOT:-}" ] && [ -f ../.env ]; then
    DATA_ROOT="$(grep -E '^DATA_ROOT=' ../.env | head -1 | cut -d= -f2- | tr -d "\"'")"
fi
: "${DATA_ROOT:?DATA_ROOT not set, export it or set it in the repo .env}"
SAMPLE_PATH="$DATA_ROOT/measurement/$SAMPLE_FILE"

echo "=== [1/5] qwen3:14b-q4_K_M (rescore at n=2000) ==="
../norm_env/bin/python score_with_model.py --model qwen3:14b-q4_K_M --sample-file "$SAMPLE_PATH"

echo "=== [2/5] gemma4:12b ==="
../norm_env/bin/python score_with_model.py --model gemma4:12b --sample-file "$SAMPLE_PATH"

echo "=== waiting for mistral-small3.2:24b pull to finish ==="
while ! ollama list | grep -q "mistral-small3.2:24b"; do
  sleep 15
done

echo "=== [3/5] mistral-small3.2:24b ==="
../norm_env/bin/python score_with_model.py --model mistral-small3.2:24b --sample-file "$SAMPLE_PATH"

echo "=== pulling llama3.1:8b ==="
ollama pull llama3.1:8b

echo "=== [4/5] llama3.1:8b ==="
../norm_env/bin/python score_with_model.py --model llama3.1:8b --sample-file "$SAMPLE_PATH"

echo "=== pulling gemma4:e4b ==="
ollama pull gemma4:e4b

echo "=== [5/5] gemma4:e4b (edge variant, added 2026-07-30 as a 5th data point alongside the frontier-model comparison) ==="
../norm_env/bin/python score_with_model.py --model gemma4:e4b --sample-file "$SAMPLE_PATH"

echo "=== computing interrater agreement ==="
../norm_env/bin/python compute_interrater_agreement.py --n 2000

echo "=== experiment complete ==="
