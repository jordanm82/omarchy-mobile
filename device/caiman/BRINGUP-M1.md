<!-- SPDX-License-Identifier: MIT -->
# caiman M1: first light on Tensor G4 (zumapro)

**Status (2026-11-13):** Stage 0, official OTA Slot-A equalization, bootloader unlock ([NOTES.md](NOTES.md)), M1.1 offline build, M1.2 pre-flash verification, M1.3 first-light Slot-B mainline Linux 7.3.0-rc6 boot (`gate a`), and **M1.4 `1280x2856` boot framebuffer console + `reboot-to bootloader` (`gate b`) are all verified on hardware.**

## Goal

1. Boot our mainline `zumapro-caiman` kernel + shared RAM initramfs from **Slot B** and reach `ssh root@172.16.42.1` over USB NCM (`CONTRIBUTING.md` §5.4 stage 1, gate a).
2. Read the bootloader's handover framebuffer address (`DPP0 RDMA_BASEADDR_P0`) and `DECON0` trigger registers (`GLOBAL_CON`, `TRIG_CON`) once, read-only, on the booted `caiman`, then add `simple-framebuffer` in a separate commit for panel console output (gate b).
3. Keep **Slot A** untouched on stock Android 17 `CP3A.261005.005` (`ripcurrentpro-17.0-15819938`) throughout. Only the five `*_b` boot partitions (`boot_b`, `init_boot_b`, `vendor_boot_b`, `vendor_kernel_boot_b`, `dtbo_b`) are written, and UFS stays disabled in M1 so the kernel never binds storage.

## What caiman inherits from zumapro and zuma

- **Base DTB matching (`/soc_compatible`):** `zumapro`'s ABL matches children of `/soc_compatible` (`product_id`, `major`, `minor`, `pkg_mode`); retail `caiman` boots Base DTB `06` (`A0_FOPLP` and `A1_FOPLP`, `product_id = <0x9875>`, `pkg_mode = <0>`), verified against live `/proc/device-tree/soc_compatible` ([NOTES.md](NOTES.md)).
- **AVB hash footers on `boot` and `init_boot`:** stock `vbmeta.img` (`Flags: 0`) chains `boot` (`0x4000000`) and `init_boot` (`0x800000`) with rollback index `1791158400` and security patch `2026-10-05`; `bin/omamobile images` signs both with AOSP's RSA-4096 test key via `AVB_FOOTERS`.
- **Empty board DTBO (`0x60906` / `0x10000`):** retail `caiman` selects stock `dtbo` entry `49` (`ro.boot.dtbo_idx = 49`), `zumapro-caiman-mp.dts` (`board_id = <0x60906>`, `board_rev = <0x10000>`).
- **USB 2.0 peripheral + S2MPG14 eUSB2 supplies:** `usb@11210000` (`dwc3`), `usbdrd_phy@11100000`, and `usb_hsphy@11110000` powered by `S2MPG14` `ldo8m` (`eusb-vdd`) and `ldo9m` (`eusb-vdda12`) over `acpm_ipc`, matching `zumapro-tegu.dts` and `caiman`'s merged factory DTB (`L8M_USB`, `L9M_USB`).
- **Cluster watchdogs and warm reboot:** `watchdog_cl0@10060000` and `watchdog_cl1@10070000` (`google,zuma-wdt`), lockup/RCU-stall panic detectors (`kernel.config` + `panic=10`), and `syscon-reboot-mode` (`0x0810`) with `reboot=warm`.

## Design

- **Minimal first-light DTS (`zumapro-caiman.dts`):** only identity, `/soc_compatible` (`A0_FOPLP`, `A1_FOPLP`), `zumapro-reserved-memory.dtsi` + `abl@f8800000`, clocks/pinctrl/sysregs, PMU + `reboot_mode`, watchdogs, ACPM + `S2MPG14` (`ldo8m`, `ldo9m`), and USB 2.0 peripheral. UFS, buttons, touch, GPU, panel, audio, and radios stay disabled in M1.
- **No guessed framebuffer or register writes in M1.3:** neither `simple-framebuffer` nor `SIMPLEFB_TRIG_CON` is present in the M1.3 build. Display handover registers (`0x19900040`, `0x19470020`, `0x19470030`) are read once over SSH before adding `simple-framebuffer` in M1.4.

## Risks

- **Silent early boot failure before USB:** `ABL` appends `console=null` and no framebuffer driver is bound in M1.3, so the bootloader's Google splash stays frozen on the panel even when Linux boots cleanly; USB enumeration on the host is the primary signal.
- **Unmarked Slot-B retry budget:** `bin/omamobile flash` activates Slot B without marking `devinfo` successful. Each unmarked Slot-B boot consumes one retry; when retries reach zero, ABL automatically falls back to untouched stock Android on Slot A. Do not mark Slot B successful during M1.
- **USB cable unplug:** without the Type-C port controller driver (`max77779-tcpc`) bound during M1, unplugging the USB-C cable drops the USB2 data switch until the next reboot. Keep the USB cable connected throughout each M1 test.
- **Forced hardware reset:** holding **Power + Volume Up** for ~15–30 s forces a PMIC reset if a hang ever escapes the lockup detectors; holding **Power + Volume Down** then enters Fastboot Mode.

## Gated Runbook

Ask the human before every reboot and flash (`AGENTS.md` §1).

### M1.1 Offline Build & Validation (host/container only)

Build `wt-zumapro-caiman-dts` into `out-zumapro-caiman-dts` inside `omamobile-build:24.04`, pack `initramfs` and `images`, and verify headers, DTBs, and AVB footers with `unpack_bootimg.py`, `avbtool.py`, `mkdtboimg.py`, and `dtc`.

- **Expect / Pass:** `tools/kernel-pr-check` passes `checkpatch --strict` (0 errors) and `W=1` DTB builds (0 new warnings); `zumapro-caiman.dtb` carries `A0_FOPLP` and `A1_FOPLP`; `images/` contains `boot.img` (64 MiB, `SHA256_RSA4096` footer, rollback `1791158400`), `init_boot.img` (8 MiB, `SHA256_RSA4096` footer, `17.0.0` / `2026-10`), `vendor_boot.img` (header v4, page size `0x800`), `vendor_kernel_boot.img` (DTB + initramfs), and `dtbo.img` (`0x60906` / `0x10000`); initramfs packs `UFS_RW` and writes no display register.
- **Stop if:** any build warning, schema/header mismatch, missing `/soc_compatible` match, or unexpected register write file in `/etc/omamobile-simplefb-trig`.
- **Rollback:** none (host files only).
- **Risk:** none.
- **Verified `[V]` (2026-11-12, `7.3.0-rc6-omamobile-push1-gbeb3f7ab6bcf`, `clang-r596125`):**
  - `initramfs`: `/etc/omamobile-ufs-rw` = `boot_b init_boot_b vendor_boot_b vendor_kernel_boot_b dtbo_b userdata`, `/etc/omamobile-usb-product` = `Pixel 9 Pro`, `/etc/omamobile-simplefb-trig` absent, static `aarch64` `devmem` + `reboot-to`, and SSH `authorized_keys` present.
  - `boot.img` (`67,108,864` B, SHA-256 `f35adc0d0902a9db7f20c5ddbfeb1f183fbbfc5dc76b789454b71588d8e9e6a9`): header v4, `Image.lz4` (`18,462,535` B), AVB `SHA256_RSA4096` footer (`rollback_index = 1791158400`, `os_version = 17`, `security_patch = 2026-10-05`).
  - `init_boot.img` (`8,388,608` B, SHA-256 `51a29b2a0d48efd6412f47e818f62b7c69416c5f9e175c2a7400bb8b0686d474`): header v4, empty ramdisk (`512` B), `17.0.0` / `2026-10`, AVB `SHA256_RSA4096` footer (`rollback_index = 1791158400`, `os_version = 17`, `security_patch = 2026-10-05`).
  - `vendor_boot.img` (`8,192` B, SHA-256 `6d79c689c9d7d4622c908604e2a5501365c9b7d5e72f1e7dc464f0e2a8713757`): header v4, page size `0x800`, empty ramdisk (`512` B), cmdline `console=tty0 clk_ignore_unused pd_ignore_unused printk.devkmsg=on bootconfig`.
  - `vendor_kernel_boot.img` (`6,815,744` B, SHA-256 `ecabd307faca61ca595f00437d006ac98ede6cc1c39a18520f4690afcee835ac`): header v4, page size `0x800`, `dtb.img` (`45,875` B, `/soc_compatible` `A0_FOPLP` + `A1_FOPLP`) + `initramfs.cpio.lz4` (`6,677,605` B).
  - `dtbo.img` (`4,096` B, SHA-256 `3b59c0228b1c7c20bf29e9ac4a5678f2f80f935e712a2fcea326e437ec4c8829`): 1 entry, `id = 0x00060906`, `rev = 0x00010000`.

### M1.2 Pre-Flash Verification (read-only phone check)

1. Confirm SSH key `/Volumes/OmarchyMobileWS/ssh/id_ed25519.pub` is packed into `initramfs`'s `/root/.ssh/authorized_keys`.
2. With human approval, run `adb -d reboot bootloader` and check named `fastboot getvar` values:
   - `product: caiman`
   - `version-bootloader: ripcurrentpro-17.0-15819938`
   - `current-slot: a`
   - `slot-successful:a: yes`, `slot-unbootable:a: no`
   - `unlocked: yes`
- **Expect / Pass:** all values match above; single fastboot device attached.
- **Stop if:** `slot-successful:a` is not `yes`, `slot-unbootable:a` is `yes`, `unlocked` is `no`, or bootloader version differs.
- **Rollback:** `fastboot reboot` returns immediately to stock Android on Slot A.
- **Risk:** low (read-only fastboot queries).
- **Verified `[V]` (2026-11-12):** single device in fastboot; `product: caiman`, `version-bootloader: ripcurrentpro-17.0-15819938`, `current-slot: a`, `slot-successful:a: yes`, `slot-unbootable:a: no`, `slot-retry-count:a: 2`, `unlocked: yes`.

### M1.3 First Boot on Slot B (gate a: USB NCM + SSH)

With explicit human approval, flash only the five `*_b` partitions from `out-zumapro-caiman-dts/images` and set Slot B active:

```sh
fastboot flash boot_b "$IMG/boot.img"
fastboot flash init_boot_b "$IMG/init_boot.img"
fastboot flash vendor_boot_b "$IMG/vendor_boot.img"
fastboot flash vendor_kernel_boot_b "$IMG/vendor_kernel_boot.img"
fastboot flash dtbo_b "$IMG/dtbo.img"
fastboot --set-active=b
fastboot reboot
```

Once macOS enumerates the `Pixel 9 Pro` USB NCM network interface, assign `172.16.42.2/24` on that interface, verify `ping -c 2 172.16.42.1`, and connect via `tools/phone-ssh`.

- **Expect / Pass:** USB NCM gadget enumerates within ~30 s; `tools/phone-ssh uname -a` prints `7.3.0-rc6-...`; all 8 CPUs are online; `dmesg` shows both `google,zuma-wdt` watchdogs bound and no `reserved-memory` overlap; the phone stays up past 90 s (beyond ABL's ~60–80 s watchdog window). Save sanitized `dmesg`, `/proc/iomem`, and `/sys/firmware/fdt` to private `reference/` storage on `ExtSSD`. Then, while the Google splash is still visible on the panel, read **once each, read-only (one argument only)**:
  - `/usr/local/bin/devmem 0x19900040` (`DPP0 RDMA_BASEADDR_P0`)
  - `/usr/local/bin/devmem 0x19470020` (`DECON0 GLOBAL_CON`)
  - `/usr/local/bin/devmem 0x19470030` (`DECON0 TRIG_CON`)
- **Stop if:** no USB gadget appears within 2 minutes, SSH drops around ~60–80 s (watchdog reset), or the panel has gone blank before the `devmem` reads. If unresponsive, hold **Power + Volume Up** (15–30 s) then **Power + Volume Down** for Fastboot Mode, or let Slot B's retries exhaust back to stock Slot A.
- **Rollback:** `fastboot --set-active=a && fastboot reboot` restores untouched stock Android 17 on Slot A immediately.
- **Risk:** medium (first mainline boot on `caiman`; bounded strictly to `*_b` with UFS disabled).
- **Verified `[V]` (2026-11-12, `7.3.0-rc6-omamobile-push1-gbeb3f7ab6bcf`):**
  - Flashed `boot_b`, `init_boot_b`, `vendor_boot_b`, `vendor_kernel_boot_b`, `dtbo_b`; verified `current-slot: b`, `slot-successful:a: yes`, `slot-unbootable:a: no`, `slot-successful:b: no`, `slot-retry-count:b: 3`, and rebooted.
  - USB gadget enumerated on `11210000.usb` at `0.238 s` (`udc` state `configured`, CDC-ACM root console `/dev/cu.usbmodemomamobile3` live on macOS in 22 s).
  - `uname -a`: `Linux omamobile 7.3.0-rc6-omamobile-push1-gbeb3f7ab6bcf #1 SMP PREEMPT`; `nproc=8` (all 8 CPUs started at `EL2`, `kvm [1]: Hyp nVHE mode initialized successfully`); `ramoops` bound `0x400000@0xfd3ff000`; `10060000.watchdog` and `10070000.watchdog` bound cleanly; `exynos-acpm-protocol` initialized 16 channels; `s2mpg14-rtc` registered as `rtc0`; no `/sys/block/sd*` exposed; zero errors or `reserved-memory` overlaps in `dmesg`; remained stable past `257 s` uptime.
  - Sanitized `dmesg.txt`, `iomem.txt`, `interrupts.txt`, `proc.txt`, and `live.dtb` saved to private `reference/caiman-m1-boot1/`.
  - Single-argument read-only `devmem` handover reads with splash visible on panel:
    - `0x19900040` (`DPP0 RDMA_BASEADDR_P0`) = `0xfac00000`
    - `0x19470020` (`DECON0 GLOBAL_CON`) = `0x00000133`
    - `0x19470030` (`DECON0 TRIG_CON`) = `0x00003070`

### M1.4 Framebuffer Console on Panel (gate b)

Using the exact handover address and `TRIG_CON` value measured in M1.3:
1. Add `cont_splash_mem` (`no-map`) and `simple-framebuffer` (`1280x2856`, `a8r8g8b8`, stride `1280 * 4`) in a separate commit on `omamobile-zumapro-caiman-dts`.
2. If `TRIG_CON` (`0x19470030`) read masked at handover (`0x3070`), set `SIMPLEFB_TRIG_CON="0x19470030 0x3061"` in `device/caiman/device.conf`.
3. Rebuild `kernel`, `initramfs`, and `images`, then with human approval reboot to Fastboot Mode (`tools/phone-ssh /usr/local/bin/reboot-to bootloader`, simultaneously testing `reboot=warm` + `syscon-reboot-mode`) and flash the updated `*_b` images.

- **Expect / Pass:** `reboot-to bootloader` lands directly in Fastboot Mode; after flashing M1.4, the panel displays the initramfs console lines (`first light`, `USB gadget up`, `ssh`, `ready`) cleanly at `1280x2856` and SSH comes up at `172.16.42.1`.
- **Stop if:** panel stays frozen on the Google logo with SSH up, garbled stride/geometry appears, or USB fails to enumerate.
- **Rollback:** revert `SIMPLEFB_TRIG_CON` / M1.4 commit, or `fastboot --set-active=a && fastboot reboot` back to stock Slot A.
- **Risk:** low (single `COMPATIBLE`-gated `TRIG_CON` write cleared on any reset).
- **Verified `[V]` (2026-11-13, `7.3.0-rc6-omamobile-push1-gd24dfc66819c`):**
  - `/usr/local/bin/reboot-to bootloader` landed directly in Fastboot Mode (`fastboot devices`).
  - Flashed `boot_b`, `init_boot_b`, `vendor_boot_b`, `vendor_kernel_boot_b`, `dtbo_b`; `slot-successful:a: yes`, `slot-unbootable:a: no`, `slot-retry-count:b: 3`.
  - `OF: reserved mem: 0x00000000fac00000..0x00000000fb9f1fff (14280 KiB) nomap non-reusable splash@fac00000`; `simpledrm` bound `chosen:framebuffer` as `fb0` (`1280x2856`); single-argument read-only `devmem 0x19470030` = `0x00003061`; Linux console lines rendered cleanly on the OLED panel; stable past `3,295 s` uptime with zero kernel errors or warnings.
