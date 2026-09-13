#include <assert.h>
#include <errno.h>
#include <stdio.h>
#define SNDRV_PCM_FORMAT_S32_LE 10
#define SND_SOC_CLOCK_OUT 1
struct snd_soc_dai { int placeholder; };
struct snd_soc_pcm_runtime { struct snd_soc_dai cpu; };
struct snd_pcm_substream { struct snd_soc_pcm_runtime *rtd; };
struct snd_pcm_hw_params { int rate, channels, format; };
static int syscalls, slotcalls, sys_error;
#define snd_soc_substream_to_rtd(s) ((s)->rtd)
#define snd_soc_rtd_to_cpu(r,n) (&(r)->cpu)
#define params_rate(p) ((p)->rate)
#define params_channels(p) ((p)->channels)
#define params_format(p) ((p)->format)
static int snd_soc_dai_set_sysclk(struct snd_soc_dai *d,int id,unsigned int hz,int dir) {
 (void)d; assert(id==0 && hz==12288000 && dir==SND_SOC_CLOCK_OUT); ++syscalls; return sys_error;
}
static int snd_soc_dai_set_tdm_slot(struct snd_soc_dai *d,unsigned int tx,unsigned int rx,int slots,int width) {
 (void)d; assert(tx==3 && rx==3 && slots==2 && width==32); ++slotcalls;return 0;
}
static int microduck_hw_params(struct snd_pcm_substream *s, struct snd_pcm_hw_params *params)
{
 struct snd_soc_pcm_runtime *rtd = snd_soc_substream_to_rtd(s);
 struct snd_soc_dai *cpu = snd_soc_rtd_to_cpu(rtd, 0);
 int ret;
 if (params_rate(params) != 48000 || params_channels(params) != 2 || params_format(params) != SNDRV_PCM_FORMAT_S32_LE) return -EINVAL;
 /* Internal MCLK is 256fs; no external MCLK pin is connected. */
 ret = snd_soc_dai_set_sysclk(cpu, 0, 48000 * 256, SND_SOC_CLOCK_OUT);
 if (ret < 0) return ret;
 /* rk2410 rockchip_sai has set_tdm_slot, no set_bclk_ratio callback.
  * Fixed 2 channels + one lane makes 2 x 32 = 64fs in its hw_params. */
 return snd_soc_dai_set_tdm_slot(cpu, 0x3, 0x3, 2, 32);
}
int main(void) {
 struct snd_soc_pcm_runtime rtd={0}; struct snd_pcm_substream s={&rtd};
 struct snd_pcm_hw_params p={48000,2,SNDRV_PCM_FORMAT_S32_LE};
 assert(microduck_hw_params(&s,&p)==0);assert(syscalls==1 && slotcalls==1);
 p.rate=16000;assert(microduck_hw_params(&s,&p)==-EINVAL);p.rate=48000;
 p.channels=1;assert(microduck_hw_params(&s,&p)==-EINVAL);p.channels=2;
 p.format=2;assert(microduck_hw_params(&s,&p)==-EINVAL);p.format=SNDRV_PCM_FORMAT_S32_LE;
 assert(syscalls==1 && slotcalls==1);
 sys_error=-EIO;assert(microduck_hw_params(&s,&p)==-EIO);assert(slotcalls==1);
 puts("PASS: actual machine hw_params requires48k/S32/2ch, requests12.288MHz and2x32slots supported by pinned SAI, rejects invalid audio before clocks, propagatesclockfailure");
}
