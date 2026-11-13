# omamobile-device-caiman

Omarchy Mobile's userspace package for the Google Pixel 9 Pro (`caiman`, Tensor G4 / `zumapro`). It hides Android partitions from desktop tools, keeps the USB gadget network address across `switch_root`, configures `s2idle`-only suspend, loads `panthor`, `gs_decon`, `cs40l26_vibra`, `leds_lm3644`, `max77779_battery`, `hci_uart`, and `nxp_nci_i2c` hang-safely before the display manager with GPU ACPM DVFS capped at `890 MHz` and `120 Hz` panel timers gated behind `gs_dsim_cmd.allow_tx`, adds charge-limit, torch, feedbackd, and Bluetooth address rules, protects `modules-push` trees from Arch cleanup, and configures pacman's `[omamobile]` repository. It deliberately does not mark a boot slot successful (`slot-successful:b` remains `no`), and does not touch the modem, Wi-Fi, or cameras.

| Path | Installs to | What it does |
| --- | --- | --- |
| `bin/omamobile-caiman-graphics-start` | `/usr/bin` | Hang-safe loader for GPU (`panthor`), display (`gs_decon` + `allow_tx=1` for `google-cm4`), haptics (`cs40l26_vibra`), torch (`leds_lm3644`), battery gauge (`max77779_battery`), Bluetooth (`hci_uart`), and NFC (`nxp_nci_i2c`) |
| `bin/omamobile-bt-addr` | `/usr/bin` | Programs the Bluetooth controller MAC from `/proc/device-tree/chosen/config/bt_addr` via `btmgmt` |
| `bin/omamobile-caiman-charge-limit` | `/usr/bin` | Applies `/etc/omamobile/charge-limit` (1–100%) to `max77779-charger` via `charge_control_end_threshold` or `charge_behaviour` hysteresis |
| `vendor/modprobe.d/omamobile-caiman-guards.conf` | `/usr/lib/modprobe.d` | Blacklists `panthor`, `gs_decon`, `cs40l26_vibra`, `leds_lm3644`, `max77779_battery`, `hci_uart`, and `nxp_nci_i2c` autoload so only the hang-safe start loads them |
| `vendor/modprobe.d/omamobile-caiman-clk-acpm.conf` | `/usr/lib/modprobe.d` | Sets `clk_acpm.zumapro_gpu_max_khz=890000` for GPU ACPM DVFS up to `890 MHz` |
| `vendor/modprobe.d/omamobile-caiman-display.conf` | `/usr/lib/modprobe.d` | Configures `gs_decon` `max_refresh=120 screen_off=2` for 120 Hz refresh and panel sleep on DPMS off |
| `vendor/systemd/system/omamobile-caiman-graphics.service` | `/usr/lib/systemd/system` | Oneshot unit enabled via `multi-user.target.wants`, ordered before `display-manager.service` |
| `vendor/systemd/system/omamobile-bt-addr@.service` | `/usr/lib/systemd/system` | Oneshot unit started by udev to apply `/chosen/config/bt_addr` when an `hciN` adapter appears |
| `vendor/systemd/system/display-manager.service.d/10-omamobile-caiman.conf` | `/usr/lib/systemd/system/display-manager.service.d` | Orders SDDM after `omamobile-caiman-graphics.service` |
| `vendor/systemd/system/linux-modules-cleanup.service.d/10-omamobile-caiman.conf` | `/usr/lib/systemd/system/linux-modules-cleanup.service.d` | Disables Arch `linux-modules-cleanup.service` while `device-caiman/version` exists so `modules-push` trees survive reboots |
| `uwsm/env.d/omamobile-caiman-graphics` | `/usr/share/uwsm/env.d` | Exports `AQ_DRM_DEVICES` and switches between hardware GL (`renderD128` + marker) and `llvmpipe` fallback |
| `vendor/udev/rules.d/10-omamobile-storage.rules` | `/usr/lib/udev/rules.d` | Hides `sda` and every Android partition except `userdata` from desktop tools (matching `omamobile-device-cheetah`). Kernel block `ro=1` flags remain set from the initramfs storage guard ([BRINGUP-M2](../../device/caiman/BRINGUP-M2.md)) |
| `vendor/udev/rules.d/20-omamobile-torch.rules` | `/usr/lib/udev/rules.d` | Grants the `video` group write access to `/sys/.../white:torch/brightness` (`lm3644`) |
| `vendor/udev/rules.d/72-omamobile-feedbackd.rules` | `/usr/lib/udev/rules.d` | Tags `cs40l26_vibra` input events with `uaccess` and `FEEDBACKD_TYPE=vibra` for `feedbackd` |
| `vendor/udev/rules.d/75-omamobile-caiman-charger.rules` | `/usr/lib/udev/rules.d` | Runs `omamobile-caiman-charge-limit` on `max77779-charger` add and `max77779-battery` change |
| `vendor/udev/rules.d/80-omamobile-bt-addr.rules` | `/usr/lib/udev/rules.d` | Starts `omamobile-bt-addr@%k.service` when `hci_uart_bcm` registers an HCI adapter |
| `vendor/systemd/network/20-usb-gadget.network` | `/usr/lib/systemd/network` | Sets `usb0` to `172.16.42.1/24` after handover as the last-resort gateway (`Metric` > 700, matching `omamobile-device-husky`) |
| `vendor/systemd/logind.conf.d/10-omamobile-power-key.conf` | `/usr/lib/systemd/logind.conf.d` | Prevents a short power-button press from powering the phone off (`omamobile-device-cheetah`) |
| `vendor/NetworkManager/conf.d/10-omamobile-usb.conf` | `/usr/lib/NetworkManager/conf.d` | Keeps NetworkManager off `usb0` (`omamobile-device-husky`) |
| `vendor/systemd/sleep.conf.d/10-omamobile.conf` | `/usr/lib/systemd/sleep.conf.d` | Forces `SuspendState=freeze` and `MemorySleepMode=s2idle`, with hibernation disabled (`omamobile-device-cheetah`) |
| `etc/omamobile-mirrorlist` | `/etc/pacman.d/omamobile-mirrorlist` | Configures where pacman finds `[omamobile]` (`omamobile-device-cheetah`) |
| `omamobile-device-caiman.install` | pacman hook | Adds `[omamobile]` before `[omarchy]` in `pacman.conf` once and preserves local channel selection (`omamobile-device-cheetah`) |
| `src/reboot-to.c` | `/usr/bin/reboot-to` | Reboots with a reason understood by `syscon-reboot-mode` (`reboot-to bootloader` reaches Fastboot Mode) |
| `device.conf` | `/usr/share/omamobile/device.conf` | Device descriptor matching `device/caiman/device.conf` |

`./build [DIR]` compiles `reboot-to`, `./install DESTDIR [DIR]` stages the package tree, and `test/all` verifies all scripts, staged paths, hang-guard logic, and upstream file parity.
