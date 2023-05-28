#! /usr/bin/env python3
#  -*- coding: utf-8 -*-
#

"""
usb reset devices & reinit (power cycle) hubs (ports)

Versioning semantics:
    Major version: backward compatibility breaking changes
    Minor version: New functionality
    Patch version: Backwards compatible bug fixes

"""

__intname__ = "usb_resetter"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2022-2023 Orsiris de Jong - NetInvent SASU"
__description__ = "USB resetter allows to reset all USB controllers or a single USB device, also emulates lsusb"
__licence__ = "BSD 3 Clause"
__version__ = "1.3.2"
__build__ = "2023052801"
__url__ = "https://github.com/netinvent/usb_resetter"
__compat__ = "python2.7+"


from typing import List
import fcntl
import re
import os
import sys
import glob
import argparse
from collections import namedtuple


if not "linux" in sys.platform:
    print("This script can only run on Linux")
    sys.exit(3)


# linux/usbdevice_fs.h equivalents
# #define USBDEVFS_RESET             _IO('U', 20)
# Basically we want to send 01010101 00010100
# ord("U") == 85 == 01010101 which we shift to the left by 8 then add 20 == 00010100
USBDEVFS_RESET = ord("U") << 8 | 20
USBDEVFS_DISCONNECT = ord("U") << 8 | 22
USBDEVFS_CONNECT = ord("U") << 8 | 23

# Glob style path to USB contollers including USB3
USB_CONTROLLER_PATHS = "/sys/bus/pci/drivers/[uoex]hci_hcd/*:*"


def hub_binder(hub_path, action):
    """
    bind or unbind a usb hub / controller
    path: full path to usb hub / controller

    Unbinding / binding is equivalent to a cold restart, but real usb power cannot be cut
    The device will still get power, but will not be able to talk to the computer

    action: bind|unbind
    """
    current_hub = os.path.basename(hub_path)
    basepath = os.path.dirname(hub_path)

    pci_unbind_path = "/sys/bus/pci/drivers"
    usb_unbind_path = "/sys/bus/usb/drivers/usb"

    # In case we get a /sys/bus/usb/device instead of a /sys/bus/usb/drivers path
    if basepath.startswith(pci_unbind_path) or basepath.startswith(usb_unbind_path):
        unbind_path = basepath
    else:
        unbind_path = usb_unbind_path

    print("{} hub {}/{}".format(action, basepath, current_hub))
    with open(os.path.join(unbind_path, action), "w") as file_handle:
        file_handle.write(current_hub)


def get_usb_hubs(vendor_id=None, product_id=None):
    """
    Get physical location of usb hub where given product is plugged in
    vendor_id and product_id are optional filters
    """

    hubs = []

    for entry in glob.glob("/sys/bus/usb/devices/**/idVendor"):
        hub_path = os.path.dirname(entry)
        abs_hub_path = os.path.abspath(hub_path)
        vendor_id_file = os.path.join(abs_hub_path, "idVendor")
        product_id_file = os.path.join(abs_hub_path, "idProduct")

        try:
            with open(vendor_id_file, "r") as file_handle:
                found_vendor_id = file_handle.read().strip()
            with open(product_id_file, "r") as file_handle:
                found_product_id = file_handle.read().strip()

            if (
                vendor_id == found_vendor_id
                and product_id == found_product_id
                or (not vendor_id and not product_id)
            ):
                hubs.append(hub_path)
        except OSError:
            print(
                "Cannot identify which vendor/product is plugged in hub {}".format(
                    hub_path
                )
            )

    return hubs


def list_usb_hubs(vendor_id=None, product_id=None):
    """
    vendor_id and product_id are optional filters
    """
    for hub in get_usb_hubs(vendor_id, product_id):
        print("Found hub {}".format(hub))


def reset_usb_hubs(hubs):
    for hub in hubs:
        hub_binder(hub, "unbind")
        hub_binder(hub, "bind")


def reset_usb_controllers():
    # type: () -> None
    """
    Allows to reset all USB controllers from a machine

    Reimplements the following bash script:

    for i in /sys/bus/pci/drivers/[uoex]hci_hcd/*:*; do
      [ -e "$i" ] || continue
      echo "Resetting ${i%/*}/${i##*/}"
      echo "${i##*/}" > "${i%/*}/unbind"
      echo "${i##*/}" > "${i%/*}/bind"
    done
    """
    reset_usb_hubs(glob.glob(USB_CONTROLLER_PATHS))


def get_usb_devices_paths(vendor_id=None, product_id=None, list_only=False):
    # type: (str, str, bool) -> List[str]
    """
    Emulates lsusb by reading from /sys/kernel/debug/usb/devices
    Does not require lsusb to be installed and should work on a fair share of recent kernels
    """

    found_devices = []
    device_paths = []
    Device = namedtuple(
        "Devices", "vendor_id, product_id, device_path, manufacturer, product"
    )
    kernel_usb_debug_path = "/sys/kernel/debug/usb/devices"  # see https://wiki.debian.org/HowToIdentifyADevice/USB

    if not os.path.isfile(kernel_usb_debug_path):
        # We could fallback to lsusb here if available, but then we need command_runner to deal with different subprocess.communicate outputs
        raise OSError(
            "Kernel path {} not found. Please run this script as root".format(
                kernel_usb_debug_path
            )
        )

    with open(kernel_usb_debug_path, "r", encoding="utf-8") as file_handle:
        first_device = True
        manufacturer = None
        product = None
        found_vendor_id = None
        found_product_id = None
        device_path = None
        while True:
            line = file_handle.readline()
            if not line:
                break
            match = re.match(r"T:\s+Bus=(\d+).*Dev#=\s+(\d+)", line, re.IGNORECASE)
            if match:
                if not first_device:
                    # New device (begins with T:), let's reset previous values that belong to earlier found devices
                    found_devices.append(
                        Device(
                            vendor_id=found_vendor_id,
                            product_id=found_product_id,
                            device_path=device_path,
                            manufacturer=manufacturer,
                            product=product,
                        )
                    )
                else:
                    first_device = False
                    manufacturer = None
                    product = None
                    found_vendor_id = None
                    found_product_id = None

                # bus and dev are always 3 digit numbers, ex 001, 003, 004
                bus = "{:03d}".format(int(match.group(1)))
                dev = "{:03d}".format(int(match.group(2)))
            match = re.match(r"S:\s+Manufacturer=(.*)", line, re.IGNORECASE)
            if match:
                manufacturer = match.group(1)
            match = re.match(r"S:\s+Product=(.*)", line, re.IGNORECASE)
            if match:
                product = match.group(1)
            match = re.match(
                r"P:\s+Vendor=([0-9A-F]{4})\s+ProdID=([0-9A-F]{4})", line, re.IGNORECASE
            )
            if match:
                found_vendor_id = match.group(1)
                found_product_id = match.group(2)
                device_path = os.path.join("/dev/bus/usb", bus, dev)
                if vendor_id == found_vendor_id and product_id == found_product_id:
                    if os.path.exists(device_path):
                        device_paths.append(device_path)
                    else:
                        print(
                            "Device path not existing for bus {} dev {}".format(
                                bus, dev
                            )
                        )
    # We need to add the final device if exists:
    if bus and dev:
        found_devices.append(
            Device(
                vendor_id=found_vendor_id,
                product_id=found_product_id,
                device_path=device_path,
                manufacturer=manufacturer,
                product=product,
            )
        )

    if list_only:
        for device in found_devices:
            print("Found device %s:%s at %s Manufacturer=%s, Product=%s" % device)
    return device_paths


def send_signal_usb_device(device_path, signal):
    # type: (str, str) -> bool
    """
    Resets a usb device by dending USBDEVFS_RESET IOCTL to device
    Device path is /dev/bus/usb/[bus_number]/[device_number]
    bus_number and device_number are given by lsusb or else
    signal = reset|connect|disconnect


    Disclaimer
    This is a pyusb emulation that doesn't have dependencies but is more messy, and allows sending disconnect/connect on top of reset commands
    from usb.core import find as finddev
    finddev(idVendor=0x0665, idProduct=0x5161).reset()
    """

    if signal == "reset":
        sig = USBDEVFS_RESET
    elif signal == "disconnect":
        sig = USBDEVFS_DISCONNECT
    elif signal == "connect":
        sig = USBDEVFS_CONNECT
    else:
        raise TypeError("Bad USB signal given")

    print("Sending signal {} to usb device {}".format(signal, device_path))
    try:
        # Would be easier if os.open would have an __enter__ function for using with context
        fd = os.open(device_path, os.O_WRONLY)
        fcntl.ioctl(fd, sig, 0)
        success = True
    except OSError:
        print("Cannot {} USB device at {}".format(signal, device_path))
        success = False
    finally:
        os.close(fd)
    return success


def interface():
    description = (
        "USB hub / controllers & devices reset tool v{}\n"
        "{}\n"
        "PRs are welcome - {}\n".format(__version__, __copyright__, __url__)
    )
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
    )

    parser.add_argument(
        "-l",
        "--list",
        dest="list",
        action="store_true",
        help="List USB devices and paths",
    )

    parser.add_argument(
        "--list-hubs",
        action="store_true",
        help="Print a list of detected USB hubs. If --device is given, list only hubs on which device is connected",
    )

    parser.add_argument(
        "-d",
        "--device",
        type=str,
        required=False,
        dest="device",
        default=None,
        help="Device for which we want to execute an action. Requires vendor_id:product_id format. Example: 8086:0001",
    )

    parser.add_argument(
        "--hub",
        type=str,
        required=False,
        dest="hub",
        default=None,
        help="Full path of hub on which to perform hub actions",
    )

    parser.add_argument(
        "--reset-device",
        dest="reset_device",
        action="store_true",
        help="Reset device given by --device",
    )

    parser.add_argument(
        "--connect-device",
        dest="connect_device",
        action="store_true",
        help="Connect device given by --device",
    )

    parser.add_argument(
        "--disconnect-device",
        dest="disconnect_device",
        action="store_true",
        help="Disconnect device given by --device",
    )

    parser.add_argument(
        "-r",
        "--reset-all",
        dest="reset_all",
        action="store_true",
        help="Reset all USB controllers, including their dependent hubs and devices",
    )

    parser.add_argument(
        "--reset-hub",
        dest="reset_hub",
        action="store_true",
        help="Reset hubs given by --hub switch, or hubs on which device given by --device is connected",
    )

    parser.add_argument(
        "--disable-hub",
        dest="disable_hub",
        action="store_true",
        help="Disable hub given by --hub switch, or hubs on which device given by --device is connected",
    )

    parser.add_argument(
        "--enable-hub",
        dest="enable_hub",
        action="store_true",
        help="Enable hub given by --hub switch, or hubs on which device given by --device is connected",
    )

    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    vendor_id = None
    product_id = None

    if args.reset_all:
        reset_usb_controllers()

    if args.device:
        try:
            vendor_id, product_id = args.device.split(":")
        except (TypeError, ValueError):
            print("Bogus device {} given.".format(args.device))
            sys.exit(2)

    if (
        args.reset_device
        or args.disconnect_device
        or args.connect_device
        or args.disable_hub
        or args.enable_hub
        or args.reset_hub
    ):
        if args.reset_device or args.disconnect_device or args.connect_device:
            paths = get_usb_devices_paths(vendor_id, product_id)
            for path in paths:
                if args.reset_device:
                    send_signal_usb_device(path, "reset")
                if args.connect_device:
                    send_signal_usb_device(path, "connect")
                if args.disconnect_device:
                    send_signal_usb_device(path, "disconnect")
        else:
            if args.hub:
                hubs = [args.hub]
            else:
                hubs = get_usb_hubs(vendor_id, product_id)
            if args.disable_hub:
                for hub in hubs:
                    hub_binder(hub, "unbind")
            if args.enable_hub:
                for hub in hubs:
                    hub_binder(hub, "bind")
            if args.reset_hub:
                reset_usb_hubs(hubs)

    if args.list:
        get_usb_devices_paths(list_only=True)

    if args.list_hubs:
        list_usb_hubs(vendor_id, product_id)


def main():
    try:
        interface()
    except KeyboardInterrupt:
        print("Program interrupted by CTRL+C")
        sys.exit(200)
    except Exception as exc:
        print("Program failed with error %s" % exc)
        # We'll keep exit code consistent
        sys.exit(201)


if __name__ == "__main__":
    main()
