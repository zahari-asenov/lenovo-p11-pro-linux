#!/bin/sh
# Protected J706F playback setup, matching stock Android's speaker mixer path.
set -eu
for attempt in $(seq 1 30); do
    test ! -e /dev/snd/controlC0 || break
    sleep 1
done
for number in 1 2 3 4; do
    amixer -c 0 sset "SPK$number DSP1 Firmware" Protection
    amixer -c 0 sset "SPK$number PCM Source" DSP
    amixer -c 0 sset "SPK$number Analog PCM" 17
    amixer -c 0 sset "SPK$number Digital PCM" 817
    amixer -c 0 sset "SPK$number DSP1 Preload" on
done
amixer -c 0 sset 'TERT_MI2S_RX Audio Mixer MultiMedia1' on
