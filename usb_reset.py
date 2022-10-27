#! /usr/bin/env python3
#  -*- coding: utf-8 -*-
#
# This file is part of ofunctions package

"""
Function decorators for threading and antiflooding
Use with @threaded

Versioning semantics:
    Major version: backward compatibility breaking changes
    Minor version: New functionality
    Patch version: Backwards compatible bug fixes

"""

__intname__ = "usb_resetter"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2022 Orsiris de Jong"
__description__ = "USB resetter allows to reset all USB controllers or a single USB device, also emulates lsusb"
__licence__ = "BSD 3 Clause"
__version__ = "1.1.0"
__build__ = "2022102701"
__compat__ = "python2.7+"


from typing import List
import fcntl
import re
import os
import sys
import glob
from argparse import ArgumentParser
from collections import namedtuple


# Equivalent of the _IO('U', 20) constant in the linux kernel.
USBDEVFS_RESET = ord("U") << (4 * 2) | 20


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

    USB_CONTROLLER_PATHS = "/sys/bus/pci/drivers/[uoex]hci_hcd/*:*"

    for usb_ctrl in glob.glob(USB_CONTROLLER_PATHS):
        current_controller = os.path.basename(usb_ctrl)
        controller_basepath = os.path.dirname(usb_ctrl)
        print(
            "Resetting controller {}/{}".format(controller_basepath, current_controller)
        )
        with open(os.path.join(controller_basepath, "unbind"), "w") as unbind:
            unbind.write(current_controller)
        with open(os.path.join(controller_basepath, "bind"), "w") as bind:
            bind.write(current_controller)


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
        return device_paths

    with open(kernel_usb_debug_path, "r") as file_handle:
        first_device = True
        manufacturer = None
        product = None
        found_vendor_id = None
        found_product_id = None
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
                    # print(
                    #    "Found device {}:{} at {} Manufacturer={} Product={}".format(
                    #        found_vendor_id, found_product_id, device_path, manufacturer, product
                    #    )
                    # )
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
                                possible_bus, possible_dev
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


def reset_usb_device(device_path):
    # type: (str) -> bool
    """
    Resets a usb device by dending USBDEVFS_RESET IOCTL to device
    Device path is /dev/bus/usb/[bus_number]/[device_number]
    bus_number and device_number are given by lsusb or else

    Disclaimer
    This is a pyusb emulation that doesn't have dependencies but is more messy
    from usb.core import find as finddev
    finddev(idVendor=0x0665, idProduct=0x5161).reset()
    """

    print("Resetting usb device {}".format(device_path))
    try:
        # Would be easier if os.open would have an __enter__ function for using with context
        fd = os.open(device_path, os.O_WRONLY)
        fcntl.ioctl(fd, USBDEVFS_RESET, 0)
        success = True
    except OSError:
        print("Cannot reset USB device at {}".format(device_path))
        success = False
    finally:
        os.close(fd)
    return success


if __name__ == "__main__":
    parser = ArgumentParser(
        prog=__file__, description="USB ports and devices reset tool"
    )

    parser.add_argument(
        "-d",
        "--devices",
        type=str,
        required=False,
        dest="devices",
        default=None,
        help="comma separated list of devices to reset, eg: '0123:2345,9876:ABCD'",
    )

    parser.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help="Reset all USB controllers",
    )

    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List USB devices and paths",
    )

    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    devices = None
    if args.devices:
        devices = [device.strip() for device in args.devices.split(",")]

    if args.reset:
        reset_usb_controllers()

    if devices:
        for device in devices:
            try:
                vendor_id, product_id = device.split(":")
                paths = get_usb_devices_paths(vendor_id, product_id)
                for path in paths:
                    reset_usb_device(path)
            except ValueError:
                print("Bogus device {} given".format(device))

    if args.list:
        get_usb_devices_paths(list_only=True)
