/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "../../kernel/drivers/power/supply/qcom_smbx_j706f.h"

int main(void)
{
	int temp, valid, fast;
	struct j706f_charge_limit limit;

	/* Check every deci-degree, both hysteresis states, and sensor failure. */
	for (temp = -400; temp <= 1250; temp++) {
		for (valid = 0; valid <= 1; valid++) {
			for (fast = 0; fast <= 1; fast++) {
				limit = j706f_charge_limit(temp, valid, fast);
				assert(limit.current_ua >= 0 && limit.current_ua <= 1950000);
				if (!valid || temp <= 0 || temp >= 500)
					assert(limit.current_ua == 0);
				if (temp < 150 || temp > 400)
					assert(limit.current_ua <= 500000);
				if (limit.current_ua > 500000)
					assert(limit.voltage_uv == 4400000);
				else
					assert(limit.voltage_uv == 4200000);
			}
		}
	}
	assert(j706f_charge_limit(260, 1, 0).current_ua == 1950000);
	assert(j706f_charge_limit(169, 1, 0).current_ua == 500000);
	assert(j706f_charge_limit(170, 1, 0).current_ua == 1950000);
	assert(j706f_charge_limit(150, 1, 1).current_ua == 1950000);
	assert(j706f_charge_limit(149, 1, 1).current_ua == 500000);
	assert(j706f_charge_limit(381, 1, 0).current_ua == 500000);
	assert(j706f_charge_limit(400, 1, 1).current_ua == 1950000);
	assert(j706f_charge_limit(401, 1, 1).current_ua == 500000);
	puts("Charge-policy sensor failure, cutoffs and hysteresis checks passed");
	return 0;
}
