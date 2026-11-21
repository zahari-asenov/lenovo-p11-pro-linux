/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include "../../kernel/drivers/gpu/drm/panel/j706f-brightness.h"

int main(void)
{
    unsigned int previous = j706f_brightness_level(0, 0);
    assert(previous == J706F_BRIGHTNESS_FLOOR);
    assert(j706f_brightness_level(J706F_BRIGHTNESS_MAX, 0) == J706F_BRIGHTNESS_MAX);
    assert(j706f_brightness_level(340, 0) == 511);
    assert(j706f_brightness_level(UINT_MAX, 0) == J706F_BRIGHTNESS_MAX);
    for (unsigned int level = 0; level <= J706F_BRIGHTNESS_MAX; ++level) {
        unsigned int applied = j706f_brightness_level(level, 0);
        assert(applied >= J706F_BRIGHTNESS_FLOOR && applied <= J706F_BRIGHTNESS_MAX);
        assert(applied >= previous && applied - previous <= 1);
        assert(j706f_brightness_level(level, 1) == 0);
        previous = applied;
    }
    puts("Brightness endpoints, monotonicity, blanking and input bounds passed");
    return 0;
}
