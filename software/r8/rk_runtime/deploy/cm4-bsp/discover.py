#!/usr/bin/env python3
"""Read-only CM4 DT -> Linux I2C discovery. Does not enable servo power."""
import argparse,json,pathlib

def find_sensor_bus(dt_root=pathlib.Path('/sys/firmware/devicetree/base'),
                    adapters=pathlib.Path('/sys/class/i2c-dev')):
 dt_root=pathlib.Path(dt_root).resolve();adapters=pathlib.Path(adapters)
 try:
  if b'microduck,r8-cm4' not in (dt_root/'compatible').read_bytes().split(b'\0'):
   raise RuntimeError('Loaded DT is not Microduck R8 CM4')
  alias=(dt_root/'aliases/microduck-sensors').read_bytes().rstrip(b'\0').decode('ascii')
  if not alias.startswith('/') or '..' in pathlib.PurePosixPath(alias).parts:
   raise RuntimeError('Invalid sensor DT alias')
  node=(dt_root/alias.lstrip('/')).resolve()
  if not node.is_relative_to(dt_root):raise RuntimeError('Sensor alias escapes DT')
  if (node/'status').read_bytes().rstrip(b'\0') not in (b'ok',b'okay'):
   raise RuntimeError('Sensor I2C controller is not enabled')
  matches=[]
  for adapter in adapters.glob('i2c-*'):
   if adapter.name[4:].isdigit() and (adapter/'device/of_node').resolve()==node:
    matches.append('/dev/'+adapter.name)
  if len(matches)!=1:raise RuntimeError(f'Expected one sensor adapter, found {len(matches)}')
  return matches[0]
 except (OSError,UnicodeError) as exc:
  raise RuntimeError(f'Cannot resolve loaded CM4 sensor DT: {exc}') from exc

def named_gpio_inventory():
 import gpiod
 names={'MICRODUCK_RUN_REQ','MICRODUCK_RUN_OK','MICRODUCK_AMP_ENABLE'}
 found={name:[] for name in names}
 for path in sorted(pathlib.Path('/dev').glob('gpiochip*')):
  with gpiod.Chip(str(path)) as chip:
   for offset in range(chip.get_info().num_lines):
    info=chip.get_line_info(offset)
    if info.name in found:found[info.name].append(dict(chip=str(path),offset=offset,used=info.used,consumer=info.consumer))
 if any(len(v)!=1 for v in found.values()):raise RuntimeError('Missing/duplicate CM4 GPIO line names')
 return {k:v[0] for k,v in found.items()}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--i2c-only',action='store_true');args=p.parse_args()
 bus=find_sensor_bus()
 if args.i2c_only:print(bus)
 else:print(json.dumps(dict(i2c_device=bus,gpio=named_gpio_inventory(),power_enabled_by_this_tool=False,motion_approved=False),indent=2))
