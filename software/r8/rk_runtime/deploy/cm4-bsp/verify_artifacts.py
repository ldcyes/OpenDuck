#!/usr/bin/env python3
"""Offline verification of compiled DTB and actual C callbacks; no hardware claims."""
import pathlib,subprocess,struct,json,hashlib,re
D=pathlib.Path(__file__).resolve().parent
F=D/'rk3576-microduck-r8.dtb'
checks=[]
def raw(node,prop):
 s=subprocess.check_output(['fdtget','-t','bx',str(F),node,prop],text=True)
 return bytes(int(x,16) for x in s.split())
def text(node,prop):return raw(node,prop).rstrip(b'\0').decode()
def nums(node,prop):
 v=raw(node,prop);return list(struct.unpack('>'+str(len(v)//4)+'I',v))
def ck(name,value):
 if not value:raise AssertionError(name)
 checks.append(name)
def sym(name):return text('/__symbols__',name)
ck('board compatible',b'microduck,r8-cm4' in raw('/','compatible').split(b'\0'))
i2c=text('/aliases','microduck-sensors');ck('I2C8 actual MMIO',nums(i2c,'reg')[1]==0x2acb0000)
ck('I2C8 enabled100k',text(i2c,'status')=='okay' and nums(i2c,'clock-frequency')==[100000])
ck('I2C8 M1 mux',nums(i2c,'pinctrl-0')==nums(sym('i2c8m1_xfer'),'phandle'))
pins=nums(sym('i2c8m1_xfer'),'rockchip,pins');ck('C6C7 function10',pins[:3]==[1,22,10] and pins[4:7]==[1,23,10])
ck('no kernel sensor clients',not subprocess.check_output(['fdtget','-l',str(F),i2c],text=True).strip())
for name,offset in [('MICRODUCK_AMP_ENABLE',16),('MICRODUCK_RUN_REQ',17),('MICRODUCK_RUN_OK',20)]:
 names=raw(sym('gpio1'),'gpio-line-names').split(b'\0')[:-1]
 ck(name+'exact offset',len(names)==32 and names[offset]==name.encode() and names.count(name.encode())==1)
ck('RUN pins GPIO mux',nums(sym('md_run_lines'),'rockchip,pins')[0:3]==[1,17,0] and nums(sym('md_run_lines'),'rockchip,pins')[4:7]==[1,20,0])
ck('RUN pin pull down',nums(sym('md_run_lines'),'rockchip,pins')[3]==nums(sym('pcfg_pull_down'),'phandle')[0])
ck('amp positive enable',nums('/microduck-amplifier','sdmode-gpios')==nums(sym('gpio1'),'phandle')+[16,0])
ck('guarded codecs',text('/microduck-amplifier','compatible')=='microduck,max98357a-duplex' and text('/microduck-microphone','compatible')=='microduck,dmic-duplex')
sai=sym('sai1');ck('SAI1 MMIO',nums(sai,'reg')[1]==0x2a610000)
ck('SAI1 duplex DMA',raw(sai,'dma-names')==b'tx\0rx\0')
ck('machine SAI1 phandle',nums('/microduck-audio','sai-controller')==nums(sai,'phandle'))
ck('SAI pinctrl only4actual pins',nums(sai,'pinctrl-0')==sum([nums(sym(n),'phandle') for n in ['sai1m0_lrck','sai1m0_sclk','sai1m0_sdi0','sai1m0_sdo0']],[]))
for name,bank,pin in [('sai1m0_lrck',4,5),('sai1m0_sclk',4,3),('sai1m0_sdi0',4,11),('sai1m0_sdo0',4,7)]:
 ck(name+'physical mux',nums(sym(name),'rockchip,pins')[:3]==[bank,pin,1])
ck('USB1 host to module HUB',text(sym('usb_drd1_dwc3'),'dr_mode')=='host')
ck('USB0 peripheral USB2 only',text(sym('usb_drd0_dwc3'),'dr_mode')=='peripheral' and text(sym('usb_drd0_dwc3'),'phy-names')=='usb2-phy')
ck('module WiFi enable preserved',nums('/wifi-chip-en','gpio')==nums(sym('gpio2'),'phandle')+[18,0])
ck('module5V input',nums('/vcc5v0-sys','regulator-min-microvolt')==[5000000])
for name in ['hdmi','gmac0','i2c6']:ck(name+'unuseddisabled',text(sym(name),'status')=='disabled')
# Ensure test's actual codec callbacks are identical to delivered final sources.
def function(src,name):
 a=src.index('static int '+name+'(');b=src.index('\n}',a)+2;return src[a:b]
test=(D/'trigger_direction_test.c').read_text()
for fn,name in [('microduck-max98357a.c','max98357a_daiops_trigger'),('microduck-dmic.c','dmic_daiops_trigger')]:
 ck(name+'actual source test',function(test,name)==function((D/fn).read_text(),name))
ck('machine params actual source test',function((D/'machine_params_test.c').read_text(),'microduck_hw_params')==function((D/'microduck-audio.c').read_text(),'microduck_hw_params'))
print(json.dumps(dict(checks=checks,passed=len(checks),dtb_sha256=hashlib.sha256(F.read_bytes()).hexdigest(),hardware_tested=False),indent=2))
