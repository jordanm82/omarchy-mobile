<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 7 — AoC DSP and Sensors (`omamobile-sensors`)

Goal: bring up the Pixel 9 Pro (`caiman`) AoC audio/sensor DSP (`154b0000.aoc`, GSA-authenticated `aoc-caiman.bin` via Trusty) and expose all USF sensors through `omamobile-sensor-proxy` (`net.hadess.SensorProxy` + `omamobile-gyro`) while keeping Slot A untouched stock Android (`CP3A.261005.005`) and leaving `snd_soc_cs35l41_spi` speaker amplifiers for Stage 8.

Stage 6 is complete ([BRINGUP-M6.md](BRINGUP-M6.md)). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = local reference captures, `F/` = extracted `CP3A.261005.005` `vendor.img` / `merged_06_49.dts`, `K/` = `linux-omarchy-mobile` (`omamobile-zumapro-caiman-aoc`).

## 1. Hardware & Package Scope

1. **Kernel (`omamobile-zumapro-caiman-aoc`, `512575177`).**
   - Enables `&trusty`, `&gsa`, `&aoc_mbox_a32`, `&aoc_mbox_f1`, `&aoc_mbox_p6`, `s2mpg15-pmic` sensor rails (`sensor_3v3` on `ldo5s` and `sensor_1v8` on `ldo7s`), and `&aoc` (`memory-region = <&aoc_reserved>`, `firmware-name = "aoc-caiman.bin"`, `google,board-id = <0x40902>`, `google,board-rev = <0x10000>`, `google,gnss-type = <2>`, matching `F/merged_06_49.dts`).
   - Built as clean kernel `7.3.0-rc6-omamobile-push1-g512575177407` with `1828` modules.
2. **Firmware extractor (`tools/extract-vendor-firmware -d caiman`).**
   - Adds `"firmware/aoc.bin|aoc-caiman.bin"` (`29,076,160` bytes) alongside the M6 Wi-Fi, Bluetooth, haptics, and `/vendor/etc/sensors/registry/` extraction (`11` mapped files total) with SHA-256 verification.
3. **Userspace (`omamobile-device-caiman` `0.6.0` + `omamobile-sensors`).**
   - `vendor/modprobe.d/omamobile-caiman-aoc.conf` blacklists `trusty_core`, `trusty_log`, `trusty_ipc`, `trusty_virtio`, `gsa`, `gs201_aoc_sysmmu`, `mailbox_wc`, `aoc_core`, `aoc_channel_dev`, `aoc_char_dev`, `aoc_alsa_dev`, `aoc_alsa_dev_util`, and `snd_soc_cs35l41_spi`.
   - `omamobile-caiman-aoc-start` (`omamobile-caiman-aoc.service`, aliased as `omamobile-aoc.service`) writes `/var/lib/omamobile/caiman-aoc-started`, loads Trusty -> GSA -> AoC drivers, writes `/run/omamobile/aoc-firmware-loaded` (read by `omamobile-sensor-proxy`), loads `aoc-caiman.bin`, and waits for `Services : [1-9]` and `/dev/acd-com.google.usf`.
   - `omamobile-sensors` runs `omamobile-sensor-proxy` after `omamobile-aoc.service` (`test/all` verified natively on the phone).

## 2. Hardware Verification (`2026-11-16`, Slot B)

Verified across Boot #1 (cold fastboot flash to Slot B) and Boot #2 (clean `reboot-to bootloader` -> `fastboot --set-active=b` -> `fastboot reboot`) on `7.3.0-rc6-omamobile-push1-g512575177407`:

- **System & AoC (`Boot #1` & `Boot #2`)** `[V]`: `systemctl is-system-running` = `running` with `0` failed units on both boots. `omamobile-caiman-aoc-start` brought AoC up to `Services : 94` (`alsa-aoc communication is ready!`) and created `/dev/acd-com.google.usf` + `/dev/acd-*` channels.
- **Sensors (`Boot #1` & `Boot #2`)** `[V]`: `omamobile-sensor-proxy` waited the AoC settle window, loaded `/usr/share/omamobile/sensors/registry/*.reg` + `append/*.reg` with `CDT 0x96100` (`/sys/firmware/devicetree/base/chosen/plat`), and exposed `accel` (handle `31`), `light` (handle `44`), `proximity` (handle `24`), `compass` (handle `53`), and `gyro` (handle `32`, `12–400 Hz`). (`debugfs -R "ls -l /sensors/registry" /dev/sda1` confirmed `persist` on `caiman` is `f2fs` rather than `ext4`, so `factory_calibration()`'s `debugfs` call skipped `persist` calibration.)
- **D-Bus & `omamobile-gyro` streaming** `[V]`: `busctl` + Python `Gio` claims verified `HasAccelerometer=true`, `HasAmbientLight=true`, `HasProximity=true`, `HasCompass=true` (`AccelerometerTilt=face-up`, `CompassHeading=75.56`), and `omamobile-gyro --stats --duration 2` streamed `779` records in `1.95 s` (`398.6 Hz`, `0` drops, `median 0.90 ms`) on Boot #1 and `781` records in `1.96 s` (`398.7 Hz`, `0` drops, `median 0.91 ms`) on Boot #2.
- **`tools/phone-smoke` (`Boot #1` & `Boot #2`)** `[V]`: all required checks (`boot`, `storage guard`, `root`, `kernel health` `0 WARN` / `0` oops/BUG, `USB gadget`, `session`) plus `systemd units`, `display`, `GPU`, `lock`, `touch`, `buttons`, `Wi-Fi` (`link up`), `Bluetooth`, `battery` (`91% Charging`), `sensors` (`ok`, `Accelerometer AmbientLight Proximity`), and `thermal` (`51 °C` Boot #1, `72 °C` Boot #2) passed; `sound cards` and `cameras` skipped (`new dmesg errors` flagged the same non-fatal `samsung-pinctrl` / `maxtcpc` / `brcmf_c_set_joinpref_default` lines).
- **Kernel PR check (`tools/kernel-pr-check c1f19ef0e HEAD`)** `[V]`: `checkpatch --strict` (`0` errors/warnings/checks), `11` device trees built with `W=1` and `dtbs_check` (`0` new warnings), policy checks (`ok`), `no Co-Authored-By trailers` (`ok`), and `C builds` (`SKIP`: no C files touched); `sign-offs` reported the expected `no human Signed-off-by` on `512575177` prior to human sign-off.
