<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 10 — Cameras (`s5kgnk`, 3x `imx858`, `gs201-csis` LoCH, and `libcamera`)

Goal: enable all four Pixel 9 Pro (`caiman`, Slot B) cameras (`s5kgnk` Main `4080x3072`, `imx858` Ultrawide `4032x3024`, `imx858` Telephoto `4032x3024`, and `imx858` Front `3840x2736`) through mainline V4L2/Media Controller (`gs201-csis` LoCH DMA + `dcphy-rx`), `libcamera`, and PipeWire/WirePlumber with `0` driver debug hacks and two-boot persistence, while keeping Slot A untouched stock Android (`CP3A.261005.005`).

Stage 9 is complete ([BRINGUP-M9.md](BRINGUP-M9.md)). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = phone hardware runs, `K/` = `linux-omarchy-mobile` (`7.3.0-rc6-omamobile-push1-g6d2575ca807f-dirty`, committed cleanly as `32264e98e` on `omamobile-zumapro-caiman-camera`).

## 1. Root Cause, Kernel Fixes & Package Changes

1. **Kernel (`K/`, commits `d72154406`, `6d2575ca8`, `32264e98e` on `omamobile-zumapro-caiman-camera`).**
   - **Device tree (`zumapro-caiman.dts`) & PMIC (`s2mpg14`/`s2mpg15`)**: added ACPM PMIC GPIO support (`d72154406`), camera PMIC supplies/sensors (`6d2575ca8`), camera clocks, C-PHY/D-PHY RX (`dcphy-rx`), `csis@1c040000` (`google,lrte-packet-delimiters;`), and `s5kgnk` (Main) / 3x `imx858` (UW, Tele, Front) bindings (`32264e98e`).
   - **`gs201-csis` (`zumapro` LoCH WDMA) production fixes (`32264e98e`)**:
     - Defaulted `pixel_mode = -1` to `CSIS_ISPCFG_PIXEL_MODE_OCTA` (`3`) when `csis->soc->has_loch` (keeping `CSIS_ISPCFG_PIXEL_MODE_QUAD` (`2`) for `gs201`; `pixel_mode=2` on `zumapro` produced `ERR 0x404`/`0x40` and `AXI=80000003` on every frame).
     - Allocated per-instance `SZ_64K` coherent `sq_cpu`/`sq_dma` in `zumapro_loch_start` and programmed `ZUMAPRO_LOCH_SQ_CFG_{ID,STRIDE,ADDR_LSB,ADDR_MSB}` (`0x108..0x114`), freed in `zumapro_loch_stop` (`SQ_EN` `0x100=1` at POR cannot be disabled or left with `ADDR=0`).
     - Fixed `CFG_MISS` (`0x10` `LateConfigError`) starvation freeze by tracking `bool loch_started`, clearing `ZUMAPRO_LOCH_WDMA_CTX_EN` in `zumapro_loch_irq` when `!csis->active && !csis->next`, and re-arming `WDMA_CTX_EN` + `WDMA_CFG_EN` in `zumapro_loch_set_addr` when `csis->loch_started`.
     - Removed temporary bring-up module parameters and debug dumps.
   - **`tools/kernel-pr-check`** (`646a14599..HEAD`, `32264e98e`): passed `no Co-Authored-By trailers`, `subjects have subsystem prefixes`, `checkpatch --strict: no errors` (`7` warnings/checks), `policy (tools/pr-check): identifiers, blobs`, `W=1 builds of 10 touched C files`, and `11 device trees build with W=1, no new warnings` (expected failure on `sign-offs` before human `Signed-off-by`; `dt_binding_check`/`dtbs_check` skipped without `dtschema` in container).
2. **`tools/extract-camera-data` & `libcamera` (`0.7.2-4.24`).**
   - Extended `tools/extract-camera-data` for `s5kgnk` (Main `0x08EF`), `imx858-{uw,tele,front}` (`0x0858`), `.text_pinned`, and `zumapro` C-PHY CTLE/RX presets.
   - Added [0058-libcamera-Add-the-Samsung-S5KGNK-and-Sony-IMX858-sensors.patch](../../packages/libcamera/0058-libcamera-Add-the-Samsung-S5KGNK-and-Sony-IMX858-sensors.patch) and rebuilt/signed `libcamera` `0.7.2-4.24` in `omamobile-alarm-build`.
3. **`omamobile-device-caiman` (`0.9.0-1`).**
   - Added [70-omamobile-dma-heap.rules](../../packages/omamobile-device-caiman/vendor/udev/rules.d/70-omamobile-dma-heap.rules) (`dma_heap` `video` `0660` `uaccess`) and [50-omamobile-cameras.conf](../../packages/omamobile-device-caiman/wireplumber/50-omamobile-cameras.conf) mapping the four sensor paths to `Main camera`, `Ultrawide camera`, `Telephoto camera`, and `Front camera` while disabling raw `~v4l2_device.platform-1c0.0000.csis` V4L2 nodes.
   - Updated `install` and `test/all` (`37` staged paths; passed all `11` checks inside `omamobile-alarm-build`).

## 2. Hardware Verification (`2026-11-17`, Slot B, zero module params)

Verified across Boot #1 and cold Boot #2 (`reboot-to bootloader` -> `fastboot set_active b` -> `fastboot reboot`) on `7.3.0-rc6-omamobile-push1-g6d2575ca807f-dirty` (built from the Stage 10 source before amending out unused `int wdma_irq;` in `32264e98e`) with `libcamera 0.7.2-4.24` and `omamobile-device-caiman 0.9.0-1`:

- **Boot #1 GStreamer SoftISP & `cam -C4` all-4 capture** `[V]` (`R/`, `gst-launch-1.0` + `cam`): unprivileged user `jordan` ran `gst-launch-1.0 libcamerasrc` (Mali-G715 Panfrost SoftISP), and `cam -c 1..4 -C4` completed with `rc=0` on all four sensors (`WDMA done ... errors 0, missed frame ends 0`; `dropped 1` on UW/Tele recovered cleanly without freeze).
- **Boot #2 Cold Persistence (`cam -c 1..4 -C4`)** `[V]` (`R/`):
  - `cam -c 1` Main (`s5kgnk`, `4072x3072`): `30.00 fps`, `50331648` B frames, `WDMA done 7 errors 0, dropped 0, missed frame ends 0`.
  - `cam -c 2` Ultrawide (`imx858`, `4024x3024`): `29.70 fps`, `48771072` B frames, `WDMA done 6 errors 0, dropped 1, missed frame ends 0`.
  - `cam -c 3` Telephoto (`imx858`, `4024x3024`): `29.54 fps`, `48771072` B frames, `WDMA done 6 errors 0, dropped 1, missed frame ends 0`.
  - `cam -c 4` Front (`imx858`, `3832x2736`): `29.70 fps`, `42024960` B frames, `WDMA done 7 errors 0, dropped 0, missed frame ends 0`.
- **PipeWire / WirePlumber & `tools/phone-smoke` (Boot #2)** `[V]` (`R/`): `wpctl status` as `jordan` showed `s5kgnk`/`imx858` `[libcamera]` sources named `Main camera`, `Ultrawide camera`, `Telephoto camera`, and `Front camera` with raw CSIS V4L2 nodes hidden; `/usr/bin/omacam` linked cleanly against `libcamera.so.0.7`. `DEVICE=caiman ./tools/phone-smoke` reported `ok` on `boot`, `storage guard`, `root`, `kernel health` (`0 WARN, 0 error lines in dmesg`), `USB gadget`, `display` (`1280x2856`), `GPU` (`panthor`), `session`, `lock`, `touch`, `buttons`, `Wi-Fi` (`wlp1s0`), `Bluetooth` (`hci0, powered true`), `battery` (`94% Full, 32 °C`), `sound cards` (`googlecaimanaoc`), `sensors`, `cameras` (`4 listed by libcamera`), and `thermal` (`41 °C`).
- **Pre-existing non-camera note in `phone-smoke`**: `systemd units` flagged `failed: omamobile-speaker-protection.service` on Boot #2 because `/dev/sda1` (`persist`) `/audio/speaker.cal` (`ino=40`) on this handset currently has `size=0` (`data=b''`) when `OMAMOBILE_SPK_DEFAULT_CAL=0` (unrelated to Stage 10 camera changes).
