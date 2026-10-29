/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _QCOM_SMBX_J706F_H
#define _QCOM_SMBX_J706F_H

struct j706f_charge_limit {
	int current_ua;
	int voltage_uv;
};

/* Conservative subset of the Android temperature policy; temp is deci-Celsius. */
static inline struct j706f_charge_limit
j706f_charge_limit(int temp, int valid, int was_fast)
{
	struct j706f_charge_limit limit = { 0, 4200000 };

	if (!valid || temp <= 0 || temp >= 500)
		return limit;

	limit.current_ua = 500000;
	if ((temp >= 170 && temp <= 380) ||
	    (was_fast && temp >= 150 && temp <= 400)) {
		limit.current_ua = 1950000;
		limit.voltage_uv = 4400000;
	}
	return limit;
}
#endif
