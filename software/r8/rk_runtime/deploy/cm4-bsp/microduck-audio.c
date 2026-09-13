// SPDX-License-Identifier: GPL-2.0-only
/* One CPU DAI, two codecs, fixed shared 48k/64fs clock. No simple-card multi-codec assumption. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>
#ifndef snd_soc_substream_to_rtd
#define snd_soc_substream_to_rtd asoc_substream_to_rtd
#endif
#ifndef snd_soc_rtd_to_cpu
#define snd_soc_rtd_to_cpu asoc_rtd_to_cpu
#endif
struct microduck_audio {
 struct snd_soc_card card;
 struct snd_soc_dai_link link;
 struct snd_soc_dai_link_component cpu, platform, codecs[2];
};
static void microduck_put_node(void *data) { of_node_put(data); }
static int microduck_startup(struct snd_pcm_substream *s)
{
 int ret;
 ret = snd_pcm_hw_constraint_single(s->runtime, SNDRV_PCM_HW_PARAM_RATE, 48000);
 if (ret < 0) return ret;
 ret = snd_pcm_hw_constraint_single(s->runtime, SNDRV_PCM_HW_PARAM_CHANNELS, 2);
 if (ret < 0) return ret;
 return snd_pcm_hw_constraint_mask64(s->runtime, SNDRV_PCM_HW_PARAM_FORMAT, SNDRV_PCM_FMTBIT_S32_LE);
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
static const struct snd_soc_ops microduck_ops = { .startup=microduck_startup, .hw_params=microduck_hw_params };
static int microduck_probe(struct platform_device *pdev)
{
 struct device *dev=&pdev->dev;
 struct microduck_audio *a;
 struct device_node *cpu, *codec;
 int ret, i;
 a=devm_kzalloc(dev,sizeof(*a),GFP_KERNEL);
 if (!a) return -ENOMEM;
 cpu=of_parse_phandle(dev->of_node,"sai-controller",0);
 if (!cpu) return dev_err_probe(dev,-EINVAL,"Missing sai-controller\n");
 ret=devm_add_action_or_reset(dev,microduck_put_node,cpu);
 if (ret) return ret;
 a->cpu.of_node=cpu; a->platform.of_node=cpu;
 for(i=0;i<2;i++) {
  codec=of_parse_phandle(dev->of_node,"audio-codecs",i);
  if (!codec) return dev_err_probe(dev,-EINVAL,"Missing audio-codecs[%d]\n",i);
  ret=devm_add_action_or_reset(dev,microduck_put_node,codec);
  if (ret) return ret;
  a->codecs[i].of_node=codec;
 }
 a->codecs[0].dai_name="HiFi";
 a->codecs[1].dai_name="dmic-hifi";
 a->link.name="Microduck SAI1 Duplex";a->link.stream_name="Microduck Audio";
 a->link.cpus=&a->cpu;a->link.num_cpus=1;
 a->link.platforms=&a->platform;a->link.num_platforms=1;
 a->link.codecs=a->codecs;a->link.num_codecs=2;
 a->link.dai_fmt=SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBS_CFS;
 a->link.symmetric_rate=1;a->link.symmetric_channels=1;a->link.symmetric_sample_bits=1;
 a->link.ops=&microduck_ops;
 a->card.name="MicroduckAudio";a->card.driver_name="MicroduckAudio";
 a->card.owner=THIS_MODULE;a->card.dev=dev;a->card.dai_link=&a->link;a->card.num_links=1;
 platform_set_drvdata(pdev,a);
 return devm_snd_soc_register_card(dev,&a->card);
}
static const struct of_device_id microduck_of_match[] = { { .compatible="microduck,rk3576-sai-audio" }, {} };
MODULE_DEVICE_TABLE(of,microduck_of_match);
static struct platform_driver microduck_driver = { .probe=microduck_probe, .driver={ .name="microduck-audio", .of_match_table=microduck_of_match } };
module_platform_driver(microduck_driver);
MODULE_AUTHOR("Microduck R8 engineering");
MODULE_DESCRIPTION("Fixed 48k full duplex RK3576 SAI1 MAX98357A and T5848 machine driver");
MODULE_LICENSE("GPL");
