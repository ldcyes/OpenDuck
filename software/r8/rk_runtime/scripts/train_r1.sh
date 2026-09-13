#!/usr/bin/env bash
set -euo pipefail
# Usage: train_r1.sh /absolute/prepared_R1_tree smoke|train [additional train CLI arguments]
if [ "$#" -lt 1 ]; then echo 'Usage: train_r1.sh PREPARED_TREE [smoke|train] [train arguments]' >&2; exit 2; fi
task_tree=$(realpath "$1")
phase=${2:-smoke}
if [ "$#" -ge 2 ]; then shift 2; else shift; fi
cd "$task_tree"
test -f R1_TRAINING_INPUTS.json || { echo 'Prepare a measured R1 tree first.' >&2; exit 2; }
export UV_HTTP_TIMEOUT=600
export WANDB_MODE=offline
uv sync --frozen --python 3.12
uv run --frozen python -c 'import torch; assert torch.cuda.is_available(), "CUDA GPU required; RK3566 runs inference only"; print(torch.cuda.get_device_name(0))'
if [ "$phase" = smoke ]; then
  uv run --frozen train Mjlab-Velocity-Flat-MicroDuck --env.scene.num-envs 64 --agent.max-iterations 5 --agent.run-name rk-r1-smoke "$@"
elif [ "$phase" = train ]; then
  test -f R1_SMOKE_PASSED.json || { echo 'Review 64-env smoke evidence, then create R1_SMOKE_PASSED.json.' >&2; exit 2; }
  uv run --frozen train Mjlab-Velocity-Flat-MicroDuck --env.scene.num-envs 4096 --agent.run-name rk-r1-walk "$@"
else
  echo 'phase must be smoke or train' >&2; exit 2
fi
