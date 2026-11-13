<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 4 — Mali-G715 `panthor` GPU and DVFS

Goal: enable the Mali-G715 Immortalis MC7 GPU (`panthor`) on `caiman` with ACPM DVFS (`150`–`890 MHz`) and hang-safe module loading (`omamobile-device-caiman` `0.2.0`), moving the Hyprland + Quickshell session from `llvmpipe` onto hardware OpenGL/GLES (`panthor`) while keeping Slot A untouched stock Android (`CP3A.261005.005`) and keeping `simpledrm` intact as fallback.

Stage 3 is complete ([BRINGUP-M3.md](BRINGUP-M3.md)). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = local reference captures, `F/` = extracted `CP3A.261005.005` factory DTBs, `K/` = `linux-omarchy-mobile` (`omamobile`).

## 1. Hardware Facts

| Item | `caiman` | Source |
| --- | --- | --- |
| GPU controller | `mali@1F000000` (`arm,mali-valhall-csf`), L2 slice hash `l2-hash-values = <0x36db6d 0x5b6db6 0x00>` | `F/merged_06_49.dts` (`mali@1F000000`), matches `K/drivers/gpu/drm/panthor/panthor_drv.c` `soc_data_google_zumapro` `[V]` |
| GPU clock & power domain | `cmu_g3d` (`&acpm` protocol `0`), thermal zone `gpu-thermal` (`acpm_tmu 3`, passive trip `85 °C`, critical `105 °C`) | `K/arch/arm64/boot/dts/exynos/google/zumapro.dtsi` `[V]` |
| GPU OPPs (`kHz`) | 13 steps `150`, `202`, `251`, `302`, `351`, `401`, `471`, `552`, `626`, `696`, `764`, `829`, `890` MHz (`940 MHz` omitted for thermal headroom until `890 MHz` is validated) | `F/merged_06_49.dts` `gpu_dvfs_table_v2`, `K/drivers/clk/samsung/clk-acpm.c` `zumapro_gpu_pairs` `[V]` |
| ACPM GPU frequency cap | `options clk_acpm zumapro_gpu_max_khz=890000` (driver default `0` keeps GPU clock read-only) | `K/drivers/clk/samsung/clk-acpm.c` (`zumapro_gpu_max_khz`) `[V]` |
| CSF firmware | `/usr/lib/firmware/arm/mali/arch11.8/mali_csffw.bin` (`299008` bytes, already in rootfs) | `R/` running M3 rootfs `[V]` |
| Active display card | `/dev/dri/by-path/platform-chosen:framebuffer-card` (`simpledrm` until Stage 5 KMS `gs-decon` + `panel-google-cm4`) | `R/` running M3 rootfs (`dev/dri/by-path`) `[V]` |

## 2. Design

1. **Board DTS commit (`omamobile-zumapro-caiman-gpu`, `93d632222`).** Adds `<dt-bindings/clock/google,zumapro-acpm.h>`, `gpu_opp` (13 OPPs `150`–`890 MHz`), `&cmu_g3d` (`clock-frequency = <890000000>`), and `&gpu` (`operating-points-v2 = <&gpu_opp>`, `status = "okay"`) to `arch/arm64/boot/dts/exynos/google/zumapro-caiman.dts`. Passes `checkpatch.pl --strict` (`0` errors, `0` warnings, `0` checks) and `CHECK_DTBS=y W=1 exynos/google/zumapro-caiman.dtb` (`0` warnings).
2. **Hang-safe userspace bring-up (`omamobile-device-caiman` `0.2.0`).**
   - `vendor/modprobe.d/omamobile-caiman-guards.conf` blacklists `panthor` for automatic udev loading.
   - `vendor/modprobe.d/omamobile-caiman-clk-acpm.conf` passes `options clk_acpm zumapro_gpu_max_khz=890000`.
   - `vendor/systemd/system/linux-modules-cleanup.service.d/10-omamobile-caiman.conf` skips automatic cleanup of old `/usr/lib/modules` trees (`ConditionPathExists=!/usr/share/omamobile/device-caiman/version`) so rollback kernel images remain bootable across reboots.
   - `omamobile-caiman-graphics.service` (enabled via `multi-user.target.wants` before `display-manager.service`) runs `omamobile-caiman-graphics-start`: checks/writes `/var/lib/omamobile/caiman-graphics-started` before `modprobe panthor` (blocking future autoloads after a hard kernel hang until `--retry`), records `/run/omamobile-caiman-gpu-ready.json`, and resolves `/run/omamobile-caiman-display-card` (ordered `19470000.display-controller` ahead of `chosen:framebuffer`).
   - `uwsm/env.d/omamobile-caiman-graphics` exports `AQ_DRM_DEVICES` when `/run/omamobile-caiman-display-card` is present so Aquamarine/Hyprland drives `simpledrm` (now, or `gs-decon` in Stage 5) with `panthor` rendering rather than splitting scanout across the render-only GPU node.

## 3. Runbook

Ask the human before pushing packages, pushing modules, rebooting, or flashing (`AGENTS.md` §1).

### M4.1 Install `omamobile-device-caiman` `0.2.0`, Push Modules, & Flash Slot B
1. Push/install `omamobile-device-caiman-0.2.0-1-aarch64.pkg.tar.zst` on the phone (`pacman -U` / `tools/repo-push`).
2. Run `bin/omamobile modules-push` to install M4 kernel modules alongside the M3 tree.
3. With human approval, run `timeout 6 ./tools/phone-ssh '/usr/bin/reboot-to bootloader' || true`, verify `product: caiman` and `slot-successful:a: yes`, flash `images-m4-gpu/{boot,init_boot,vendor_boot,vendor_kernel_boot,dtbo}.img` to `*_b`, run `fastboot --set-active=b`, and `fastboot reboot`.

### M4.2 Verify `panthor` Render Node, DVFS, & Reboot Persistence
- **Pass criteria:**
  - `panthor 1f000000.gpu` probes cleanly with `mali_csffw.bin`, creates `/dev/dri/renderD128` (`tools/phone-smoke` reports `GPU: ok`), and clears `/var/lib/omamobile/caiman-graphics-started`.
  - GPU devfreq exposes the `150`–`890 MHz` OPPs (`clk_acpm.zumapro_gpu_max_khz=890000`).
  - Hyprland / Quickshell renders smoothly without `llvmpipe` fallback (`0` failed systemd units).
  - A second reboot preserves `/usr/lib/modules` trees (`linux-modules-cleanup` skipped) and brings `panthor` back cleanly.
- **Rollback:** Flash `/Volumes/OmarchyMobileWS/omamobile-kernel/images-m3-input/*_b` (and if needed run `pacman -U` or downgrade `omamobile-device-caiman`).

## 4. Hardware Verification (`2026-11-13`)

- **`panthor` & DVFS (Boot #1 & Boot #2)** `[V]`: `omamobile-caiman-graphics.service` exited `0/SUCCESS` on both boots, clearing `/var/lib/omamobile/caiman-graphics-started`, publishing `/run/omamobile-caiman-gpu-ready.json` and `/run/omamobile-caiman-display-card` (`/dev/dri/card0`), and probing `panthor 1f000000.gpu` (`Mali-G715 id 0xb8a2`, `CSF FW v2.8.0` via `mali_csffw.bin`, `/dev/dri/renderD128`). `clk_acpm.zumapro_gpu_max_khz=890000` unlocked all `13` OPPs (`150`–`890 MHz`) under `simple_ondemand` (`61` transitions up to `890 MHz`).
- **Compositor & persistence** `[V]`: Hyprland/Aquamarine used `/dev/dri/renderD128` (`OpenGL ES 3.1 Mesa 26.2.4-arch1.1.4.omamobile4`, `Mali-G715 MC7 (Panfrost)`) with `AQ_DRM_DEVICES=/dev/dri/card0` (`simpledrm` `1280x2856@60Hz`; owner noted improved smoothness over `llvmpipe`, with full `120 Hz` page-flipped smoothness waiting on Stage 5 KMS `gs-decon` + `panel-google-cm4`). `linux-modules-cleanup.service` skipped on both boots leaving all `3` `/usr/lib/modules` trees intact, and `tools/phone-smoke` passed `GPU: ok` alongside all required checks with `0` failed systemd units (`Boot #1` `42 °C`, `Boot #2` `61 °C` immediately after boot).
