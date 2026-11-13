# Pixel 9 Pro (`caiman`) — M5 Display (`panel-google-cm4` + `gs-decon` KMS + `gs-dsim-cmd`)

Status: offline preparation built and validated; awaiting owner approval for Slot B flash and live hardware Boot #1.

## Scope & Architecture

- **Panel:** Google CM4 `1280x2856` command-mode AMOLED (`66x147 mm`), take-over driver `panel-google-cm4` (`CONFIG_DRM_PANEL_GOOGLE_CM4=m`):
  - Exposes `1280x2856@60` (preferred) and `1280x2856@120` modes.
  - Backlight DBV range `176..3271`, default `1209`, MSB-first DCS `SET_DISPLAY_BRIGHTNESS`, and `0x22` (`CM4_DCS_ALL_PIXEL_OFF`) at brightness `0`.
  - Samsung `0xf0`/`0xb9`/`0xbd`/`0xf2`/`0x60`/`0xf7` refresh-rate switch and `prepare`/`enable`/`disable`/`unprepare` sequences; leaves `allow_tx=0` read-only unless `exynos_drm.panel_name=google-cm4` (or `google-cm4.<id>`) is on `/proc/cmdline`.
- **Display Controller (`gs-decon`):**
  - Updated `gs_decon_soc_data` to carry a list of per-panel mode sets so `google,zumapro-decon` supports both `tegu` (`1080x2424`) and `cm4` (`1280x2856`), selecting the matching mode set from bootloader scanout geometry at probe time.
- **Devicetree (`zumapro-caiman.dts`):**
  - Added `64 MiB` `display_pool` (`0x98000000..0x9e000000`, inside Linux's default `384 MiB` CMA region with no firmware carve-outs in between) and enabled `decon0` (`display-controller@19470000`) and `dsi0` (`dsi@19440000` -> `panel@0` `compatible = "google,cm4"`).
- **Userspace (`omamobile-device-caiman` `0.3.0-1`):**
  - Blacklists `gs_decon` alongside `panthor` in `omamobile-caiman-guards.conf` for hang-safe startup.
  - Adds `omamobile-caiman-display.conf` (`options gs_decon max_refresh=120 screen_off=2`).
  - `omamobile-caiman-graphics-start` sets `gs_dsim_cmd.allow_tx=1` when `/proc/cmdline` names `google-cm4` (or `google-cm4.<id>`), loads `gs_decon stage=2 fbdev=0`, waits for `19470000.display-controller` -> `gs-decon`, and updates `/run/omamobile-caiman-display-card`.

## Offline Validation Results

1. **Userspace (`omarchy-mobile` branch `caiman-m5`, `3a7590b`):**
   - `./packages/omamobile-device-caiman/test/all` passed all 16 checks (staging 19 files, `allow_tx` gating for `google-cm4` / `google-cm4.<id>` vs other/unnamed, `gs_decon stage=2 fbdev=0`, `gs-decon` card priority over `simpledrm`, marker/retry/failure isolation).
   - Built, GPG-signed, and indexed `omamobile-device-caiman-0.3.0-1-aarch64.pkg.tar.zst` in `out/caiman/repo/aarch64/`.
   - `./tools/pr-check` and `./tests/review-lessons` passed.
2. **Kernel (`linux-omarchy-mobile` branch `omamobile-zumapro-caiman-display`, `df13b3b8f`..`f71678d09`):**
   - `scripts/checkpatch.pl --strict --no-signoff` and `./tools/kernel-pr-check` reported 0 errors across all 4 commits (`google,cm4.yaml`, `panel-google-cm4`, `gs-decon`, `zumapro-caiman.dts`; human `Signed-off-by` to be added by owner before PR).
   - `W=1` compile of `exynos/google/zumapro-caiman.dtb`, `panel-google-cm4.o`, and `gs-decon.o` plus full incremental build (`7.3.0-rc6-omamobile-push1-gf71678d09eda`) passed with 0 warnings/errors.
   - Packed clean `modules-7.3.0-rc6-omamobile-push1-gf71678d09eda.tar.zst` (1828 modules, zero AppleDouble files) and AVB-signed boot images in `images-m5-display/` (`dtb.img` verified for `decon0`, `dsi0`/`google,cm4`, `display-pool`; `initramfs` verified for `ssh-ed25519`).

## Hardware Verification Plan (Pending Owner Approval)

1. **Install & Flash (`Slot B` only):**
   - On the live M4 boot (`172.16.42.1`): push `modules-7.3.0-rc6-omamobile-push1-gf71678d09eda.tar.zst` (`modules-push`) and upgrade `omamobile-device-caiman` to `0.3.0-1` (`pacman -U` + `sync`).
   - Reboot to bootloader (`fastboot`) and flash `images-m5-display/{boot,init_boot,vendor_boot,vendor_kernel_boot,dtbo}.img` to `_b` (`slot-retry-count:b` reset to `3`).
2. **Boot #1 Verification (60 Hz KMS + DSIM Timer Capture):**
   - Verify `gs_dsim_cmd.allow_tx=1`, `panel-google-cm4` backlight (`/sys/class/backlight/*`), `gs-decon` binding on `19470000.display-controller`, `1280x2856` KMS replacing `simpledrm`, and Hyprland rendering with `panthor`.
   - Read ABL's 60 Hz `UNDERRUN_CTRL` and `CMD_TE_CTRL1` registers logged by `gs_dsim_probe()` in `dmesg`.
3. **120 Hz Follow-Up:**
   - Add CM4's measured 60 Hz and derived 120 Hz (`85.5 MHz` word clock) timing row to `gs_dsim_rates[][2]` in `drivers/gpu/drm/google/gs-dsim-cmd.c`, rebuild `gs-dsim-cmd.ko` and boot images, and verify `1280x2856@120`, backlight slider, `screen_off=2` DPMS off/on, and two-boot persistence.
