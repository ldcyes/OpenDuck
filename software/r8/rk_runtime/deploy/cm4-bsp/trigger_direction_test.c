#include <assert.h>
#include <stdio.h>
#define SNDRV_PCM_STREAM_PLAYBACK 0
#define SNDRV_PCM_STREAM_CAPTURE 1
#define SNDRV_PCM_TRIGGER_START 0
#define SNDRV_PCM_TRIGGER_STOP 1
#define SNDRV_PCM_TRIGGER_RESUME 2
#define SNDRV_PCM_TRIGGER_SUSPEND 3
#define SNDRV_PCM_TRIGGER_PAUSE_RELEASE 4
#define SNDRV_PCM_TRIGGER_PAUSE_PUSH 5
struct snd_pcm_substream { int stream; };
struct snd_soc_component { void *data; void *dev; };
struct snd_soc_dai { struct snd_soc_component *component; };
struct gpio_desc { int value; };
struct max98357a_priv { struct gpio_desc *sdmode; unsigned int sdmode_delay; int sdmode_switch; };
struct dmic { struct gpio_desc *gpio_en; int wakeup_delay; int modeswitch_delay; };
static int gpio_calls, delays;
static void *snd_soc_component_get_drvdata(struct snd_soc_component *c) { return c->data; }
static void gpiod_set_value(struct gpio_desc *g,int v) { ++gpio_calls; g->value=v; }
static void mdelay(unsigned int d) { delays+=(int)d; }
#define dev_dbg(...) ((void)0)
static int max98357a_daiops_trigger(struct snd_pcm_substream *substream,
		int cmd, struct snd_soc_dai *dai)
{
	struct snd_soc_component *component = dai->component;
	struct max98357a_priv *max98357a =
		snd_soc_component_get_drvdata(component);

	/* A shared link may call this codec for capture on older BSP ASoC. */
	if (substream->stream != SNDRV_PCM_STREAM_PLAYBACK)
		return 0;

	if (!max98357a->sdmode)
		return 0;

	switch (cmd) {
	case SNDRV_PCM_TRIGGER_START:
	case SNDRV_PCM_TRIGGER_RESUME:
	case SNDRV_PCM_TRIGGER_PAUSE_RELEASE:
		mdelay(max98357a->sdmode_delay);
		if (max98357a->sdmode_switch) {
			gpiod_set_value(max98357a->sdmode, 1);
			dev_dbg(component->dev, "set sdmode to 1");
		}
		break;
	case SNDRV_PCM_TRIGGER_STOP:
	case SNDRV_PCM_TRIGGER_SUSPEND:
	case SNDRV_PCM_TRIGGER_PAUSE_PUSH:
		gpiod_set_value(max98357a->sdmode, 0);
		dev_dbg(component->dev, "set sdmode to 0");
		break;
	}

	return 0;
}

static int dmic_daiops_trigger(struct snd_pcm_substream *substream,
			       int cmd, struct snd_soc_dai *dai)
{
	struct snd_soc_component *component = dai->component;
	struct dmic *dmic = snd_soc_component_get_drvdata(component);

	/* Do not let playback triggers affect the capture endpoint. */
	if (substream->stream != SNDRV_PCM_STREAM_CAPTURE)
		return 0;

	switch (cmd) {
	case SNDRV_PCM_TRIGGER_STOP:
		if (dmic->modeswitch_delay)
			mdelay(dmic->modeswitch_delay);

		break;
	}

	return 0;
}

int main(void) {
 struct gpio_desc gpio={0}; struct max98357a_priv amp={&gpio,5,1};
 struct snd_soc_component comp={&amp,0}; struct snd_soc_dai dai={&comp};
 struct snd_pcm_substream pb={SNDRV_PCM_STREAM_PLAYBACK}, cap={SNDRV_PCM_STREAM_CAPTURE};
 assert(max98357a_daiops_trigger(&pb,SNDRV_PCM_TRIGGER_START,&dai)==0);
 assert(gpio.value==1 && gpio_calls==1 && delays==5);
 for(int cmd=0;cmd<6;cmd++) assert(max98357a_daiops_trigger(&cap,cmd,&dai)==0);
 assert(gpio.value==1 && gpio_calls==1 && delays==5);
 assert(max98357a_daiops_trigger(&pb,SNDRV_PCM_TRIGGER_STOP,&dai)==0);
 assert(gpio.value==0 && gpio_calls==2);
 struct dmic mic={0,10,9}; comp.data=&mic; delays=0;
 for(int cmd=0;cmd<6;cmd++) assert(dmic_daiops_trigger(&pb,cmd,&dai)==0);
 assert(delays==0);
 assert(dmic_daiops_trigger(&cap,SNDRV_PCM_TRIGGER_STOP,&dai)==0);
 assert(delays==9);
 puts("PASS: actual callbacks keep capture STOP from muting playback; all opposite-direction triggers ignored; intended-direction operations retained");
 return 0;
}
