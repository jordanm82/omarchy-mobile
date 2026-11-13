# Pixel 9 Pro (`caiman`) — M5 Display (`panel-google-cm4` + `gs-decon` KMS + `gs-dsim-cmd`)

Status: **PASSED on hardware across Boot #1 and Boot #2** (`7.3.0-rc6-omamobile-push1-gf71678d09eda`, `omamobile-device-caiman` `0.3.0-1`, `slot-retry-count:b` refreshed to `3` before Boot #1, Slot A untouched).

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

## Hardware Verification Results (Boot #1 & Boot #2 Passed)

1. **Install & Flash (`Slot B` only):**
   - Pushed `/usr/lib/modules/7.3.0-rc6-omamobile-push1-gf71678d09eda` (`depmod -a`) and upgraded `omamobile-device-caiman` to `0.3.0-1` on the running M4 boot (`172.16.42.1`).
   - Flashed `images-m5-display/{boot,init_boot,vendor_boot,vendor_kernel_boot,dtbo}.img` to `_b` (`slot-retry-count:b: 3`).
2. **Boot #1 Verification (`1280x2856@120 Hz` on First Boot):**
   - `omamobile-caiman-graphics.service` exited `0/SUCCESS` (`up: GPU, display`, marker cleared), setting `gs_dsim_cmd.allow_tx=1` (matching `exynos_drm.panel_name=google-cm4.<id>`) and resolving `/run/omamobile-caiman-display-card` to `/dev/dri/card2` (`19470000.display-controller`).
   - `gs-dsim-cmd` dumped `CMD_TE_CTRL1 (0x088) = 0x34c53c1e` and matched `link timers for 60 Hz` (`1368 Mbit/s` / `85.5 MHz` word clock / `350 us` TE idle — shared with HK3), enabling `120 Hz` immediately without needing a separate row in `gs_dsim_rates[]`.
   - `gs-decon` attached `display-pool` (`0x98000000`), registered `card2-DSI-1` (`1280x2856`, `60/120 Hz`), and switched cleanly to `120 Hz` (`gs-decon-fs` / `gs-decon-fd` ticking evenly, zero flip timeouts).
   - `hyprctl monitors`: `1280x2856@120.00000 at 0x0`, physical size `66x147 mm`, `scale: 2.6666667`, `availableModes: 1280x2856@120.00Hz 1280x2856@60.00Hz`; owner visually confirmed noticeably smoother 120 Hz rendering.
   - **Backlight (`/sys/class/backlight/19440000.dsi.0`):** `1209 -> 300 -> 2400 -> 0 -> 1209` verified via `actual_brightness` (`max_brightness=3271`). Note: udev autoloaded `panel-google-cm4` at `3.818s` (before `omamobile-caiman-graphics.service` enabled `allow_tx=1`), logging one harmless `-1` (`-EPERM`) backlight init attempt while `cm4_bl_update_status` preserved the level (`1209`).
   - **DPMS (`screen_off=2`):** Verified `hl.dsp.dpms({ action = "enable" / "disable" / "enable" })`: toggled `dpms=On -> Off -> On`, dropped to `60 Hz` with panel sleep (`gs-decon-fs` stopped at `5394`), and woke cleanly back to `120 Hz` (`5394 -> 5578`).
3. **Boot #2 Verification (Persistence):**
   - Clean `systemctl reboot` came up on `7.3.0-rc6-omamobile-push1-gf71678d09eda` with `omamobile-device-caiman` `0.3.0-1`, `omamobile-caiman-graphics.service` `active`, `marker-cleared`, `/dev/dri/card2`, `allow_tx=Y`, `actual_brightness=1209`, `1280x2856@120.00000`, `dpms=On`, and `gs-decon-fs`/`fd` interrupts (`1822`/`1821`) ticking cleanly.
