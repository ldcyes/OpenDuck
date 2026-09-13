"""LSM6DSV16X SFLP over Linux I2C, based on ST's official register driver.

FIFO is the validity signal. A consumed 0x13 tagged identity quaternion is valid;
registers that were merely zero after reset are never exposed as measurements.
No synthetic orientation or IMU fallback exists in the live path.
"""
import math
import struct
import time
import threading


class ImuFault(RuntimeError):
    pass


def conjugate(q):
    return [q[0],-q[1],-q[2],-q[3]]


def multiply(a,b):
    w,x,y,z=a; v,i,j,k=b
    return [w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v]


def rotate(q,v):
    return multiply(multiply(q,[0.]+list(v)),conjugate(q))[1:]


def decode_quat(data):
    if len(data) != 6:
        raise ImuFault('short SFLP quaternion')
    xyz=list(struct.unpack('<eee',data)); n=sum(x*x for x in xyz)
    if not all(math.isfinite(x) for x in xyz) or n > 1.02:
        raise ImuFault('corrupt SFLP quaternion')
    # ST sflp2q: normalize vector if float16 rounding puts norm just above one.
    if n > 1:
        xyz=[x/math.sqrt(n) for x in xyz]; n=1.
    return [math.sqrt(1-n)]+xyz


class ImuStream:
    def __init__(self,mount,min_samples=240,max_age=.05):
        if len(mount)!=4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in mount) or abs(sum(x*x for x in mount)-1) > 1e-4:
            raise ValueError('calibrated unit IMU mounting quaternion required')
        self.mount=mount; self.min_samples=min_samples; self.max_age=max_age
        self.gyro=None; self.quat=None; self.gyro_t=None; self.quat_t=None; self.count=0

    def push(self,tag,data,now):
        if len(data)!=6:
            raise ImuFault('short FIFO record')
        if tag==0x01:
            raw=struct.unpack('<hhh',data)
            if any(abs(v)>=32760 for v in raw):
                raise ImuFault('gyro saturated at configured 500 dps')
            self.gyro=rotate(self.mount,[v*.0175*math.pi/180 for v in raw]); self.gyro_t=now
        elif tag==0x13:
            self.quat=multiply(decode_quat(data),conjugate(self.mount)); self.quat_t=now; self.count+=1

    def sample(self,now):
        if self.count<self.min_samples or self.gyro is None:
            raise ImuFault('IMU not calibrated/converged: waiting for fresh SFLP FIFO samples')
        if any(now-t>self.max_age or now<t for t in [self.gyro_t,self.quat_t]):
            raise ImuFault('IMU stale >50 ms or clock invalid')
        g=rotate(conjugate(self.quat),[0,0,-1])
        return {'gyro':self.gyro[:],'gravity':g,'quat':self.quat[:],
                'quaternion_samples':self.count,'age_s':max(now-self.gyro_t,now-self.quat_t)}


class LinuxI2c:
    def __init__(self,path,address):
        from smbus2 import SMBus,i2c_msg
        self.bus=SMBus(path); self.address=address; self.msg=i2c_msg

    def read(self,register,count):
        addr=self.msg.write(self.address,[register]); data=self.msg.read(self.address,count)
        self.bus.i2c_rdwr(addr,data)
        return bytes(data)

    def write(self,register,value):
        self.bus.i2c_rdwr(self.msg.write(self.address,[register,value]))

    def close(self):
        self.bus.close()


class Lsm6dsv16x:
    def __init__(self,bus,mount,clock=time.monotonic,sleep=time.sleep):
        self.bus=bus; self.clock=clock; self.sleep=sleep; self.stream=ImuStream(mount)

    def initialize(self):
        if self.bus.read(0x0f,1)!=b'\x70':
            raise ImuFault('WHO_AM_I is not LSM6DSV16X 0x70')
        self.bus.write(0x01,0x04)  # ST sw_por resets main + embedded functions.
        self.sleep(.03)
        self.bus.write(0x12,0x44)  # BDU and IF_INC.
        self.bus.write(0x15,0x02)  # Gyro ±500 dps, 17.5 mdps/LSB.
        self.bus.write(0x17,0x01)  # Accel ±4g.
        self.bus.write(0x0a,0x00)  # FIFO bypass, flush.
        self.bus.write(0x09,0x60)  # Gyro FIFO batch 120Hz; no raw accel batch.
        self.bus.write(0x01,0x80)  # Embedded bank.
        try:
            self.bus.write(0x44,0x02)  # SFLP_GAME_FIFO_EN; only quaternion batch.
            self.bus.write(0x5e,0x18)  # SFLP_GAME_ODR=3 -> 120Hz, bits 5:3.
        finally:
            self.bus.write(0x01,0x00)
        self.bus.write(0x10,0x06)  # Accel high-performance 120Hz.
        self.bus.write(0x11,0x06)  # Gyro high-performance 120Hz.
        self.bus.write(0x0a,0x06)  # Continuous FIFO.
        self.bus.write(0x01,0x80)
        try:
            self.bus.write(0x04,0x02)  # SFLP_GAME_EN after ODR setup, matching ST sequence.
            for reg,want in [(0x44,2),(0x5e,0x18),(0x04,2)]:
                if self.bus.read(reg,1)[0]!=want: raise ImuFault('embedded SFLP configuration readback failed')
        finally:
            self.bus.write(0x01,0)
        for reg,want in [(0x12,0x44),(0x15,0x02),(0x17,0x01),(0x09,0x60),(0x10,6),(0x11,6),(0x0a,6)]:
            if self.bus.read(reg,1)[0]!=want:
                raise ImuFault(f'IMU configuration readback failed at 0x{reg:02x}')

    def poll(self):
        t=self.clock(); status=self.bus.read(0x1b,2)
        if len(status)!=2 or status[1]&0x68:
            raise ImuFault('FIFO full/overrun or short status; orientation history lost')
        count=status[0]+((status[1]&1)<<8)
        # FIFO 120 gyro +120 quat =240 records/s; >12 records already spans >50ms.
        if count>12:
            raise ImuFault('FIFO backlog exceeds 50ms freshness budget')
        for _ in range(count):
            record=self.bus.read(0x78,7)
            if len(record)!=7:
                raise ImuFault('short FIFO read')
            self.stream.push(record[0]>>3,record[1:],t)
        return count

    def read(self):
        self.poll()
        return self.stream.sample(self.clock())

    def warmup(self,timeout=5.):
        start=self.clock()
        while self.clock()-start<timeout:
            self.poll()
            if self.stream.count>=self.stream.min_samples and self.stream.gyro is not None:
                return self.stream.sample(self.clock())
            self.sleep(.005)
        raise ImuFault('no valid SFLP after 5 seconds; motion remains disabled')


class ImuWorker:
    """Drain FIFO independently while USB servo configuration blocks the control thread."""
    def __init__(self,imu):
        self.imu=imu;self.lock=threading.Lock();self.error=None
        self.stop=threading.Event();self.thread=threading.Thread(target=self._loop,daemon=True)

    def start(self):
        self.imu.initialize();self.thread.start()

    def _loop(self):
        try:
            while not self.stop.is_set():
                with self.lock: self.imu.poll()
                self.stop.wait(.003)
        except Exception as exc:
            self.error=exc

    def read(self):
        if self.error: raise ImuFault(f'IMU worker stopped: {self.error}')
        with self.lock: return self.imu.stream.sample(self.imu.clock())

    def wait_ready(self,timeout=5.):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if self.error: raise ImuFault(f'IMU worker stopped: {self.error}')
            with self.lock:
                if self.imu.stream.count>=self.imu.stream.min_samples and self.imu.stream.gyro is not None:
                    return self.imu.stream.sample(self.imu.clock())
            time.sleep(.005)
        raise ImuFault('SFLP startup timeout; motion disabled')

    def close(self):
        self.stop.set()
        if self.thread.is_alive(): self.thread.join(timeout=1.)
