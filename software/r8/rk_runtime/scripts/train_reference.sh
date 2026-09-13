#!/usr/bin/env bash
set -euo pipefail
# Original XL330 reference training. Outputs are not authorized for the RK/XC330 robot.
runtime_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$runtime_root/../microduck_rl_upstream"
export UV_HTTP_TIMEOUT=600
export WANDB_MODE=offline
uv sync --frozen --python 3.12
uv run --frozen python -c 'import torch; assert torch.cuda.is_available(), "External CUDA GPU required; reference source is complete but training is not precomputed"; print(torch.cuda.get_device_name(0))'
uv run --frozen train Mjlab-Velocity-Flat-MicroDuck --env.scene.num-envs 64 --agent.max-iterations 5 --agent.run-name original-xl330-reference "$@"
