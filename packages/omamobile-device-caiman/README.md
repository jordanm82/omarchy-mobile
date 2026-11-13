# omamobile-device-caiman

Omarchy Mobile's initial userspace package for the Google Pixel 9 Pro (`caiman`, Tensor G4 / `zumapro`). It hides Android partitions from desktop tools, keeps the USB gadget network address across `switch_root`, configures `s2idle`-only suspend, and configures pacman's `[omamobile]` repository. It deliberately does not mark a boot slot successful (`slot-successful:b` remains `no`), and does not touch the radio, charger, or cameras.

| Path | Installs to | What it does |
| --- | --- | --- |
| `vendor/udev/rules.d/10-omamobile-storage.rules` | `/usr/lib/udev/rules.d` | Hides `sda` and every Android partition except `userdata` from desktop tools (matching `omamobile-device-cheetah`). Kernel block `ro=1` flags remain set from the initramfs storage guard ([BRINGUP-M2](../../device/caiman/BRINGUP-M2.md)) |
| `vendor/systemd/network/20-usb-gadget.network` | `/usr/lib/systemd/network` | Sets `usb0` to `172.16.42.1/24` after handover as the last-resort gateway (`Metric` > 700, matching `omamobile-device-husky`) |
| `vendor/systemd/logind.conf.d/10-omamobile-power-key.conf` | `/usr/lib/systemd/logind.conf.d` | Prevents a short power-button press from powering the phone off (`omamobile-device-cheetah`) |
| `vendor/NetworkManager/conf.d/10-omamobile-usb.conf` | `/usr/lib/NetworkManager/conf.d` | Keeps NetworkManager off `usb0` (`omamobile-device-husky`) |
| `vendor/systemd/sleep.conf.d/10-omamobile.conf` | `/usr/lib/systemd/sleep.conf.d` | Forces `SuspendState=freeze` and `MemorySleepMode=s2idle`, with hibernation disabled (`omamobile-device-cheetah`) |
| `etc/omamobile-mirrorlist` | `/etc/pacman.d/omamobile-mirrorlist` | Configures where pacman finds `[omamobile]` (`omamobile-device-cheetah`) |
| `omamobile-device-caiman.install` | pacman hook | Adds `[omamobile]` before `[omarchy]` in `pacman.conf` once and preserves local channel selection (`omamobile-device-cheetah`) |
| `src/reboot-to.c` | `/usr/bin/reboot-to` | Reboots with a reason understood by `syscon-reboot-mode` (`reboot-to bootloader` reaches Fastboot Mode) |
| `device.conf` | `/usr/share/omamobile/device.conf` | Device descriptor matching `device/caiman/device.conf` |

`./build [DIR]` compiles `reboot-to`, `./install DESTDIR [DIR]` stages the package tree, and `test/all` verifies all scripts, staged paths, and upstream file parity.
