/* SPDX-License-Identifier: GPL-2.0-only */
#undef TRACE_SYSTEM
#define TRACE_SYSTEM drm_msm_dsi

#if !defined(_MSM_DSI_TRACE_H_) || defined(TRACE_HEADER_MULTI_READ)
#define _MSM_DSI_TRACE_H_

#include <drm/drm_mipi_dsi.h>
#include <linux/tracepoint.h>

TRACE_EVENT(msm_dsi_command,
	TP_PROTO(int logical, int physical, const char *phase,
		 const struct mipi_dsi_msg *msg, int result),
	TP_ARGS(logical, physical, phase, msg, result),
	TP_STRUCT__entry(
		__field(int, logical)
		__field(int, physical)
		__string(phase, phase)
		__field(u8, type)
		__field(u16, flags)
		__field(size_t, length)
		__field(int, command)
		__field(int, brightness)
		__field(int, result)
	),
	TP_fast_assign(
		const u8 *payload = msg->tx_buf;

		__entry->logical = logical;
		__entry->physical = physical;
		__assign_str(phase);
		__entry->type = msg->type;
		__entry->flags = msg->flags;
		__entry->length = msg->tx_len;
		__entry->command = payload && msg->tx_len ? payload[0] : -1;
		__entry->brightness = payload && msg->tx_len == 3 &&
			payload[0] == 0x51 ? (payload[1] << 8) | payload[2] : -1;
		__entry->result = result;
	),
	TP_printk("logical=%d physical=%d phase=%s type=%#x flags=%#x len=%zu cmd=%#x brightness=%d result=%d",
		  __entry->logical, __entry->physical, __get_str(phase),
		  __entry->type, __entry->flags, __entry->length,
		  __entry->command, __entry->brightness, __entry->result)
);

TRACE_EVENT(msm_dsi_state,
	TP_PROTO(int physical, const char *phase, u32 ctrl, u32 status,
		 u32 clock, u32 trigger, u32 dma_ctrl, int result),
	TP_ARGS(physical, phase, ctrl, status, clock, trigger, dma_ctrl, result),
	TP_STRUCT__entry(
		__field(int, physical)
		__string(phase, phase)
		__field(u32, ctrl)
		__field(u32, status)
		__field(u32, clock)
		__field(u32, trigger)
		__field(u32, dma_ctrl)
		__field(int, result)
	),
	TP_fast_assign(
		__entry->physical = physical;
		__assign_str(phase);
		__entry->ctrl = ctrl;
		__entry->status = status;
		__entry->clock = clock;
		__entry->trigger = trigger;
		__entry->dma_ctrl = dma_ctrl;
		__entry->result = result;
	),
	TP_printk("physical=%d phase=%s ctrl=%#x status=%#x clock=%#x trigger=%#x dma_ctrl=%#x result=%d",
		  __entry->physical, __get_str(phase), __entry->ctrl,
		  __entry->status, __entry->clock, __entry->trigger,
		  __entry->dma_ctrl, __entry->result)
);

TRACE_EVENT(msm_dsi_error,
	TP_PROTO(int physical, u32 fifo, u32 timeout),
	TP_ARGS(physical, fifo, timeout),
	TP_STRUCT__entry(
		__field(int, physical)
		__field(u32, fifo)
		__field(u32, timeout)
	),
	TP_fast_assign(
		__entry->physical = physical;
		__entry->fifo = fifo;
		__entry->timeout = timeout;
	),
	TP_printk("physical=%d fifo=%#x timeout=%#x", __entry->physical,
		  __entry->fifo, __entry->timeout)
);

#endif /* _MSM_DSI_TRACE_H_ */

#undef TRACE_INCLUDE_PATH
#define TRACE_INCLUDE_PATH .
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_FILE dsi_trace
#include <trace/define_trace.h>
