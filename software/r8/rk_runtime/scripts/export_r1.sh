#!/usr/bin/env bash
set -euo pipefail
# Usage: export_r1.sh /absolute/prepared_R1_tree /absolute/model_N.pt /absolute/policy.onnx
runtime_root=$(cd "$(dirname "$0")/.." && pwd)
task_tree=$(realpath "$1")
checkpoint=$(realpath "$2")
output_policy=$(realpath -m "$3")
cd "$task_tree"
test -f R1_TRAINING_INPUTS.json
export WANDB_MODE=offline
uv run --frozen scripts/export.py Mjlab-Velocity-Flat-MicroDuck --checkpoint-file "$checkpoint" --onnx-file "$output_policy" --num-envs 1 --device cuda:0
PYTHONPATH="$runtime_root" uv run --frozen python -m microduck_rk validate-policy "$output_policy"
PYTHONPATH="$runtime_root" uv run --frozen python -m microduck_rk.make_manifest --training-inputs R1_TRAINING_INPUTS.json --policy "$output_policy" --checkpoint "$checkpoint"
