<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 6 — Power, Peripherals, `BCM4390B1` Wi-Fi + Bluetooth, and Charge Limit

Goal: bring up the Pixel 9 Pro (`caiman`) Stage 6 power and peripheral suite — `MAX77779` fuel gauge, charger, and USB-C TCPC with charge-limit control, `CS40L26A` haptics, `LM3644` rear torch, `ST54L` NFC, and shared-radio `BCM4390B1` Wi-Fi + Bluetooth with deterministic bootloader address programming — behind `omamobile-device-caiman` `0.5.0` and `tools/extract-vendor-firmware -d caiman`, keeping Slot A untouched stock Android (`CP3A.261005.005`).

Stage 5 is complete ([BRINGUP-M5.md](BRINGUP-M5.md)). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = local reference captures, `F/` = extracted `CP3A.261005.005` `vendor.img`, `K/` = `linux-omarchy-mobile` (`omamobile-zumapro-caiman-peripherals`).

## 1. Hardware & Package Scope

1. **Kernel (`omamobile-zumapro-caiman-peripherals`, `7bcdbf898`..`c1f19ef0e`).**
   - `7bcdbf898`: `arm64: dts: exynos: google: zumapro-caiman: add haptics and torch` (`CS40L26A` haptic actuator + `LM3644` `white:torch` on I2C).
   - `a7577a34b`: `arm64: dts: exynos: google: zumapro-caiman: add fuel gauge and USB-C TCPC` (`MAX77779` fuel gauge + `maxtcpc` at `1-0025`).
   - `47c1f2f71`: `arm64: dts: exynos: google: zumapro-caiman: add MAX77779 charger` (`0x69` on `hsi2c6`, linked to the fuel gauge).
   - `4ef656b03`: `arm64: dts: exynos: google: zumapro-caiman: add Bluetooth` (`uart18` / USI_APM1 at 3 Mbaud, `BT_REG_ON` on `gpn8-0` with `gpp24-3` DBO latch).
   - `82028545e`: `arm64: dts: exynos: google: zumapro-caiman: add NFC controller` (`ST54L` at `0x08` on `hsi2c9`).
   - `474e520ab`: `wifi: brcmfmac: add BCM4390 PCIe support` (adds chip ID `0x4390` / PCI ID `0x4438` and maps `brcmfmac4390b1-pcie`).
   - `c1f19ef0e`: `arm64: dts: exynos: google: zumapro-caiman: add Wi-Fi` (`pcie_1` Gen2 + `pcie_1_phy`, `wl_reg_on` on `gph3-4`, `wifi@0,0` `pci14e4,4438`, `16 MiB` `wifi_dma_pool`).
2. **Firmware extractor (`tools/extract-vendor-firmware -d caiman`).**
   - Extracts `10` mapped files (`fw_bcmdhd.bin_4390_b1` `Version=27.10.1121.57.26 (g9f20a98 b1 release24)`, `BCM_200.hcd` `BCM4390B1_0340_002.002.008.1464.0000`, `cs40l26*.{wmfw,bin}`) plus `etc/sensors/registry/` from the owner's `vendor.img` and verifies its SHA-256 manifest.
3. **Userspace (`omamobile-device-caiman` `0.5.0`, bumped from `0.4.0`).**
   - `vendor/modprobe.d/omamobile-caiman-guards.conf` blacklists `phy_zuma_pcie`, `pcie_gs201`, and `brcmfmac` alongside `hci_uart` and the other guarded drivers.
   - `omamobile-caiman-graphics-start` checks `wifi_pcie`/`wifi_pool`/`wifi_fw` and loads `phy_zuma_pcie`, `pcie_gs201`, and `brcmfmac` — waiting for a `wl*` interface before loading `hci_uart`, because `BCM4390B1` shares its radio/firmware bring-up with Bluetooth (`0xfc18`) — along with `cs40l26_vibra`, `leds_lm3644`, `max77779-fg`, and clock-gated `nxp_nci_i2c`.
   - `omamobile-bt-addr@hci0.service` (triggered by `80-omamobile-bt-addr.rules`) programs `hci0`'s public BD address from `/proc/device-tree/chosen/config/bt_addr`.
   - `75-omamobile-caiman-charger.rules` and `omamobile-caiman-charge-limit` control charging via `max77779-charger`'s `charge_behaviour` attribute.

## 2. Hardware Verification (`2026-11-15`, Slot B)

Both Boot #1 (cold fastboot flash to Slot B) and Boot #2 (clean `fastboot reboot` after `--set-active=b`) booted kernel `7.3.0-rc6-omamobile-push1-g82028545ebb3-dirty` (built from the identical working tree committed as `474e520ab` and `c1f19ef0e` after fixing `wifi@0,0` `compatible = "pci14e4,4438"`):

- **System & services (`Boot #1` & `Boot #2`)** `[V]`: `systemctl is-system-running` reached `running` with `0` failed units (`FAILED_UNITS=0`) on both boots; `omamobile-caiman-graphics.service` exited `0/SUCCESS` logging `up: GPU, display, haptics, torch, gauge 92 %, Wi-Fi (wlp1s0/wlan0), Bluetooth, NFC`.
- **Wi-Fi (`BCM4390B1`, `brcmfmac`)** `[V]`: `wlp1s0` came up behind `brcmfmac`; `iw dev wlp1s0 scan` returned `16` BSSs on Boot #1 and `23` BSSs on Boot #2.
- **Bluetooth (`BCM4390B1`, `hci_uart` + `omamobile-bt-addr@hci0`)** `[V]`: `omamobile-bt-addr@hci0.service` exited `0/SUCCESS`, `btmgmt --index 0 info` matched `/proc/device-tree/chosen/config/bt_addr` on both boots, and `timeout 8 btmgmt find` discovered `39` devices on Boot #1 and `43` devices on Boot #2.
- **Battery, Type-C PD, and Charge Limit (`max77779`)** `[V]`: `max77779-battery` reported `92%` / `Full` / `33.7 °C` / `4341562 uV` (Boot #1) and `91%` / `Full` / `32.3 °C` / `4351796 uV` (Boot #2), `max77779-charger` reported `online=1` with `charge_behaviour=[auto] inhibit-charge`, `typec/port0` showed `[sink]` and `host [device]`, `upower -d` exposed `tcpm-source-psy-1-0025` and `battery_max77779_battery`, and writing `inhibit-charge` then `auto` to `charge_behaviour` switched battery `status` between `Not charging` and `Charging`.
- **Haptics, Torch, & NFC** `[V]`: `/dev/input/event2` (`cs40l26_vibra`) passed `EVIOCSFF` `FF_RUMBLE` (`0x50`) upload/play/erase (`id=0`) on both boots; `white:torch` (`lm3644 0-0063`, `53` steps) toggled `0 -> 5 -> 0` on both boots; `/sys/class/nfc/nfc0/device/name` reported `st54l` on both boots.
- **`tools/phone-smoke` (`Boot #1` & `Boot #2`)** `[V]`: `boot`, `storage guard` (`62` partitions), `root` (`99G free`), `kernel health` (`0 WARN`, `0` oops/BUG), `systemd units`, `USB gadget`, `display`, `GPU`, `session` (Hyprland + Omarchy shell), `lock` (`passwordPam true`, `locked true`), `touch`, `buttons`, `Wi-Fi`, `Bluetooth`, `battery`, and `thermal` (`41 °C` Boot #1, `40 °C` Boot #2) all reported `ok`; `sound cards`, `sensors`, and `cameras` reported `skip`; `new dmesg errors` flagged expected non-fatal bring-up lines (`samsung-pinctrl` IRQ x6, `maxtcpc 1-0025: Failed to get vbus regulator handle`, `cma: Failed to reserve 384 MiB`).
- **Kernel PR check (`tools/kernel-pr-check f71678d09 HEAD`)** `[V]`: `checkpatch --strict` (`0` errors/warnings/checks), `W=1` builds of `3` touched C files (`ok`), `11` device trees built with `W=1` and `dtbs_check` (`0` new warnings), policy checks (`ok`), and `no Co-Authored-By trailers` (`ok`); `sign-offs` reported the expected `no human Signed-off-by` across the `7` M6 kernel commits (`7bcdbf898`..`c1f19ef0e`), which the human adds before upstream PR submission.
