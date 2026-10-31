// SPDX-License-Identifier: GPL-2.0-only
/* Lenovo TB-J706F: Q6 tertiary MI2S and four CS35L41 amplifiers. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <sound/soc.h>
#include <sound/pcm_params.h>
#include <sound/cs35l41.h>
#include <dt-bindings/sound/qcom,q6afe.h>
#include "common.h"
#include "qdsp6/q6afe.h"
#define J706F_BCLK 1536000
static int j706f_startup(struct snd_pcm_substream *s)
{
 struct snd_soc_pcm_runtime *rtd=snd_soc_substream_to_rtd(s);
 struct snd_soc_dai *cpu=snd_soc_rtd_to_cpu(rtd,0), *codec;
 int ret,i;
 ret=snd_soc_dai_set_fmt(cpu,SND_SOC_DAIFMT_BP_FP|SND_SOC_DAIFMT_I2S|SND_SOC_DAIFMT_NB_NF);
 if(ret<0)return ret;
 ret=snd_soc_dai_set_sysclk(cpu,Q6AFE_LPASS_CLK_ID_TER_MI2S_IBIT,J706F_BCLK,SNDRV_PCM_STREAM_PLAYBACK);
 if(ret<0)return ret;
 for_each_rtd_codec_dais(rtd,i,codec){
  /* Match the monitor input expected by Lenovo's protection firmware. */
  ret=snd_soc_component_write(codec->component,CS35L41_DSP1_RX6_SRC,
                            CS35L41_INPUT_SRC_CLASSH);
  if(ret<0)return ret;
  ret=snd_soc_dai_set_fmt(codec,SND_SOC_DAIFMT_BC_FC|SND_SOC_DAIFMT_I2S|SND_SOC_DAIFMT_NB_NF);
  if(ret<0)return ret;
  ret=snd_soc_component_set_sysclk(codec->component,CS35L41_CLKID_SCLK,0,J706F_BCLK,SND_SOC_CLOCK_IN);
  if(ret<0)return ret;
  ret=snd_soc_dai_set_sysclk(codec,CS35L41_CLKID_SCLK,J706F_BCLK,SND_SOC_CLOCK_IN);
  if(ret<0)return ret;
  ret=snd_soc_dai_set_tdm_slot(codec,0,3,2,16);
  if(ret<0 && ret!=-ENOTSUPP)return ret;
 }
 return 0;
}
static void j706f_shutdown(struct snd_pcm_substream *s)
{
 struct snd_soc_pcm_runtime *rtd=snd_soc_substream_to_rtd(s);
 snd_soc_dai_set_sysclk(snd_soc_rtd_to_cpu(rtd,0),Q6AFE_LPASS_CLK_ID_TER_MI2S_IBIT,0,SNDRV_PCM_STREAM_PLAYBACK);
}
static int j706f_fixup(struct snd_soc_pcm_runtime *rtd,struct snd_pcm_hw_params *p)
{
 struct snd_interval *rate=hw_param_interval(p,SNDRV_PCM_HW_PARAM_RATE);
 struct snd_interval *ch=hw_param_interval(p,SNDRV_PCM_HW_PARAM_CHANNELS);
 rate->min=rate->max=48000;ch->min=ch->max=2;
 /* Stock Android selects stereo 16-bit audio at 48 kHz. */
 snd_mask_none(hw_param_mask(p,SNDRV_PCM_HW_PARAM_FORMAT));
 snd_mask_set_format(hw_param_mask(p,SNDRV_PCM_HW_PARAM_FORMAT),SNDRV_PCM_FORMAT_S16_LE);
 return 0;
}
static const struct snd_soc_ops j706f_ops={.startup=j706f_startup,.shutdown=j706f_shutdown};
static int j706f_probe(struct platform_device *pdev)
{
 struct snd_soc_card *card;int ret,i;
 card=devm_kzalloc(&pdev->dev,sizeof(*card),GFP_KERNEL);if(!card)return -ENOMEM;
 card->dev=&pdev->dev;card->owner=THIS_MODULE;
 ret=qcom_snd_parse_of(card);if(ret)return ret;
 for(i=0;i<card->num_links;i++)if(card->dai_link[i].no_pcm){
  card->dai_link[i].ops=&j706f_ops;
  card->dai_link[i].be_hw_params_fixup=j706f_fixup;
 }
 return devm_snd_soc_register_card(&pdev->dev,card);
}
static const struct of_device_id j706f_match[]={{.compatible="lenovo,j706f-audio"},{}};
MODULE_DEVICE_TABLE(of,j706f_match);
static struct platform_driver j706f_driver={.probe=j706f_probe,.driver={.name="j706f-audio",.of_match_table=j706f_match}};
module_platform_driver(j706f_driver);
MODULE_DESCRIPTION("Lenovo TB-J706F speaker audio");
MODULE_LICENSE("GPL");
