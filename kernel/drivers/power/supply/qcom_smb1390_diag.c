// SPDX-License-Identifier: GPL-2.0-only
/*
 * Disabled-pump bring-up for Lenovo J706F. Register definitions and IRQ
 * polarity follow Lenovo's downstream SMB1390 and qcom-i2c-pmic drivers.
 * This intentionally provides no charge-pump enable or current-control API.
 */
#include <linux/atomic.h>
#include <linux/i2c.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/regmap.h>
#include <linux/sysfs.h>

#define SMB1390_REVISION		0x0100
#define SMB1390_CSIR		0x09f1
#define SMB1390_STATUS1		0x1006
#define SMB1390_RT_STATUS	0x1010
#define SMB1390_IRQ_TYPE		0x1011
#define SMB1390_IRQ_POL_HIGH	0x1012
#define SMB1390_IRQ_POL_LOW	0x1013
#define SMB1390_IRQ_ACK		0x1014
#define SMB1390_IRQ_ENABLE	0x1015
#define SMB1390_IRQ_DISABLE	0x1016
#define SMB1390_IRQ_LATCHED	0x1018
#define SMB1390_CONTROL		0x1020
#define SMB1390_SWITCHER_ENABLE	BIT(0)
#define SMB1390_SLAVE_ENABLE	BIT(1)
#define SMB1390_NUM_IRQS		8

struct smb1390_diag {
	struct regmap *map;
	struct device *dev;
	atomic_t irq_events;
};

#define SMB1390_IRQ(n) { .mask = BIT(n), .type = { \
	.types_supported = IRQ_TYPE_EDGE_BOTH } }

static const struct regmap_irq smb1390_irqs[] = {
	SMB1390_IRQ(0), SMB1390_IRQ(1), SMB1390_IRQ(2), SMB1390_IRQ(3),
	SMB1390_IRQ(4), SMB1390_IRQ(5), SMB1390_IRQ(6), SMB1390_IRQ(7),
};

static const unsigned int smb1390_irq_config[] = {
	SMB1390_IRQ_TYPE, SMB1390_IRQ_POL_HIGH, SMB1390_IRQ_POL_LOW,
};

static int smb1390_irq_type(unsigned int **buf, unsigned int type,
			    const struct regmap_irq *irq, int idx, void *data)
{
	if (type != IRQ_TYPE_EDGE_RISING && type != IRQ_TYPE_EDGE_FALLING &&
	    type != IRQ_TYPE_EDGE_BOTH)
		return -EINVAL;
	buf[0][idx] |= irq->mask;
	if (type & IRQ_TYPE_EDGE_RISING)
		buf[1][idx] |= irq->mask;
	else
		buf[1][idx] &= ~irq->mask;
	if (type & IRQ_TYPE_EDGE_FALLING)
		buf[2][idx] |= irq->mask;
	else
		buf[2][idx] &= ~irq->mask;
	return 0;
}

static const struct regmap_irq_chip smb1390_irq_chip = {
	.name = "smb1390-diag",
	.status_base = SMB1390_IRQ_LATCHED,
	.mask_base = SMB1390_IRQ_DISABLE,
	.unmask_base = SMB1390_IRQ_ENABLE,
	.mask_unmask_non_inverted = true,
	.ack_base = SMB1390_IRQ_ACK,
	.init_ack_masked = true,
	.num_regs = 1,
	.irqs = smb1390_irqs,
	.num_irqs = ARRAY_SIZE(smb1390_irqs),
	.config_base = smb1390_irq_config,
	.num_config_bases = ARRAY_SIZE(smb1390_irq_config),
	.num_config_regs = 1,
	.set_type_config = smb1390_irq_type,
};

static const struct regmap_config smb1390_regmap = {
	.reg_bits = 16,
	.val_bits = 8,
	.reg_format_endian = REGMAP_ENDIAN_BIG,
	.max_register = 0x10ff,
};

static int smb1390_disable(struct smb1390_diag *chip)
{
	unsigned int control;
	int ret;

	ret = regmap_update_bits(chip->map, SMB1390_CONTROL,
				 SMB1390_SWITCHER_ENABLE | SMB1390_SLAVE_ENABLE, 0);
	if (ret)
		return ret;
	ret = regmap_read(chip->map, SMB1390_CONTROL, &control);
	if (ret)
		return ret;
	return control & (SMB1390_SWITCHER_ENABLE | SMB1390_SLAVE_ENABLE) ? -EIO : 0;
}

static irqreturn_t smb1390_irq(int irq, void *data)
{
	struct smb1390_diag *chip = data;
	unsigned int status;
	int ret;

	atomic_inc(&chip->irq_events);
	ret = regmap_read(chip->map, SMB1390_RT_STATUS, &status);
	if (ret)
		dev_err_ratelimited(chip->dev, "Cannot read IRQ status: %d\n", ret);
	else
		dev_info_ratelimited(chip->dev, "IRQ %d: realtime status=%02x (pump disabled)\n",
				     irq, status);
	return IRQ_HANDLED;
}

static ssize_t status_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct smb1390_diag *chip = dev_get_drvdata(dev);
	unsigned int control, realtime;
	u8 status[3];
	int ret;

	ret = regmap_bulk_read(chip->map, SMB1390_STATUS1, status, sizeof(status));
	if (ret)
		return ret;
	ret = regmap_read(chip->map, SMB1390_CONTROL, &control);
	if (ret)
		return ret;
	ret = regmap_read(chip->map, SMB1390_RT_STATUS, &realtime);
	if (ret)
		return ret;
	return sysfs_emit(buf, "control=%02x status=%02x,%02x,%02x realtime=%02x irq_events=%d\n",
			  control, status[0], status[1], status[2], realtime,
			  atomic_read(&chip->irq_events));
}
static DEVICE_ATTR_RO(status);

static struct attribute *smb1390_attrs[] = {
	&dev_attr_status.attr,
	NULL,
};
ATTRIBUTE_GROUPS(smb1390);

static void smb1390_cleanup(void *data)
{
	struct smb1390_diag *chip = data;
	int ret;

	ret = regmap_write(chip->map, SMB1390_IRQ_DISABLE, 0xff);
	if (ret)
		dev_err(chip->dev, "Cannot mask pump IRQs: %d\n", ret);
	ret = smb1390_disable(chip);
	if (ret)
		dev_err(chip->dev, "Cannot verify disabled pump: %d\n", ret);
}

static int smb1390_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct regmap_irq_chip_data *irq_data;
	struct smb1390_diag *chip;
	u8 revision[6], csir[2];
	int ret, i, virq;

	if (client->irq <= 0)
		return dev_err_probe(dev, -EINVAL, "Missing pump interrupt\n");
	chip = devm_kzalloc(dev, sizeof(*chip), GFP_KERNEL);
	if (!chip)
		return -ENOMEM;
	chip->dev = dev;
	chip->map = devm_regmap_init_i2c(client, &smb1390_regmap);
	if (IS_ERR(chip->map))
		return PTR_ERR(chip->map);
	i2c_set_clientdata(client, chip);
	atomic_set(&chip->irq_events, 0);
	ret = regmap_bulk_read(chip->map, SMB1390_REVISION, revision, sizeof(revision));
	if (ret)
		return dev_err_probe(dev, ret, "Cannot read SMB1390 identification\n");
	if (!revision[4] || revision[4] == 0xff)
		return dev_err_probe(dev, -ENODEV, "Invalid PMIC type %02x\n", revision[4]);
	ret = regmap_bulk_read(chip->map, SMB1390_CSIR, csir, sizeof(csir));
	if (ret)
		return dev_err_probe(dev, ret, "Cannot read SMB1390 CSIR\n");
	ret = smb1390_disable(chip);
	if (ret)
		return dev_err_probe(dev, ret, "Cannot verify pump disabled\n");
	ret = devm_add_action_or_reset(dev, smb1390_cleanup, chip);
	if (ret)
		return ret;
	ret = devm_regmap_add_irq_chip(dev, chip->map, client->irq, IRQF_ONESHOT,
				       0, &smb1390_irq_chip, &irq_data);
	if (ret)
		return dev_err_probe(dev, ret, "Cannot register pump IRQ chip\n");
	for (i = 0; i < SMB1390_NUM_IRQS; i++) {
		virq = regmap_irq_get_virq(irq_data, i);
		if (virq <= 0)
			return virq ?: -EINVAL;
		/* Stock: both edges for bits0..4, rising only for bits5..7. */
		ret = devm_request_threaded_irq(dev, virq, NULL, smb1390_irq,
					       IRQF_ONESHOT | (i < 5 ? IRQF_TRIGGER_RISING |
					       IRQF_TRIGGER_FALLING : IRQF_TRIGGER_RISING),
					       "smb1390-diag", chip);
		if (ret)
			return dev_err_probe(dev, ret, "Cannot request pump IRQ %d\n", i);
	}
	dev_info(dev, "revision=%*ph CSIR=%04x pump disabled; register/IRQ diagnostics only\n",
		 (int)sizeof(revision), revision, csir[0] | csir[1] << 8);
	return 0;
}

static void smb1390_shutdown(struct i2c_client *client)
{
	smb1390_cleanup(i2c_get_clientdata(client));
}

static const struct of_device_id smb1390_of_match[] = {
	{ .compatible = "lenovo,j706f-smb1390-diag" },
	{}
};
MODULE_DEVICE_TABLE(of, smb1390_of_match);

static struct i2c_driver smb1390_driver = {
	.driver = {
		.name = "smb1390-diag",
		.of_match_table = smb1390_of_match,
		.dev_groups = smb1390_groups,
	},
	.probe = smb1390_probe,
	.shutdown = smb1390_shutdown,
};
module_i2c_driver(smb1390_driver);

MODULE_DESCRIPTION("J706F disabled SMB1390 register and IRQ diagnostics");
MODULE_LICENSE("GPL");
