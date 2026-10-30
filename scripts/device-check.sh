#!/bin/sh
# Read-only inspection; run on the HANDHELD via SSH, never source firmware config.
set -u
printf 'Kernel / architecture: '
uname -smr
if [ -r /proc/device-tree/model ]; then
  printf 'Device model: '
  tr -d '\000' < /proc/device-tree/model
  printf '\n'
fi
printf '\nOS release:\n'
cat /etc/os-release 2>/dev/null || true
printf '\nMemory:\n'
sed -n '1,3p' /proc/meminfo
printf '\nStorage:\n'
df -h /mnt/mmc /mnt/sdcard /userdata /roms /roms2 2>/dev/null || true
printf '\nGraphics devices:\n'
ls -ld /dev/dri /dev/dri/* /dev/mali* /dev/fb* 2>/dev/null || true
printf '\nPortMaster candidates:\n'
for path in /opt/muos/PortMaster /opt/system/Tools/PortMaster /opt/tools/PortMaster /roms/ports/PortMaster /mnt/mmc/ports/PortMaster /mnt/mmc/Roms/APPS/PortMaster /mnt/mmc/ROMS/APPS/PortMaster /userdata/system/.local/share/PortMaster; do
  if [ -d "$path" ]; then
    printf '%s\n' "$path"
    ls -l "$path/control.txt" "$path/runtimes/love_11.5/love.aarch64" "$path/libs/weston_pkg_0.2.squashfs" 2>/dev/null || true
  fi
done
