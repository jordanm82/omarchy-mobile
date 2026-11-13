<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 3 — Input (`gpio-keys` buttons and Synaptics `S3908TG` SPI touchscreen)

Goal: make `caiman` usable by hand on Omarchy Mobile (`gate f` for Power and Volume keys, `gate g` for touchscreen PIN-pad unlock, shell gestures, and on-screen keyboard) while keeping Slot A untouched stock Android (`CP3A.261005.005`) and keeping M2.7's `userdata` root filesystem intact (updating only `/usr/lib/modules/<release>` via `bin/omamobile modules-push` and flashing Slot B's 5 boot images).

Stage 2 is complete ([BRINGUP-M2.md](BRINGUP-M2.md)). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = local reference captures, `F/` = extracted `CP3A.261005.005` factory DTBs, `G/` = Google's GPL `devices/google/caimito` tree (`38a058681d6c`), `K/` = `linux-omarchy-mobile` (`omamobile`).

## 1. Hardware Facts

| Item | `caiman` | `tegu` (merged) | Source |
| --- | --- | --- | --- |
| Power / Volume Down / Volume Up | `gpa4-0` (`KEY_POWER`, wakeup), `gpa4-1` (`KEY_VOLUMEDOWN`), `gpa6-2` (`KEY_VOLUMEUP`), all `GPIO_ACTIVE_LOW` | Identical pins, keycodes, and polarities | `F/merged_06_49.dts`, `K/zumapro-tegu.dts` `[V]` |
| Key & touch bank EINTs | `&gpa4` (`GIC_SPI 28..29`), `&gpa6` (`GIC_SPI 30..35`), `&gpn0` (`GIC_SPI 0`) | Identical GIC SPI lines on `zumapro` | `F/base-dtbs/06.dts`, `K/zumapro-tegu.dts` `[V]` |
| Touch SPI bus | `&spi20` (`usi2_hsi0` at `0x111d0000`), CS0, mode 0, `10 MHz`, dedicated USI2 pads | Identical (`&spi20`, `10 MHz`) | `G/zuma-caimito-common-touch.dtsi`, `K/zumapro-tegu.dts` `[V]` |
| Touch interrupt | `gpn0-0`, `IRQ_TYPE_LEVEL_LOW` (`IRQF_ONESHOT \| IRQF_TRIGGER_LOW`) | Identical (`gpn0-0`, `IRQ_TYPE_LEVEL_LOW`) | `G/zuma-caimito-common-touch.dtsi`, `K/zumapro-tegu.dts` `[V]` |
| Touch reset | `gpp1-1`, `GPIO_ACTIVE_LOW`; held low via `touch_reset_held` on `&usi2_hsi0` before USI switches to SPI | Identical (`gpp1-1`, `touch_reset_held`) | `G/zuma-caimito-common-touch.dtsi`, `K/zumapro-tegu.dts` `[V]` |
| Touch supplies | `vdd-supply`: S2MPG14 `ldo25m` (`1.8 V`, `PP1800_L25M_TS1_DVDD`); `avdd-supply`: S2MPG14 `ldo4m` (`3.3 V`, `PP3300_L4M_TS1_AVDD`) | Identical (`ldo25m` `1.8 V`, `ldo4m` `3.3 V`, matching ABL handover voltages) | `G/zuma-caimito-common-touch.dtsi` lines 13–14 & 32–40, `K/zumapro-tegu.dts` `[V]` |
| Touch controller | Synaptics `S3908TG` (`compatible = "syna,s3908"`, TouchComm over SPI; `1280x2856` sensor resolution reported by controller firmware) | Synaptics `S3908` (`syna,s3908`) | `G/zuma-caiman-touch.dtsi` (`synaptics,suffix-fw-name = "S3908TG"`), `R/vendor-modules.txt` (`syna_touch.ko`), `K/drivers/input/touchscreen/synaptics_tcm.c` `[V]` |
| Active display/touch size | `66 x 147 mm` (`19` px/mm at `1280x2856`) | `65 x 145 mm` | `G/zuma-caiman-touch.dtsi` (`synaptics,pixels-per-mm = <19>`), MIT `panel-gs-cm4.c` (`WIDTH_MM = 66`, `HEIGHT_MM = 147`) `[V]` |

## 2. Design

1. **Zero new kernel C code or Kconfig changes (`[V]`).** `CONFIG_KEYBOARD_GPIO=y`, `CONFIG_SPI_S3C64XX=y`, and `CONFIG_TOUCHSCREEN_SYNAPTICS_TCM_SPI=y` are already built into `caiman`'s kernel. Unlike `akita` (whose Goodix GT9895 runs `LDO4M` at `3.0 V` vs ABL's `3.3 V`), `caiman`'s Synaptics `S3908TG` runs `PP3300_L4M_TS1_AVDD` at **`3.3 V`** (`3300000 uV`) and `PP1800_L25M_TS1_DVDD` at **`1.8 V`** (`1800000 uV`) (`G/zuma-caimito-common-touch.dtsi`), matching ABL's S2MPG14 handover selectors and `zumapro-tegu.dts`.
2. **No external firmware file.** `synaptics_tcm.c` runs the TouchComm firmware already in the `S3908TG`'s on-chip flash, sequences `avdd` (`3.3 V`) ahead of `vdd` (`1.8 V`) with a `200 ms` power delay, releases `reset-gpios`, reads `ts->max_x` / `ts->max_y` from `IDENTIFY` + `GET_APP_INFO`, and applies `touchscreen-x-mm = <66>` / `touchscreen-y-mm = <147>`.
3. **Board DTS commit (`omamobile-zumapro-caiman-input`, `91ad3d566`).** Adds `gpio-keys`, `touch_avdd` (`ldo4m`) and `touch_vdd` (`ldo25m`), `&gpa4`/`&gpa6`/`&gpn0` interrupt-controller declarations, `touch_reset_held` on `&pinctrl_peric0` / `&usi2_hsi0`, and `touchscreen@0` (`syna,s3908`) on `&spi20`. Passes `checkpatch.pl --strict` (0 warnings/checks) and `CHECK_DTBS=y W=1 exynos/google/zumapro-caiman.dtb` (0 warnings).
4. **No `userdata` reinstall.** Push the new kernel's module tree with `bin/omamobile modules-push` (keeping M2.7's `33549ee80` module tree intact for instant rollback) and flash only the 5 Slot-B boot partitions.

## 3. Runbook

Ask the human before pushing modules, rebooting, or flashing (`AGENTS.md` §1). Track `slot-retry-count:b` at each step.

### M3.1 Push Modules & Flash `omamobile-zumapro-caiman-input`
1. Over USB SSH on the running M2.7 system, run `bin/omamobile modules-push` to install `/usr/lib/modules/7.3.0-rc6-omamobile-push1-g91ad3d566a6c`.
2. With human approval, run `/usr/bin/reboot-to bootloader`, verify `product: caiman` and `slot-successful:a: yes`, flash the 5 `images-m3-input/*_b` partitions, run `fastboot --set-active=b` (`slot-retry-count:b = 3`), and `fastboot reboot`.

### M3.2 Verify Buttons (`gate f`) & Touchscreen (`gate g`)
- **Pass (`gate f` — buttons):**
  - `gpio-keys` registers as an input device with interrupts on `gpa4-0` (`Power`), `gpa4-1` (`Volume Down`), and `gpa6-2` (`Volume Up`) in `/proc/interrupts`.
  - Short presses increment interrupt counts (`logind` logs short Power press; short Power press locks and wakes the screen). *(Never hold Power long — PMIC hardware reset.)*
  - `/sys/power/mem_sleep` reads `[s2idle] deep`.
- **Pass (`gate g` — touchscreen & session):**
  - `synaptics-tcm spi0.0` identifies `S3908` / TouchComm firmware at `1280x2856` with zero errors; `touch-avdd` and `touch-vdd` enable cleanly; interrupts rise on `gpn0-0` with touches.
  - Swiping up on the lock screen and tapping the PIN pad unlocks the Omarchy session by hand; shell gestures and the on-screen keyboard work at normal height (`66x147 mm`).
  - `tools/phone-smoke` reports `buttons: ok` and `touch: ok` alongside all required rows `ok` (`0` failed systemd units).
  - A second boot (`reboot-to bootloader` → `fastboot --set-active=b && fastboot reboot`) comes up identically with touch and buttons working.
- **Rollback:** Flash `/Volumes/OmarchyMobileWS/omamobile-kernel/images-m2.5-ufs-root/*_b` (whose module directory remains installed in `/usr/lib/modules/`).

## 4. Hardware Verification (`2026-11-13`)

- **`gate f` (Buttons)** `[V]`: `gpio-keys` (`input1`, `event1`) bound `Power` (`gpa4 0`), `Volume Down` (`gpa4 1`), and `Volume Up` (`gpa6 2`); IRQ counters incremented on physical presses (`10` / `2` / `6`), `/sys/power/mem_sleep` read `[s2idle] deep`, and owner confirmed button operation.
- **`gate g` (Touchscreen)** `[V]`: `touch-avdd` (`3.3 V`) and `touch-vdd` (`1.8 V`) enabled cleanly; `synaptics-tcm spi0.0` probed `S3908GA1B0-15.0` (`TouchComm v1`, `build 4432698`, `12800x28560`, `ABS_MT_POSITION_X` `0..12799` res `193`, `ABS_MT_POSITION_Y` `0..28559` res `194`, `gpn0` IRQ `564`), bound in Hyprland as `synaptics-touchcomm-touchscreen`, and owner confirmed accurate touch tracking, lock-screen PIN unlock, shell navigation, and on-screen keyboard input. `tools/phone-smoke` (`7.3.0-rc6-omamobile-push1-g91ad3d566a6c`, `0` failed systemd units, `up 2886s`) passed `touch: ok` and `buttons: ok` alongside all required checks.
