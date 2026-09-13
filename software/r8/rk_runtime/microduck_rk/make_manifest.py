"""Attach provenance; newly exported policies remain unapproved for hardware motion."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--training-inputs',required=True);p.add_argument('--policy',required=True);p.add_argument('--checkpoint',required=True)
    a=p.parse_args();m=json.loads(Path(a.training_inputs).read_text());policy=Path(a.policy)
    m.update({'policy_sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),
              'checkpoint_sha256':hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest(),
              'normalizer':'baked by pinned upstream export_policy_to_onnx',
              'motion_approved':False,'validation_report':None,'training_completed':True})
    out=policy.with_suffix('.manifest.json');out.write_text(json.dumps(m,indent=2)+'\n');print(out)


if __name__=='__main__':main()
