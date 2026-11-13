<!-- SPDX-License-Identifier: MIT -->
# Pixel 9 Pro (caiman): Stage 2 — UFS behind the storage guard and Arch/Omarchy root

Goal: bring up `caiman`'s internal UFS 4.0 storage (`ufs@13200000`) on mainline Linux 7.3-rc6 behind the read-only storage guard (`gate c`), take two verified read-only radio/NV backups (`tools/nv-backup -d caiman`), and boot persistent Arch Linux ARM (`gate d`) and Omarchy Mobile (`gate e`) from `userdata` on Slot B while keeping stock Android 17 (`CP3A.261005.005`) untouched on Slot A.

Every statement of fact is marked `[V]` (verified from hardware or stock/mainline sources) or `[I]` (inference to verify on hardware). Path abbreviations follow [NOTES.md](NOTES.md): `R/` = local Stage 0/M1 reference captures (`/Volumes/OmarchyMobileWS/android/reference/caiman-*`, never committed), `F/` = extracted `CP3A.261005.005` factory DTBs, `L/` = `linux-omarchy-mobile` (`omamobile`).

## 1. Hardware Facts

| Item | Value | Source |
| --- | --- | --- |
| UFS host | `ufs@13200000` (`google,zumapro-ufs`), GIC SPI 466; regions: `hci` `0x13200000/0x200`, `vs_hci` `0x13201100/0x2000`, `unipro` `0x13280000/0x8000`, `ufsp` `0x132a0000/0xa014`; 2 lanes, `dma-coherent` | `F/base-dtbs/06.dts`, `L/zumapro.dtsi` [V] |
| UFS PHY | `phy@13204000` (`google,zumapro-ufs-phy`), `phy-pma` `0x13204000/0x4000`, 38.4 MHz `ufs_ref_clk`, PMU isolation `0x3ec0` via `&pmu_system_controller` | `F/base-dtbs/06.dts`, `L/zumapro.dtsi` [V] |
| UFS sysreg | `syscon@13020000` (`google,zumapro-ufs-sysreg`), IOCC offset `0x710` (`&sysreg_ufs 0x710`) | `F/base-dtbs/06.dts`, `L/zumapro.dtsi`, M1.3 boot [V] |
| UFS clocks | `CMU_HSI2` (`0x13000000`, `google,zumapro-cmu-hsi2`): `CLK_GOUT_UFS_ACLK`, `CLK_GOUT_UFS_UNIPRO`, `CLK_GOUT_UFS_FMP`, `CLK_GOUT_QE_UFS_ACLK`, `CLK_GOUT_QE_UFS_PCLK`, `CLK_GOUT_SYSREG_HSI2` | `L/zumapro.dtsi` [V] |
| UFS pins | `pinctrl_hsi2ufs` (`0x13060000`): `ufs_reset` (`gph5-1`) and `ufs_refclk` (`gph5-0`), function 2 | `L/zumapro.dtsi`, M1.3 boot [V] |
| UFS VCC | Fixed GPIO regulator `"ufs-vcc"` on `gpp0-1` (`pinctrl_peric0` `0x10840000`, `GPIO_ACTIVE_HIGH`, `enable-active-high`) | `F/base-dtbs/06.dts` (`ufs_fixed_vcc: gpio = <0x06 0x01 0x00>`, phandle `0x06` = `gpp0`) [V] |
| LUNs & partitions | 4 data/boot LUNs (`sda`–`sdd`, 62 named partitions total): `sda` holds `persist` (`sda1`), `efs` (`sda5`), `efs_backup` (`sda6`), `modem_userdata` (`sda7`), `trusty_persist` (`sda8`), `trusty_userdata` (`sda9`), `metadata` (`sda10`), slot A (`sda13`–`sda22`), slot B (`sda23`–`sda32`), `super` (`sda33`), `userdata` (`sda34`); `sdb`/`sdc` hold bootloaders (`bl1`, `pbl`, `bl2`, `dram_train`, `abl`, `bl31`, `tzsw`, `gsa`, `gsa_bl1`, `ldfw`, `dpm`, `gcf`); `sdd` holds `devinfo` (`sdd1`), `pinfo` (`sdd2`), `blenv` (`sdd3`), `mfg_data` (`sdd4`) | `R/caiman-stage0-adb/by-name-links.txt` [V] |
| Storage guard allowlist | `UFS_RW="boot_b init_boot_b vendor_boot_b vendor_kernel_boot_b dtbo_b userdata"` (`sda23`–`sda27`, `sda34`); `/dev/sda` whole-disk node removed; `sdb`–`sdd` and all other `sda*` partitions forced `ro=1` | `device/caiman/device.conf`, `initramfs/init` [V] |
| Radio/NV backup list | `NV_PARTS="efs efs_backup modem_userdata persist modem_a modem_b"`, `NV_BACKUP_EXTRA="devinfo metadata trusty_persist trusty_userdata"` | `device/caiman/device.conf`, `R/caiman-stage0-adb/by-name-links.txt` [V] |

## 2. Design

1. **Zero new kernel C code required (`[V]`).** `linux-omarchy-mobile` (`omamobile`) already ships `google,zumapro-ufs` (`drivers/ufs/host/ufs-exynos.c`), `google,zumapro-ufs-phy` (`drivers/phy/samsung/phy-exynos-ufs.c`), `google,zumapro-cmu-hsi2`, and `google,zumapro-pinctrl`, validated on sibling Tensor G4 `zumapro-tegu`. Furthermore, `zumapro-caiman.dts` already enables `&cmu_hsi2`, `&cmu_peric0`, `&pinctrl_hsi2ufs`, `&pinctrl_peric0`, `&sysreg_peric0`, and `&sysreg_ufs` in M1.
2. **Board DTS addition (`zumapro-caiman.dts`).** Include `<dt-bindings/gpio/gpio.h>`, add `ufs_vcc: regulator-ufs-vcc` (`gpp0 1 GPIO_ACTIVE_HIGH`, `enable-active-high`, `regulator-boot-on`, `regulator-always-on`), and enable `&ufs` (`vcc-supply = <&ufs_vcc>`) and `&ufs_phy`.
3. **Read-only first UFS boot (`M2.3`, `gate c`).** Before any boot can touch `userdata`, build the Slot-B images with `DTB_OVERLAYS="ufs-probe"` (`device/caiman/overlays/ufs-probe.dtso`), which appends `omamobile.ufs-probe omamobile.initramfs` to `bootargs`. PID 1 (`/init`) runs the storage guard, writes the full LUN/partition audit to `/run/ufs-probe.txt` and `kmsg`, and stays in the RAM-backed initramfs without running `e2fsck` or `mount` on `userdata`.
4. **Two read-only NV backups (`M2.4`).** With UFS verified read-only in `M2.3`, run `tools/nv-backup -d caiman` over SSH to capture `efs`, `efs_backup`, `modem_userdata`, `persist`, `modem_a`, `modem_b`, `devinfo`, `metadata`, `trusty_persist`, and `trusty_userdata` to `/Volumes/OmarchyMobileWS/android/backups/caiman-nv-<date>` plus a second independent backup copy on `/Volumes/ExtSSD/OmarchyMobile/backups/`, then verify with `tools/nv-backup -d caiman --check`.
5. **Initial device package (`omamobile-device-caiman`, `M2.5`).** Stage the minimal M2 package modeled on `omamobile-device-akita`: `10-omamobile-storage.rules` (hiding `sda` and non-`userdata` partitions from desktop tools), `20-usb-gadget.network` (`172.16.42.1/24`, metric `>700`), `10-omamobile-usb.conf` (keeping NetworkManager off `usb0`), `10-omamobile-power-key.conf`, `10-omamobile.conf` (`SuspendState=freeze`, `MemorySleepMode=s2idle`, no hibernation), `omamobile-mirrorlist`, `omamobile-device-caiman.install`, `reboot-to`, and `device.conf`. Deliberately omits any boot-success marker (`slot-successful:b` stays `no`), radio startup, charger writes, or camera scripts.

## 3. Slot-B Retry Accounting

Because `omamobile-device-caiman` intentionally omits any boot-success marker, ABL decrements `slot-retry-count:b` (from `3` down to `0`) on every Slot-B boot, clean or not `[V]`. Both `bin/omamobile flash` and `tools/install-phone` end with `fastboot --set-active=b`, resetting the counter to `3`. Before a fourth consecutive reboot without flashing, reboot to fastboot (`reboot-to bootloader`) and run `fastboot --set-active=b && fastboot reboot`.

If retries ever reach `0` after `userdata` holds Arch/Omarchy, ABL falls back to Slot A, where stock Android cannot decrypt/mount the ext4 `userdata` partition and offers a recovery factory reset:
- **Decline the factory reset** (accepting erases `userdata`).
- Select **Reboot to bootloader** (or hold Power + Volume Down), run `fastboot --set-active=b && fastboot reboot`.
- If stock Android booted far enough to start its modem stack, take a fresh `tools/nv-backup` into a new directory (keeping earlier backups) before any radio/PMIC/AoC/Trusty work.

## 4. Runbook

Ask the human before every reboot, flash, overlay boot, or `install-phone` write (`AGENTS.md` §1). Keep M1.4's verified build untouched in `out-zumapro-caiman-dts` until `gate b` passes; build Stage 2 in `wt-zumapro-caiman-ufs` / `out-zumapro-caiman-ufs`.

### M2.1 Offline Kernel & Overlay Build (zero hardware risk)
1. Branch `omamobile-zumapro-caiman-ufs` from `omamobile-zumapro-caiman-dts` in worktree `/Volumes/OmarchyMobileWS/omamobile-kernel/wt-zumapro-caiman-ufs`.
2. Add `ufs_vcc`, `&ufs`, and `&ufs_phy` to `zumapro-caiman.dts`.
3. Validate with `scripts/checkpatch.pl --strict -g HEAD`, `CHECK_DTBS=y W=1 exynos/google/zumapro-caiman.dtb`, and `DTC=... bash tests/device-overlays`.
4. Build `Image.gz`, `dtbs`, `modules`, `modules-*.tar.zst`, `initramfs`, and Slot-B images in `out-zumapro-caiman-ufs` with `DTB_OVERLAYS="ufs-probe"` set temporarily for `M2.3`.
- **Pass:** Zero warnings/errors; `fdtdump` on `out-zumapro-caiman-ufs/images/dtb.img` shows `ufs@13200000` (`status = "okay"`), `regulator-ufs-vcc`, and `bootargs` ending in `omamobile.ufs-probe omamobile.initramfs`.

### M2.2 & M2.3 Read-Only UFS Probe Boot (`gate c`)
1. With human approval, run `/usr/local/bin/reboot-to bootloader` (or from fastboot), verify `product: caiman`, `unlocked: yes`, `slot-successful:a: yes`, and flash the 5 `M2.1` `*_b` images (`--set-active=b`).
2. Connect over SSH (`tools/phone-ssh`) / CDC-ACM and inspect `dmesg` and `/run/ufs-probe.txt`.
- **Pass (`gate c`):**
  - `ufs_exynos 13200000.ufs` links cleanly at HS-G4 2 lanes (`FAST series_B G_4 L_2` `[I]`).
  - `/run/ufs-probe.txt` lists `sda`–`sdd` and all 62 partitions matching `R/caiman-stage0-adb/by-name-links.txt` by `PARTNAME` and block node.
  - Every partition outside `UFS_RW` (`sda23`–`sda27`, `sda34`) has `ro=1`; `sdb`, `sdc`, `sdd` have `ro=1`; `/dev/sda` whole-disk device node is absent; nothing is mounted from UFS.
- **Stop if:**
  - Any partition outside `UFS_RW` reports `ro=0` → run `/usr/local/bin/reboot-to bootloader` immediately, touch nothing else, and fix the storage guard before proceeding.
  - UFS link startup fails → save `dmesg`, `reboot-to bootloader`, and inspect `gph5` (`0x13060000`) / `gpp0` (`0x10840000`) single-register read-only `devmem` state.
- **Rollback:** Flash M1.4's `out-zumapro-caiman-dts/images/*_b`, or `fastboot --set-active=a`.

### M2.4 Two Independent Read-Only NV Backups
1. While still in the read-only `M2.3` initramfs over USB SSH (`172.16.42.1`), run:
   ```bash
   tools/nv-backup -d caiman /Volumes/OmarchyMobileWS/android/backups/caiman-nv-$(date +%Y%m%d)
   tools/nv-backup -d caiman --check /Volumes/OmarchyMobileWS/android/backups/caiman-nv-$(date +%Y%m%d)
   ```
2. Copy the verified backup directory (`chmod 700` / `600`) to `/Volumes/ExtSSD/OmarchyMobile/backups/caiman-nv-$(date +%Y%m%d)-copy2` and verify `shasum -a 256 -c SHA256SUMS` in both locations.
- **Pass:** All `NV_PARTS` and `NV_BACKUP_EXTRA` partitions captured read-only and verified `SAME` against live flash. Never share or commit anything from `backups/`.

### M2.5 & M2.6 Persistent Arch Root on `userdata` (`gate d`)
1. Run `packages/omamobile-device-caiman/test/all` offline.
2. Rebuild `out-zumapro-caiman-ufs` images **without** `DTB_OVERLAYS="ufs-probe"` so `/init` hands over to `omamobile-root` on `userdata`.
3. Assemble the test Arch rootfs (`device/caiman/build-u3-root /Volumes/OmarchyMobileWS/omamobile-kernel/out-zumapro-caiman-ufs`).
4. Run `tools/install-phone --dry-run --reinstall --device caiman --bootloader-slots-match ripcurrentpro-17.0-15819938 ...` and inspect the exact fastboot plan.
5. With explicit human approval to erase stock Android's `userdata`, run `tools/install-phone` without `--dry-run`.
- **Pass (`gate d`):**
  - `initramfs` grows `omamobile-root` across `userdata` (`sda34`) and `switch_root`s into Arch Linux ARM.
  - SSH as `root` over `172.16.42.1` succeeds with the installed `ed25519` key.
  - `systemctl is-system-running` reaches `running` (`systemctl --failed` empty).
  - Storage guard holds under systemd/udev: only `UFS_RW` `ro=0`, `sdb`–`sdd` `ro=1`, `/dev/sda` mode `0000` or absent.
  - `reboot-to bootloader` reaches Fastboot Mode cleanly, and a second boot (`fastboot --set-active=b && fastboot reboot`) comes up identically.
- **Stop if:** Any partition outside `UFS_RW` has `ro=0` (`reboot-to bootloader` immediately), or no SSH after 2 minutes (inspect framebuffer console, then Power + Volume Up to reset and Power + Volume Down for fastboot).
- **Rollback:** Flash `M2.3` `ufs-probe` images to stay in initramfs, or `fastboot --set-active=a` (stock Android will then require a factory reset since `userdata` was formatted for Linux).

### M2.7 Full Omarchy Mobile Root Image (`gate e`)
1. Initialize local contributor signing key (`tools/local-key-init caiman`), build local `[omamobile]` packages (`ALARM_CACHE=/Volumes/OmarchyMobileWS/cache/alarm tools/build-packages --local caiman`), and build the full Omarchy Mobile rootfs (`ALARM_CACHE=/Volumes/OmarchyMobileWS/cache/alarm KERNEL_OUT=/Volumes/OmarchyMobileWS/omamobile-kernel/out-zumapro-caiman-ufs tools/build-rootfs --local caiman`).
2. Dry-run and, with human approval, run `tools/install-phone` to `userdata`.
- **Pass (`gate e`):**
  - `omamobile-firstboot` creates the user account, SDDM autologs into Hyprland, and Omarchy's lock screen renders on `simpledrm` at `1280x2856`.
  - Owner SSH login works, `systemctl --failed` is empty, storage guard flags hold, `reboot-to bootloader` works, and `tools/phone-smoke` passes `boot`, `storage guard`, `root`, `kernel health`, `USB`, `display`, `session`, and `lock` (with `GPU` and `touch` expected `not ok` until M4 and M3).

## 5. Results (`2026-11-13` — `gate c`, `M2.4`, `gate d` & `gate e` PASSED)

Kernel commit `33549ee80` (`arm64: dts: exynos: google: zumapro-caiman: enable UFS behind storage guard`, release `7.3.0-rc6-omamobile-push1-g33549ee804eb`):

| Step | Test | Seen on hardware `[V]` | Meaning |
| --- | --- | --- | --- |
| M2.3 | Flash `ufs-probe` Slot-B images (`slot-retry-count:b = 3`) and inspect `/run/ufs-probe.txt` + `dmesg` | `exynos-ufshc 13200000.ufs` linked at `FAST series_B G_4 L_2` (HS-G4, 2 lanes) on the 128 GB Samsung `KLUDG4UHGC-B0E1` (`3303`). `/dev/sda` whole-disk node removed; `sdb`–`sdd` `ro=1`; all 62 partitions matched Stage 0 `by-name`; only `UFS_RW` (`sda23`–`sda27`, `sda34`) `ro=0`; all 56 other partitions `ro=1`; zero UFS mounts; `ufs-ro: guard running` | **`gate c` passed.** UFS 4.0 and the read-only storage guard work as designed |
| M2.4 | `tools/nv-backup -d caiman` + `tools/nv-backup -d caiman --check` + independent second copy | Copied all 10 unmounted read-only partitions (`977 MiB`: `efs`, `efs_backup`, `modem_userdata`, `persist`, `modem_a`, `modem_b`, `devinfo`, `metadata`, `trusty_persist`, `trusty_userdata`); all 10 verified `SAME` against live UFS and `OK` under `shasum -a 256 -c SHA256SUMS` in two independent `chmod 700` backup directories | **M2.4 passed.** Dual verified NV backups stored offline |
| M2.7 (Boot #1) | `tools/install-phone` (`--dry-run`, then live) with `omamobile-rootfs-caiman-2026.11.13-aarch64.img.zst` (`15/15` `tests/rootfs-smoke`) | Flashed the 5 Slot-B boot images + `userdata` (`34/34` sparse chunks in `77.8 s`), `--set-active=b`, rebooted. `/init` grew `omamobile-root` on `/dev/sda34` to `108G` (`99G` free). `omamobile-firstboot` finished `0/SUCCESS` and removed `/etc/omamobile/firstboot.conf`. `s5m-rtc s2mpg14-rtc` set system time at `0.26 s`. SDDM + `uwsm` + Hyprland `0.57.0` + `quickshell` rendered the Omarchy lock screen on `1280x2856@60Hz` (`66x147 mm`, `scale 2.67`), visually confirmed by the owner (`systemd-firstboot.service` failed once on boot #1 because ABL sets `console=null` before `/etc/machine-id` exists) | First boot, `omamobile-firstboot`, owner SSH, and Hyprland lock screen verified |
| M2.7 (Boot #2) | `/usr/bin/reboot-to bootloader` → `fastboot --set-active=b` (`2 → 3`) → `fastboot reboot` → `tools/phone-smoke` | Landed directly in Fastboot Mode; Boot #2 reached `systemctl is-system-running` = `running` with **0 failed units** (`systemd units: ok`). Storage guard held (`62` partitions, `/dev/sda` absent, only `UFS_RW` `ro=0`). `tools/phone-smoke`: `boot` `ok`, `storage guard` `ok`, `root` `ok` (`99G` free), `kernel health` `ok` (`0` oops, `0` WARN), `USB gadget` `ok`, `display` `ok` (`1280x2856`), `session` `ok`, `lock` `ok`, `thermal` `ok` (`45 °C`) | **`gate d` and `gate e` passed** across two consecutive boots (`slot-retry-count:b = 2` tries left) |
