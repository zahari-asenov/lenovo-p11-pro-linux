/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __J706F_BRIGHTNESS_H__
#define __J706F_BRIGHTNESS_H__

#define J706F_BRIGHTNESS_MAX 2047U
#define J706F_BRIGHTNESS_FLOOR 205U

/* Logical slider scale; blanking remains independent of the visible floor. */
static inline unsigned int j706f_brightness_level(unsigned int requested,
						  int blank)
{
	if (blank)
		return 0;
	if (requested > J706F_BRIGHTNESS_MAX)
		requested = J706F_BRIGHTNESS_MAX;

	return J706F_BRIGHTNESS_FLOOR +
		(requested * (J706F_BRIGHTNESS_MAX - J706F_BRIGHTNESS_FLOOR) +
		 J706F_BRIGHTNESS_MAX / 2) / J706F_BRIGHTNESS_MAX;
}

#endif
