"""Hardware transport is substituted only here; live driver never uses fake data."""
import struct
import unittest
from microduck_rk.imu import Lsm6dsv16x,ImuFault
from microduck_rk.dynamixel import Dynamixels,signed
from microduck_rk.contract import IDS
from microduck_rk.actuators import spec_for_id, current_raw


class RegisterBus:
    def __init__(self): self.bank=0;self.reg={(0,15):0x70};self.fifo=[];self.overrun=False
    def write(self,r,v):
        if r==1: self.bank=1 if v==0x80 else 0
        else: self.reg[self.bank,r]=v
    def read(self,r,n):
        if r==0x1b:return bytes([len(self.fifo),0x40 if self.overrun else 0])
        if r==0x78:return self.fifo.pop(0)
        return bytes([self.reg.get((self.bank,r),0)])


class ServoRegisters(Dynamixels):
    """Test-only register transport; rejects unsupported firmware reads."""
    def __init__(self,firmware=46,startup=0,torque=0):
        from test_mixed_drive import data,load
        self.cal=load(data())  # Explicit synthetic mouth acceptance before testing firmware gate.
        self.reg={i:{0:spec_for_id(i).model_number,6:firmware,9:0,10:0,11:5,20:0,31:70,32:118,34:100,38:current_raw(i,300),
                    60:startup,63:53,64:torque,70:0,132:2048,144:80,146:25} for i in IDS}
        self.events=[];self.ignore_startup_write=False

    def read_register(self,i,address,size):
        self.events.append(('read',i,address,size))
        if address==60 and self.reg[i][6]<spec_for_id(i).minimum_firmware:
            raise AssertionError('Startup Configuration read on unsupported firmware')
        return self.reg[i][address]

    def write_register(self,i,address,size,value):
        self.events.append(('write',i,address,size,value))
        if not (address==60 and self.ignore_startup_write): self.reg[i][address]=value


class StartupConfigurationTests(unittest.TestCase):
    def test_commission_clears_startup_after_all_torque_off_and_reads_back(self):
        d=ServoRegisters(startup=3,torque=1);d.commission()
        self.assertEqual(d.events[:len(IDS)],[('write',i,64,1,0) for i in IDS])
        for i in IDS:
            event=('write',i,60,1,0);index=d.events.index(event)
            self.assertEqual(d.events[index+1],('read',i,60,1))
            for j in IDS:
                self.assertLess(d.events.index(('read',j,6,1)),index)
            self.assertEqual(d.reg[i][60],0);self.assertEqual(d.reg[i][64],0)
        self.assertFalse(any(e[0]=='write' and e[2]==64 and e[4]!=0 for e in d.events))

    def test_verify_rejects_each_nonzero_startup_configuration(self):
        for value in (1,2,3):
            with self.subTest(startup=value):
                d=ServoRegisters(startup=value)
                with self.assertRaisesRegex(RuntimeError,'reg60'): d.verify()
                self.assertFalse(any(e[0]=='write' for e in d.events))

    def test_enable_rejects_startup_configuration_before_any_write(self):
        d=ServoRegisters();d.reg[IDS[-1]][60]=1
        with self.assertRaisesRegex(RuntimeError,'reg60'): d.enable([0]*15)
        self.assertFalse(any(e[0]=='write' for e in d.events))

    def test_old_firmware_rejects_verification_and_enable_without_reading_startup(self):
        for method in ('verify','enable'):
            with self.subTest(method=method):
                d=ServoRegisters(firmware=45)
                with self.assertRaisesRegex(RuntimeError,'firmware.*46'):
                    getattr(d,method)(*([[]] if method=='enable' else []))
                self.assertFalse(any(e[0]=='write' or e[2]==60 for e in d.events))

    def test_old_firmware_commission_turns_all_off_before_refusing_eeprom_changes(self):
        d=ServoRegisters(startup=3,torque=1);d.reg[20][6]=45
        with self.assertRaisesRegex(RuntimeError,'firmware.*46'): d.commission()
        self.assertEqual([e for e in d.events if e[0]=='write'],[('write',i,64,1,0) for i in IDS])
        self.assertFalse(any(e[2]==60 for e in d.events))

    def test_inspect_reports_firmware_and_skips_unsupported_startup_register(self):
        d=ServoRegisters(startup=3);d.reg[IDS[0]][6]=45
        result=d.inspect()
        self.assertEqual(result[0]['firmware'],45)
        self.assertIsNone(result[0]['startup_configuration'])
        self.assertEqual(result[1]['firmware'],46)
        self.assertEqual(result[1]['startup_configuration'],3)
        self.assertFalse(any(e[0]=='write' for e in d.events))

    def test_commission_refuses_failed_startup_readback_without_enabling_torque(self):
        d=ServoRegisters(startup=3);d.ignore_startup_write=True
        with self.assertRaisesRegex(RuntimeError,'reg60'): d.commission()
        self.assertFalse(any(e[0]=='write' and e[2]==64 and e[4]!=0 for e in d.events))


class HardwareLogicTests(unittest.TestCase):
    def test_real_register_sequence_selects_sflp120_and_gyro500(self):
        b=RegisterBus();d=Lsm6dsv16x(b,[1,0,0,0],sleep=lambda _:None)
        d.initialize()
        self.assertEqual(b.bank,0)
        self.assertEqual(b.reg[1,0x5e],0x18)
        self.assertEqual(b.reg[1,0x44],2)
        self.assertEqual(b.reg[0,0x15],2)
        self.assertEqual(b.reg[0,0x09],0x60)
        self.assertEqual(b.reg[0,0x0a],6)

    def test_wrong_chip_rejected_before_setup(self):
        b=RegisterBus();b.reg[0,15]=0
        with self.assertRaises(ImuFault):Lsm6dsv16x(b,[1,0,0,0]).initialize()

    def test_fifo_tag_shift_and_fresh_identity(self):
        b=RegisterBus();d=Lsm6dsv16x(b,[1,0,0,0],clock=lambda:10)
        d.stream.min_samples=1
        b.fifo=[bytes([1<<3])+struct.pack('<hhh',100,0,0),bytes([0x13<<3])+bytes(6)]
        s=d.read();self.assertEqual(s['gravity'],[0,0,-1]);self.assertGreater(s['gyro'][0],0)

    def test_fifo_overrun_is_fatal(self):
        b=RegisterBus();b.overrun=True
        with self.assertRaises(ImuFault):Lsm6dsv16x(b,[1,0,0,0]).poll()

    def test_missing_fifo_never_synthesizes_upright(self):
        with self.assertRaises(ImuFault):Lsm6dsv16x(RegisterBus(),[1,0,0,0]).read()

    def test_torque_off_attempts_every_servo_after_failure(self):
        d=Dynamixels.__new__(Dynamixels);calls=[]
        def write(i,a,n,v):
            calls.append(i)
            if i==IDS[0]:raise RuntimeError('simulated unplugged servo')
        d.write_register=write
        failures=d.torque_off()
        self.assertEqual(calls,IDS);self.assertEqual(len(failures),1)

    def test_torque_already_on_blocks_verify(self):
        d=Dynamixels.__new__(Dynamixels)
        d.cal=ServoRegisters().cal
        d.read_register=lambda i,a,s: 1 if a==64 else 0
        with self.assertRaisesRegex(RuntimeError,'reg64'): d.verify()

    def test_signed_register_decoding(self):
        self.assertEqual(signed(0xffff,16),-1)
        self.assertEqual(signed(0xffffffff,32),-1)
        self.assertEqual(signed(0x7fffffff,32),2147483647)
