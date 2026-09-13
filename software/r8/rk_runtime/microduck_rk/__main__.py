"""Explicit commissioning, diagnostics, command lease, and 50 Hz control CLI."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from .contract import Calibration,observation,action_targets
from .safety import Guard,read_command,mouth_step,check_joint_currents
from .telemetry import publish as publish_telemetry
from .motion_context import MotionContextGuard
from microduck_interaction.executor import CommandWriter
from microduck_interaction.schema import ROBOT_PROFILE


def hardware_args(p):
    p.add_argument('--calibration',required=True)
    p.add_argument('--serial',default='/dev/serial/by-id/REPLACE_WITH_U2D2_ID')
    p.add_argument('--i2c',help='optional override must equal calibrated CM4 sensor I2C device')
    p.add_argument('--power-config',required=True,help='measured CM4 power calibration JSON')
    p.add_argument('--address',type=lambda s:int(s,0),default=0x6a)


def run(args):
    if Path(args.stop_file).exists(): raise RuntimeError('STOP file present; hardware startup refused')
    if isinstance(args.seconds,bool) or not math.isfinite(args.seconds) or not 0<args.seconds<=7200:raise ValueError('run duration must be finite, positive, at most7200s')
    from .imu import LinuxI2c,Lsm6dsv16x,ImuWorker
    from .dynamixel import Dynamixels
    from .policy import Policy
    from .power import PowerConfig,PowerSystem
    # All gates before opening a servo port. Template cannot arm.
    cal=Calibration.load(args.calibration,motion=True)
    if args.robot_profile!=cal.data['robot']:raise ValueError('R8 telemetry/action robot profile mismatch')
    if not args.arm: raise ValueError('run requires explicit --arm after commissioning')
    power_config=PowerConfig.load(args.power_config)
    if power_config.sha256!=cal.data.get('power_configuration_sha256'):raise ValueError('power configuration SHA differs from calibrated robot')
    if args.address!=0x6a or (args.i2c and args.i2c!=power_config.data['i2c_device']):raise ValueError('CM4 sensor bus/address differs from power contract')
    context=MotionContextGuard(cal.home,getattr(args,'motion_context','head_home_locked'),getattr(args,'confirm_supported_double',False))
    policy=Policy(args.policy,cal,args.manifest,context.mode)
    bench=policy.benchmark()
    if bench['p99_ms']>8: raise RuntimeError(f'CPU policy p99 exceeds 8ms preflight budget: {bench}')
    bus=None;motors=None;log=None;imu=None;power=None
    last_measured=None;last_sent=None
    def stop_signal(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop_signal); signal.signal(signal.SIGINT,stop_signal)
    try:
        power=PowerSystem(power_config);power.start()
        bus=LinuxI2c(power_config.data['i2c_device'],args.address)
        imu=ImuWorker(Lsm6dsv16x(bus,cal.data['imu_sensor_to_trunk_wxyz']));imu.start();imu.wait_ready()
        power.enable();time.sleep(.2) # Rail established before bounded servo boot/verification; torque still off.
        motors=Dynamixels(args.serial,cal); motors.prepare_enable()
        actual=motors.read(); state=imu.read(); cmd,mouth,lease=read_command(args.command)
        check_joint_currents(actual['current_ma'],cal)
        guard=Guard(cal.data);guard.check(time.monotonic(),actual['volts'],actual['temps'],state['gravity'],lease)
        # Bringup requires physical placement within 0.1 rad of home. No blind homing sweep.
        if max(abs(p-h) for p,h in zip(actual['positions'],cal.home))>.1:
            raise RuntimeError('place supported robot within 0.1 rad of calibrated home before arming')
        if Path(args.stop_file).exists(): raise RuntimeError('STOP file present; torque enable refused')
        # Torque remains off: require a stream of actual stable readings, never a sent HOME target.
        settle_deadline=time.monotonic()+2.
        while True:
            if Path(args.stop_file).exists():raise RuntimeError('STOP during measured HOME preflight')
            actual=motors.read();state=imu.read();measured=time.monotonic()
            cmd,mouth,lease=read_command(args.command);context.validate_commands(cmd,mouth)
            power.check();check_joint_currents(actual['current_ma'],cal)
            guard.check(time.monotonic(),actual['volts'],actual['temps'],state['gravity'],lease)
            ready=context.observe(actual['positions'],actual['velocities'],state['gyro'],state['gravity'],measured,time.monotonic(),state['age_s'])
            last_measured=(actual,state,measured)
            if args.telemetry:publish_telemetry(args.telemetry,actual,state,cal.sha256,args.robot_profile,False,measured,motion_context=context.status())
            if ready:break
            if time.monotonic()>=settle_deadline:raise RuntimeError('actual HOME did not remain stable for0.5s within2s')
            time.sleep(.02)
        def arming_ready():
            context.require_fresh(time.monotonic())
            if Path(args.stop_file).exists():raise RuntimeError('STOP during torque enable')
            cmd,mouth,lease=read_command(args.command);context.validate_commands(cmd,mouth)
            power.check()
            guard.check(time.monotonic(),actual['volts'],actual['temps'],state['gravity'],lease)
            context.require_fresh(time.monotonic())
        context.activate(time.monotonic())
        motors.enable(actual['positions'],check_ready=arming_ready)
        power.activate_control()  # Short 50Hz heartbeat starts after bounded torque setup.
        previous_target=actual['positions']; previous_action=[0.]*14
        log=open(args.log,'a',buffering=1); log.write(json.dumps({'event':'armed','calibration_sha256':cal.sha256,'benchmark':bench})+'\n')
        tick=time.monotonic(); next_health=tick; deadline=tick+args.seconds
        while time.monotonic()<deadline:
            start=time.monotonic()
            if Path(args.stop_file).exists(): raise RuntimeError('STOP file present')
            imu_state=imu.read(); imu_read_at=time.monotonic(); sensors=motors.read(); measured_at=time.monotonic()
            imu_state={**imu_state,'age_s':imu_state['age_s']+measured_at-imu_read_at}
            last_measured=(sensors,imu_state,measured_at)
            commands,mouth,lease=read_command(args.command)
            context.observe(sensors['positions'],sensors['velocities'],imu_state['gyro'],imu_state['gravity'],measured_at,time.monotonic(),imu_state['age_s'])
            context.validate_commands(commands,mouth)
            power_state=power.check()
            check_joint_currents(sensors['current_ma'],cal)
            guard.check(time.monotonic(),sensors['volts'],sensors['temps'],imu_state['gravity'],lease)
            if start>=next_health:
                motors.check_health()
                next_health=start+1
            obs=observation(imu_state['gyro'],imu_state['gravity'],sensors['positions'],sensors['velocities'],previous_action,commands,cal.home)
            mouth_joint=cal.joints[9]
            mouth=mouth_step(mouth,previous_target[9],mouth_joint['min_rad'],mouth_joint['max_rad'],mouth_joint['max_step_rad'])
            raw_actions=policy.run(obs);actions,mouth=context.filter_actions(raw_actions,mouth); target=action_targets(actions,mouth,cal.home,cal.data['action_scale'])
            cal.check_step(target,previous_target)
            elapsed=time.monotonic()-start
            if elapsed>.020: raise RuntimeError(f'control computation missed 20ms deadline ({elapsed:.4f}s)')
            motors.write(target);sent_at=time.monotonic();previous_action=raw_actions;previous_target=target
            last_sent={'commands':commands,'mouth_rad':mouth,'monotonic_s':sent_at,'source_monotonic_s':lease}
            if args.telemetry: publish_telemetry(args.telemetry,sensors,imu_state,cal.sha256,args.robot_profile,True,measured_at,last_sent,motion_context=context.status())
            log.write(json.dumps({'t':start,'obs':obs,'actions':raw_actions,'applied_actions':actions,'motion_context':context.status(),'targets':target,'volts':sensors['volts'],
                                  'temps':sensors['temps'],'current_ma':sensors['current_ma'],'imu_age':imu_state['age_s'],
                                  'power':power_state,'cycle_ms':(time.monotonic()-start)*1000})+'\n')
            tick+=.02
            if time.monotonic()>tick: raise RuntimeError('control output/logging missed 20ms deadline')
            time.sleep(max(0,tick-time.monotonic()))
    finally:
        original=sys.exc_info()[1];cleanup=[]
        if power:
            try:power.close()
            except Exception as exc:cleanup.append('RUN_REQ shutdown failed: '+str(exc))
        if motors:
            try:
                failures=motors.torque_off()
                if failures:print('TorqueOff not acknowledged after requested supply cut: '+'; '.join(failures),file=sys.stderr)
            except Exception as exc:cleanup.append('motor cleanup: '+str(exc))
            finally:
                try:motors.close()
                except Exception as exc:cleanup.append('motor port close: '+str(exc))
        if args.telemetry and last_measured:
            try:publish_telemetry(args.telemetry,last_measured[0],last_measured[1],cal.sha256,args.robot_profile,False,last_measured[2],last_sent,motion_context={**context.status(),'active':False,'ready':False})
            except Exception as exc:cleanup.append('telemetry final state: '+str(exc))
        for resource in [log,imu,bus]:
            if resource:
                try:resource.close()
                except Exception as exc:cleanup.append('resource close: '+str(exc))
        if cleanup:raise RuntimeError((str(original)+'; 'if original else '')+'; '.join(cleanup))


def powered_servo_command(args):
    from .power import PowerConfig,PowerSystem
    from .dynamixel import Dynamixels
    c=Calibration.load(args.calibration,motion=False);cfg=PowerConfig.load(args.power_config)
    supply=None;m=None
    try:
        supply=PowerSystem(cfg);supply.start();supply.enable();time.sleep(.2)
        m=Dynamixels(args.serial,c);supply.check()
        if args.mode=='inspect':print(json.dumps(m.inspect(),indent=2))
        else:
            m.commission();supply.check()
            print('Commissioned per-model settings; torque remains off. Power closes on command exit.')
    finally:
        try:
            if supply:supply.close()
        finally:
            if m:
                try:
                    if args.mode=='commission':m.torque_off()
                finally:m.close()


def bench_power_capture(args):
    """Isolated electronic-load calibration only: no actuator transport exists here."""
    from .power import PowerSystem
    from .power_io import ntc_temperature
    if args.confirm_servos_disconnected is not True or isinstance(args.seconds,bool) or not math.isfinite(args.seconds) or not .5<=args.seconds<=5:
        raise ValueError('bench capture requires disconnected servo confirmation and0.5..5s duration')
    if Path(args.stop_file).exists():raise RuntimeError('STOP file present; bench supply refused')
    class NominalBenchOnly:
        data={'measurements_verified':False,'i2c_device':args.i2c,
              'ina226':{n:{'current_gain':1.,'current_offset_A':0.,'bus_gain':1.,'bus_offset_V':0.}for n in ('battery','servo','brake')},
              'adc':{'gain':1.,'offset_V':0.}}
        @staticmethod
        def temperature(name,voltage,excitation):return ntc_temperature(voltage,excitation,10000,10000,3977)
    supply=None;records=[]
    try:
        supply=PowerSystem(NominalBenchOnly());supply.start();deadline=time.monotonic()+args.seconds
        supply.enable();supply.activate_control()
        while time.monotonic()<deadline:
            if Path(args.stop_file).exists():raise RuntimeError('STOP file present')
            row=supply.check()
            if abs(row['power']['servo']['current_A'])>5.:raise RuntimeError('isolated calibration load exceeds5A ceiling')
            records.append(row);time.sleep(min(.02,max(0,deadline-time.monotonic())))
        if not records:raise RuntimeError('no samples before bounded calibration deadline')
        return {'calibrated':False,'motion_approved':False,'source':'live hardware, nominal conversion for isolated load calibration only','servo_bus_physically_disconnected_confirmed':True,'maximum_requested_duration_s':args.seconds,'samples':records}
    finally:
        if supply:supply.close()


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('check-calibration');q.add_argument('path')
    q=sub.add_parser('imu');q.add_argument('--i2c',required=True);q.add_argument('--address',type=lambda s:int(s,0),default=0x6a)
    q.add_argument('--mount',type=float,nargs=4,required=True,metavar=('W','X','Y','Z'));q.add_argument('--seconds',type=float,default=10)
    q=sub.add_parser('power-diagnostics');q.add_argument('--i2c',required=True)
    q=sub.add_parser('bench-power-capture');q.add_argument('--i2c',required=True);q.add_argument('--confirm-servos-disconnected',action='store_true',required=True)
    q.add_argument('--seconds',type=float,default=2);q.add_argument('--stop-file',default='/tmp/microduck-r8.STOP')
    q=sub.add_parser('commission');hardware_args(q)
    q=sub.add_parser('inspect');hardware_args(q)
    q=sub.add_parser('stop');q.add_argument('--path',default='/tmp/microduck-r8.STOP')
    q=sub.add_parser('command');q.add_argument('--path',default='/tmp/microduck-r8-command.json')
    q.add_argument('--vx',type=float,default=0);q.add_argument('--vy',type=float,default=0);q.add_argument('--yaw',type=float,default=0)
    q.add_argument('--head',type=float,nargs=4,default=[0]*4);q.add_argument('--body',type=float,nargs=3,default=[0]*3)
    q.add_argument('--mouth',type=float,default=0);q.add_argument('--seconds',type=float,default=10)
    q=sub.add_parser('run');hardware_args(q);q.add_argument('--policy',required=True);q.add_argument('--manifest',required=True)
    q.add_argument('--arm',action='store_true');q.add_argument('--command',default='/tmp/microduck-r8-command.json')
    q.add_argument('--stop-file',default='/tmp/microduck-r8.STOP');q.add_argument('--log',default='run.jsonl');q.add_argument('--seconds',type=float,default=10)
    q.add_argument('--motion-context',choices=('head_home_locked','supported_double'),default='head_home_locked')
    q.add_argument('--confirm-supported-double',action='store_true',help='actual dual-foot supported setup; not an automatic contact measurement')
    q.add_argument('--telemetry',help='atomically publish latest actual joint/IMU state for local clients')
    q.add_argument('--robot-profile',default=ROBOT_PROFILE)
    q=sub.add_parser('validate-policy');q.add_argument('path')
    args=p.parse_args()
    if args.mode in ('run','commission','inspect','power-diagnostics','bench-power-capture'):
        def interrupted(*_):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    if args.mode=='check-calibration':
        c=Calibration.load(args.path,motion=True);print(json.dumps({'calibration_sha256':c.sha256,'motion_gate':'passed'}))
    elif args.mode=='stop':
        Path(args.path).write_text('Operator stop\n');print('Stop requested; confirm torque/power status on hardware.')
    elif args.mode=='command':
        end=time.monotonic()+args.seconds;path=Path(args.path)
        with CommandWriter(path) as writer:
            while time.monotonic()<end:
                data={'monotonic_s':time.monotonic(),'commands':[args.vx,args.vy,args.yaw]+args.head+[0,0]+args.body+[0],'mouth_rad':args.mouth}
                writer.write(data);read_command(path);time.sleep(.05)
    elif args.mode=='imu':
        from .imu import LinuxI2c,Lsm6dsv16x
        bus=LinuxI2c(args.i2c,args.address)
        try:
            imu=Lsm6dsv16x(bus,args.mount);imu.initialize();imu.warmup();end=time.monotonic()+args.seconds
            while time.monotonic()<end: print(json.dumps(imu.read()));time.sleep(.02)
        finally: bus.close()
    elif args.mode in ('commission','inspect'):powered_servo_command(args)
    elif args.mode=='bench-power-capture':print(json.dumps(bench_power_capture(args),indent=2))
    elif args.mode=='power-diagnostics':
        from .power_io import raw_diagnostics
        print(json.dumps(raw_diagnostics(args.i2c),indent=2))
    elif args.mode=='validate-policy':
        from .policy import Policy
        print(json.dumps(Policy(args.path).benchmark(),indent=2))
    else: run(args)


if __name__=='__main__':
    try: main()
    except (ValueError,RuntimeError,OSError,KeyboardInterrupt) as exc:
        print(f'STOPPED: {exc}',file=sys.stderr);sys.exit(2)
