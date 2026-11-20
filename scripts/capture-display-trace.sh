#!/bin/sh
# Tablet root helper: observe only; never change brightness or global tracing.
set -eu
umask 077
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.' >&2; exit 1; }
duration=${1:-45}
case "$duration" in ''|*[!0-9]*) echo 'Duration must be 1..45 seconds.' >&2; exit 2 ;; esac
[ "$duration" -ge 1 ] && [ "$duration" -le 45 ] || exit 2
[ "$#" -le 1 ] || exit 2
[ "$(stat -f -c %T /run)" = tmpfs ] || { echo '/run must be tmpfs.' >&2; exit 1; }

tracefs=
for candidate in /sys/kernel/tracing /sys/kernel/debug/tracing; do
    if [ -d "$candidate/events" ] && [ -d "$candidate/instances" ]; then
        tracefs=$candidate
        break
    fi
done
[ -n "$tracefs" ] || { echo 'Mounted tracefs with instances required.' >&2; exit 1; }
instance=$tracefs/instances/j706f-brightness
[ ! -e "$instance" ] || { echo 'Trace instance already exists; refusing to alter it.' >&2; exit 1; }
output=$(mktemp -d /run/j706f-brightness.XXXXXXXX)
mkdir "$output/formats" "$output/stats"
owned=0
reason=setup-failed
error_event=
error_trigger=
finish() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$owned" -eq 1 ]; then
        # Every tracing mutation below addresses our own instance only.
        printf '0\n' >"$instance/tracing_on" || status=1
        cat "$instance/trace" >"$output/trace.txt" || status=1
        for stats in "$instance"/per_cpu/cpu*/stats; do
            [ -f "$stats" ] || continue
            cpu=${stats%/stats}; cpu=${cpu##*/}
            cat "$stats" >"$output/stats/$cpu.txt" || status=1
        done
        [ -z "$error_event" ] || cat "$error_event/trigger" >"$output/trigger-final.txt" || status=1
        printf '0\n' >"$instance/events/enable" || status=1
        if [ -n "$error_trigger" ]; then
            printf '!%s\n' "$error_trigger" >"$error_event/trigger" || status=1
        fi
        rmdir "$instance" || status=1
    fi
    printf 'reason=%s\nexit=%s\n' "$reason" "$status" >"$output/result.txt"
    printf 'Display trace evidence: %s\n' "$output"
    exit "$status"
}
trap finish EXIT
trap 'reason=interrupted; exit 129' HUP
trap 'reason=interrupted; exit 130' INT
trap 'reason=interrupted; exit 143' TERM
mkdir "$instance"
owned=1
printf '0\n' >"$instance/tracing_on"
printf 'nop\n' >"$instance/current_tracer"
printf '1024\n' >"$instance/buffer_size_kb"
printf 'mono\n' >"$instance/trace_clock"
grep -q '\[mono\]' "$instance/trace_clock"

# Event names are pinned to the diagnostic kernel; absence is a hard stop.
dsi_events='drm_msm_dsi/msm_dsi_command drm_msm_dsi/msm_dsi_state drm_msm_dsi/msm_dsi_error'
dpu_events='dpu/dpu_enc_prepare_kickoff dpu/dpu_enc_kickoff dpu/dpu_enc_trigger_start dpu/dpu_enc_phys_cmd_pp_tx_done dpu/dpu_enc_frame_done_cb dpu/dpu_enc_frame_done_timeout'
clk_events='clk/clk_prepare clk/clk_unprepare clk/clk_enable clk/clk_disable clk/clk_set_rate clk/clk_set_parent'
rpm_events='rpm/rpm_resume rpm/rpm_suspend rpm/rpm_usage rpm/rpm_status rpm/rpm_return_int'
events="$dsi_events $dpu_events $clk_events $rpm_events"
for event in $events; do
    [ -f "$instance/events/$event/enable" ] && [ -f "$instance/events/$event/format" ] || {
        echo "Required event missing: $event" >&2; exit 1;
    }
    label=$(printf '%s' "$event" | tr / _)
    cat "$instance/events/$event/format" >"$output/formats/$label.txt"
done
name_filter='name ~ "*mdss*" || name ~ "*dsi*" || name ~ "*ae94000*" || name ~ "*ae96000*"'
for event in $clk_events $rpm_events; do
    printf '%s\n' "$name_filter" >"$instance/events/$event/filter"
    label=$(printf '%s' "$event" | tr / _)
    cat "$instance/events/$event/filter" >"$output/formats/$label-filter.txt"
done
error_event=$instance/events/drm_msm_dsi/msm_dsi_error
# A FIFO snapshot can contain ordinary EMPTY bits; only actual timeout stops us.
error_trigger='traceoff:1 if timeout != 0'
printf '%s\n' "$error_trigger" >"$error_event/trigger"
grep -q 'traceoff' "$error_event/trigger"
cat "$error_event/trigger" >"$output/trigger-start.txt"
for event in $events; do
    printf '1\n' >"$instance/events/$event/enable"
done
{
    printf 'duration_seconds=%s\ninstance=%s\nper_cpu_buffer_kib=1024\n' "$duration" "$instance"
    uname -a
    cat /proc/uptime
    cat "$instance/trace_clock" "$instance/buffer_size_kb"
} >"$output/metadata.txt"
if [ -r /sys/kernel/debug/clk/clk_summary ]; then
    cat /sys/kernel/debug/clk/clk_summary >"$output/clk-summary-before.txt"
fi
printf '1\n' >"$instance/tracing_on"
printf 'J706F display capture started; no brightness change; evidence %s\n' "$output"
elapsed=0
reason=duration-limit
while [ "$elapsed" -lt "$duration" ]; do
    if [ "$(cat "$instance/tracing_on")" = 0 ]; then
        reason=first-dsi-error
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
if [ "$(cat "$instance/tracing_on")" = 0 ]; then
    reason=first-dsi-timeout
fi
printf '0\n' >"$instance/tracing_on"
if [ -r /sys/kernel/debug/clk/clk_summary ]; then
    cat /sys/kernel/debug/clk/clk_summary >"$output/clk-summary-after.txt"
fi
