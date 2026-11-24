# Hardware and source map

Kernel paths below are relative to `kernel/`; desktop configuration paths are
relative to the repository root.

| Feature | Implementation / evidence |
| --- | --- |
| Board wiring | `arch/arm64/boot/dts/qcom/sm7150-lenovo-j706f-*.dts` |
| RM692E6 dual-DSI panel and brightness | `drivers/gpu/drm/panel/panel-lenovo-j706f.c` |
| Bonded command lifetime / completion | `drivers/gpu/drm/msm/dsi/dsi_manager.c`, `dsi_host.c`, `dsi.h` |
| DSI timeout/FIFO diagnostics | `drivers/gpu/drm/msm/dsi/dsi_host.c` |
| Goodix GT738x touch | `drivers/input/touchscreen/goodix_gt738x.c` |
| GPIO exclusions | `drivers/pinctrl/qcom/pinctrl-msm.c` |
| Bluetooth controller | `drivers/bluetooth/hci_qca.c` plus board DT |
| Charging / SMB5 encoding | `drivers/power/supply/qcom_smbx.c` |
| Audio routing | `sound/soc/qcom/j706f.c` |
| Four protected speaker amplifiers | `sound/soc/codecs/cs35l41.c` and `.h` |
| Probe tracing | `drivers/base/dd.c` |
| GNOME gesture workaround | `configs/touch-gesture-extension.js` and metadata |

## Device-tree layers

The active `power.dts` includes `daily`, then `gpu`, `connectivity`, `hall-power`,
`dual-hid`, `keyboard-v2`, and `diagnostic` layers. These are small feature layers
within one source tree, not independent kernel copies. `audio` and older keyboard
variants preserve earlier target choices. Review includes before editing a node.
Do not rename these during unrelated driver work.

## Important hardware facts

- Touch is GT738x; the verified coordinate base is `0x824d`.
- The display is dual-link command-mode RM692E6 EDO; maximum brightness is 2047,
  with a logical 0–2047 interface mapped to an approximately 10–100% active
  panel-code range. Blanking sends zero. Under this mapping logical 340 maps
  to physical 511; the old raw-511 recovery procedure is not an accepted
  recovery test for the new mapping.
- Keyboard and touchpad are separate HID devices. Hall supply L8c at 1.8V and
  GPIO93 lid state were essential to real input, beyond enumeration.
- Four CS35L41 B2 amplifiers occupy I2C1 addresses `0x40..0x43`. Their protection
  firmware must remain enabled. `wm_adsp dsp` must remain the first private member.
- Battery gauge is BQ27541 at I2C9 address `0x55`. SMB5 voltage encoding differs
  from the SMB2 formula; the current charging configuration is conservative.
- A GPIO59 register read caused a hang; this is not proof of a physically broken
  pin. Do not probe GPIO59–62 or hot-unbind Bluetooth.
- The public Bluetooth DT omits a fixed device address. Optional private identity
  configuration is applied only to the generated DTB; see the build guide.

Upstream source identity and archive digest are recorded in `configs/layout.json`.
Use the maintained source and public technical milestones when studying local
changes; private maintainer references and frozen research patches are not
required inputs for the public build.
