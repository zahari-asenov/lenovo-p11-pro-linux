// SPDX-License-Identifier: GPL-2.0-only
/* GT738x/Phoenix bring-up, protocol from Lenovo's Goodix vendor driver.
 * Uses resident firmware; never downloads firmware or writes configuration.
 * Pen reports are acknowledged but not exposed in this initial driver.
 */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/input/mt.h>
#include <linux/input/touchscreen.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/regmap.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>

/* Live firmware places the event byte before stock source's 0x824e constant.
 * See tests/touch-register-offset.txt and raw-touch-packets.txt. */
#define GT_COORD 0x824d
struct gt738x {
 struct device *dev;
 struct regmap *map;
 struct input_dev *input;
 struct touchscreen_properties prop;
};
static irqreturn_t gt738x_irq(int irq, void *data)
{
 struct gt738x *ts = data;
 u8 buf[88], ack[2] = {0}, sum = 0;
 unsigned int n, len, i;
 int ret, slot;
 /* Vendor pre-read length includes one full pen record. */
 ret = regmap_raw_read(ts->map, GT_COORD, buf, 16);
 if (ret) {
  dev_err_ratelimited(ts->dev, "event read: %d\n", ret);
  return IRQ_HANDLED;
 }
 if (!(buf[0] & 0x80)) goto ack;
 n = buf[1] & 0x0f;
 if (n > 10) goto ack;
 len = 4 + 8 * max(n, 1U) + ((buf[1] & 0x20) ? 4 : 0);
 if (len > 16) {
  ret = regmap_raw_read(ts->map, GT_COORD + 16, buf + 16, len - 16);
  if (ret) goto ack;
 }
 for (i = 1; i < len; i++) sum += buf[i];
 if (n && sum) {
  dev_warn_ratelimited(ts->dev, "event checksum failed len=%u sum=%02x data=%*ph\n", len, sum, 16, buf);
  goto ack;
 }
 /* Pen uses a different record layout; release fingers on pen-only frames. */
 if (buf[1] & 0x20) n = 0;
 for (i = 0; i < n; i++) {
  u8 *p = buf + 2 + i * 8;
  unsigned int x = get_unaligned_le16(p + 1);
  unsigned int y = get_unaligned_le16(p + 3);
  unsigned int w = get_unaligned_le16(p + 5);
  if (x > ts->prop.max_x || y > ts->prop.max_y || !w) continue;
  slot = input_mt_get_slot_by_key(ts->input, p[0]);
  if (slot < 0) continue;
  input_mt_slot(ts->input, slot);
  input_mt_report_slot_state(ts->input, MT_TOOL_FINGER, true);
  touchscreen_report_pos(ts->input, &ts->prop, x, y, true);
  input_report_abs(ts->input, ABS_MT_TOUCH_MAJOR, w);
 }
 input_mt_sync_frame(ts->input);
 input_sync(ts->input);
ack:
 ret = regmap_raw_write(ts->map, GT_COORD, ack, sizeof(ack));
 if (ret) dev_err_ratelimited(ts->dev, "event acknowledge: %d\n", ret);
 return IRQ_HANDLED;
}
static const struct regmap_config gt738x_regmap = {
 .reg_bits = 16, .val_bits = 8, .max_raw_read = 256, .max_raw_write = 256,
};
static int gt738x_probe(struct i2c_client *client)
{
 struct device *dev = &client->dev;
 struct gpio_desc *reset, *enable;
 struct gt738x *ts;
 u8 version[16], esd = 0xaa;
 int ret;
 ts = devm_kzalloc(dev, sizeof(*ts), GFP_KERNEL);
 if (!ts) return -ENOMEM;
 ts->dev = dev;
 ts->map = devm_regmap_init_i2c(client, &gt738x_regmap);
 if (IS_ERR(ts->map)) return PTR_ERR(ts->map);
 reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
 if (IS_ERR(reset)) return dev_err_probe(dev, PTR_ERR(reset), "reset GPIO\n");
 enable = devm_gpiod_get(dev, "avdd-enable", GPIOD_OUT_HIGH);
 if (IS_ERR(enable)) return dev_err_probe(dev, PTR_ERR(enable), "power GPIO\n");
 ret = devm_regulator_get_enable(dev, "avdd");
 if (ret) return dev_err_probe(dev, ret, "AVDD\n");
 msleep(10);
 gpiod_set_value_cansleep(reset, 0);
 msleep(440);
 ret = regmap_raw_read(ts->map, 0x8240, version, sizeof(version));
 if (ret) return dev_err_probe(dev, ret, "version read\n");
 dev_info(dev, "GT738x resident version: %*ph\n", (int)sizeof(version), version);
 /* Vendor reset initializes the static ESD marker. */
 ret = regmap_raw_write(ts->map, 0x8043, &esd, 1);
 if (ret) return dev_err_probe(dev, ret, "ESD marker\n");
 ts->input = devm_input_allocate_device(dev);
 if (!ts->input) return -ENOMEM;
 ts->input->name = "Goodix GT738x Touchscreen";
 ts->input->id.bustype = BUS_I2C;
 input_set_abs_params(ts->input, ABS_MT_POSITION_X, 0, 2559, 0, 0);
 input_set_abs_params(ts->input, ABS_MT_POSITION_Y, 0, 1599, 0, 0);
 input_set_abs_params(ts->input, ABS_MT_TOUCH_MAJOR, 0, 2368, 0, 0);
 touchscreen_parse_properties(ts->input, true, &ts->prop);
 ret = input_mt_init_slots(ts->input, 10, INPUT_MT_DIRECT | INPUT_MT_DROP_UNUSED);
 if (ret) return ret;
 ret = input_register_device(ts->input);
 if (ret) return ret;
 return devm_request_threaded_irq(dev, client->irq, NULL, gt738x_irq,
                                 IRQF_ONESHOT, "goodix-gt738x", ts);
}
static const struct of_device_id gt738x_match[] = {
 { .compatible = "goodix,gt738x" }, { }
};
MODULE_DEVICE_TABLE(of, gt738x_match);
static struct i2c_driver gt738x_driver = {
 .driver = { .name = "goodix-gt738x", .of_match_table = gt738x_match },
 .probe = gt738x_probe,
};
module_i2c_driver(gt738x_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Goodix GT738x resident-firmware touchscreen bring-up");
