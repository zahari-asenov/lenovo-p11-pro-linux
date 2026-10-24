// SPDX-License-Identifier: GPL-2.0-only
/*
 * TB-J706F RM692E6 command-mode variant, using exact stock firmware packets.
 * Based on panel-raydium-rm69380.c by David Wronek.
 * Copyright (c) 2024 David Wronek <david@mainlining.org>
 */

#include <linux/backlight.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_device.h>
#include <linux/of_graph.h>
#include <linux/regulator/consumer.h>

#include <video/mipi_display.h>

#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>
#include <drm/drm_probe_helper.h>

#include "j706f-brightness.h"

struct j706f_panel {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi[2];
	struct regulator_bulk_data supplies[2];
	struct gpio_desc *reset_gpio;
	struct mutex lock;
	bool initialized;
	u16 applied_brightness;
};

static inline
struct j706f_panel *to_j706f_panel(struct drm_panel *panel)
{
	return container_of(panel, struct j706f_panel, panel);
}

/* MSM synchronized bonded writes are triggered through DSI1. */
static struct mipi_dsi_device *j706f_command_dsi(struct j706f_panel *ctx)
{
	return ctx->dsi[1] ? ctx->dsi[1] : ctx->dsi[0];
}

static void j706f_reset(struct j706f_panel *ctx)
{
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	usleep_range(15000, 16000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	usleep_range(10000, 11000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	msleep(10);
}

/* Preserve stock packet type, payload, channel and per-command delay. */
static int j706f_packet(struct mipi_dsi_device *dsi, u8 type,
		       const u8 *data, size_t len, unsigned int delay_ms, bool lpm)
{
	struct mipi_dsi_msg msg = {
		.channel = dsi->channel,
		.type = type,
		.flags = lpm ? MIPI_DSI_MSG_USE_LPM : 0,
		.tx_buf = data,
		.tx_len = len,
	};
	ssize_t ret;

	if (!dsi->host->ops || !dsi->host->ops->transfer)
		return -ENOSYS;
	ret = dsi->host->ops->transfer(dsi->host, &msg);
	if (ret < 0)
		return ret;
	/* MSM returns aligned packet bytes, rather than payload bytes. */
	dev_dbg(&dsi->dev, "J706F_PANEL_PACKET type=%02x cmd=%02x payload=%zu transferred=%zd\n",
		type, data[0], len, ret);
	if (delay_ms)
		msleep(delay_ms);
	return 0;
}

static int j706f_on(struct j706f_panel *ctx)
{
	int ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xfe, 0xa1 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xb1, 0x04 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xcd, 0x6b }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xce, 0xbb }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xfe, 0xd1 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xb4, 0x01 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xfe, 0x00 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0x53, 0x28 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0xc2, 0x08 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0x35, 0x00 }, 2, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x39,
			    (const u8[]) { 0x51, 0x07, 0xff }, 3, 0, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x05,
			    (const u8[]) { 0x11, 0x00 }, 2, 20, true);
	if (ret)
		return ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x05,
			    (const u8[]) { 0x29, 0x00 }, 2, 100, true);
	if (ret)
		return ret;
	return 0;
}

static void j706f_off(struct j706f_panel *ctx)
{
	int ret;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x05,
			    (const u8[]) { 0x28, 0x00 }, 2, 120, false);
	if (ret)
		return;
	ret = j706f_packet(j706f_command_dsi(ctx), 0x05,
			    (const u8[]) { 0x10, 0x00 }, 2, 100, false);
	if (ret)
		return;
}

static int j706f_prepare(struct drm_panel *panel)
{
	struct j706f_panel *ctx = to_j706f_panel(panel);
	int ret;

	mutex_lock(&ctx->lock);

	ret = regulator_enable(ctx->supplies[0].consumer);
	if (ret < 0)
		goto unlock;
	msleep(2);
	ret = regulator_enable(ctx->supplies[1].consumer);
	if (ret < 0) {
		regulator_disable(ctx->supplies[0].consumer);
		goto unlock;
	}

	dev_info(panel->dev, "J706F_PANEL rails enabled; resetting\n");
	j706f_reset(ctx);

	ret = j706f_on(ctx);
	dev_info(panel->dev, "J706F_PANEL startup result=%d\n", ret);
	if (ret < 0) {
		gpiod_set_value_cansleep(ctx->reset_gpio, 1);
		regulator_bulk_disable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	} else {
		ctx->applied_brightness = 2047;
		ctx->initialized = true;
	}

unlock:
	mutex_unlock(&ctx->lock);
	return ret;
}

static int j706f_unprepare(struct drm_panel *panel)
{
	struct j706f_panel *ctx = to_j706f_panel(panel);

	mutex_lock(&ctx->lock);
	ctx->initialized = false;
	j706f_off(ctx);

	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	regulator_bulk_disable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	ctx->applied_brightness = 0;
	mutex_unlock(&ctx->lock);

	return 0;
}

static const struct drm_display_mode j706f_mode = {
	.clock = (2560 + 64 + 24 + 76) * (1600 + 20 + 4 + 8) * 60 / 1000,
	.hdisplay = 2560,
	.hsync_start = 2560 + 64,
	.hsync_end = 2560 + 64 + 24,
	.htotal = 2560 + 64 + 24 + 76,
	.vdisplay = 1600,
	.vsync_start = 1600 + 20,
	.vsync_end = 1600 + 20 + 4,
	.vtotal = 1600 + 20 + 4 + 8,
	.width_mm = 248,
	.height_mm = 155,
	.type = DRM_MODE_TYPE_DRIVER,
};

static int j706f_get_modes(struct drm_panel *panel,
					struct drm_connector *connector)
{
	return drm_connector_helper_get_modes_fixed(connector, &j706f_mode);
}

static const struct drm_panel_funcs j706f_panel_funcs = {
	.prepare = j706f_prepare,
	.unprepare = j706f_unprepare,
	.get_modes = j706f_get_modes,
};

static int j706f_bl_update_status(struct backlight_device *bl)
{
	struct j706f_panel *ctx = bl_get_data(bl);
	u16 requested = backlight_get_brightness(bl);
	u16 brightness;
	u8 payload[3] = { MIPI_DCS_SET_DISPLAY_BRIGHTNESS };
	int ret = 0;

	/* Keep the usable slider range at 10..100%; blanking still sends zero. */
	brightness = j706f_brightness_level(requested, backlight_is_blank(bl));
	payload[1] = brightness >> 8;
	payload[2] = brightness & 0xff;

	mutex_lock(&ctx->lock);
	/* The backlight core retains the request and applies it on enable. */
	if (!ctx->initialized)
		goto unlock;

	/* Stock runtime backlight writes use HS; startup commands remain LP.
	 * Set the message mode explicitly without changing shared mode_flags.
	 */
	ret = j706f_packet(j706f_command_dsi(ctx), MIPI_DSI_DCS_LONG_WRITE,
			   payload, sizeof(payload), 0, false);
	if (!ret)
		ctx->applied_brightness = requested;

unlock:
	mutex_unlock(&ctx->lock);
	return ret;
}

static int j706f_bl_get_brightness(struct backlight_device *bl)
{
	struct j706f_panel *ctx = bl_get_data(bl);
	int brightness;

	/* Keep actual_brightness in the same logical scale as brightness. */
	mutex_lock(&ctx->lock);
	brightness = ctx->applied_brightness;
	mutex_unlock(&ctx->lock);
	return brightness;
}

static const struct backlight_ops j706f_bl_ops = {
	.update_status = j706f_bl_update_status,
	.get_brightness = j706f_bl_get_brightness,
};

static struct backlight_device *
j706f_create_backlight(struct j706f_panel *ctx)
{
	struct device *dev = &ctx->dsi[0]->dev;
	const struct backlight_properties props = {
		.type = BACKLIGHT_RAW,
		.brightness = 340, /* Maps to the previous panel default of 511. */
		.max_brightness = J706F_BRIGHTNESS_MAX,
	};

	return devm_backlight_device_register(dev, dev_name(dev), dev, ctx,
					      &j706f_bl_ops, &props);
}

static int j706f_probe(struct mipi_dsi_device *dsi)
{
	struct mipi_dsi_host *dsi_sec_host;
	struct j706f_panel *ctx;
	struct device *dev = &dsi->dev;
	struct device_node *dsi_sec;
	int ret, i;

	ctx = devm_drm_panel_alloc(dev, struct j706f_panel, panel,
				   &j706f_panel_funcs,
				   DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ctx->supplies[0].supply = "vddio";
	ctx->supplies[1].supply = "avdd";
	ret = devm_regulator_bulk_get(dev, ARRAY_SIZE(ctx->supplies),
				      ctx->supplies);
	if (ret < 0)
		return dev_err_probe(dev, ret, "Failed to get regulators\n");

	ctx->reset_gpio = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(ctx->reset_gpio))
		return dev_err_probe(dev, PTR_ERR(ctx->reset_gpio),
				     "Failed to get reset-gpios\n");

	dsi_sec = of_graph_get_remote_node(dsi->dev.of_node, 1, -1);

	if (dsi_sec) {
		const struct mipi_dsi_device_info info = { "RM692E6 DSI1", 0,
							   dsi_sec };

		dsi_sec_host = of_find_mipi_dsi_host_by_node(dsi_sec);
		of_node_put(dsi_sec);
		if (!dsi_sec_host)
			return dev_err_probe(dev, -EPROBE_DEFER,
					     "Cannot get secondary DSI host\n");

		ctx->dsi[1] =
			devm_mipi_dsi_device_register_full(dev, dsi_sec_host, &info);
		if (IS_ERR(ctx->dsi[1]))
			return dev_err_probe(dev, PTR_ERR(ctx->dsi[1]),
					     "Cannot get secondary DSI node\n");

		mipi_dsi_set_drvdata(ctx->dsi[1], ctx);
	}

	ctx->dsi[0] = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);
	mutex_init(&ctx->lock);

	ctx->panel.prepare_prev_first = true;

	ctx->panel.backlight = j706f_create_backlight(ctx);
	if (IS_ERR(ctx->panel.backlight))
		return dev_err_probe(dev, PTR_ERR(ctx->panel.backlight),
				     "Failed to create backlight\n");

	drm_panel_add(&ctx->panel);

	for (i = 0; i < ARRAY_SIZE(ctx->dsi); i++) {
		if (!ctx->dsi[i])
			continue;

		dev_dbg(&ctx->dsi[i]->dev, "Binding DSI %d\n", i);

		ctx->dsi[i]->lanes = 4;
		ctx->dsi[i]->format = MIPI_DSI_FMT_RGB888;
		ctx->dsi[i]->mode_flags = MIPI_DSI_MODE_LPM |
					  MIPI_DSI_CLOCK_NON_CONTINUOUS;

		ret = devm_mipi_dsi_attach(dev, ctx->dsi[i]);
		if (ret < 0) {
			drm_panel_remove(&ctx->panel);
			return dev_err_probe(dev, ret,
					     "Failed to attach to DSI%d\n", i);
		}
	}

	return 0;
}

static void j706f_remove(struct mipi_dsi_device *dsi)
{
	struct j706f_panel *ctx = mipi_dsi_get_drvdata(dsi);

	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id j706f_of_match[] = {
	{ .compatible = "lenovo,j706f-edo-rm692e6" },
	{ /* sentinel */ }
};
MODULE_DEVICE_TABLE(of, j706f_of_match);

static struct mipi_dsi_driver j706f_panel_driver = {
	.probe = j706f_probe,
	.remove = j706f_remove,
	.driver = {
		.name = "panel-lenovo-j706f",
		.of_match_table = j706f_of_match,
	},
};
module_mipi_dsi_driver(j706f_panel_driver);

MODULE_AUTHOR("David Wronek <david@mainlining.org>");
MODULE_DESCRIPTION("DRM driver for Raydium RM692E6-equipped DSI panels");
MODULE_LICENSE("GPL");
