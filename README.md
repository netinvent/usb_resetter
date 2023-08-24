# usb_resetter
small tool to reset USB controllers, hubs or devices

## So here we are, with sh*TTY built usb devices, that don't work properly.

I've had numerous problems with USB devices that simply don't work unless you disconnect / reconnect them.
While I'd probably like to throw away those devices, sometimes there's no choice than the rejoice of using those devices.

A couple solutions:

1. Buy a robot hand that unplugs / plugs the device :) - Nice solution but costly... But again, very nice...
2. Reset the USB device (works sometimes)
3. Reset the USB hub where the device is plugged in (is generally sufficient)
4. Reset all USB controllers (a bit broad, but works miracles on reluctant devices)
5. Burn the device and promise to buy better hardware (also very nice solution)

I've scripted solutions 2 to 4 in order to achieve what I need into a Python script.

## Setup

Grab yourself a copy of `usb_resetter` via pypi with `pip install usb_resetter` or download via

```
curl -o /usr/local/bin/usb_resetter -L https://raw.githubusercontent.com/netinvent/usb_resetter/main/usb_resetter/usb_resetter.py && chmod +x /usr/local/bin/usb_resetter
```

## Usage

### List all USB devices
```
usb_resetter -l
```
Result
```
Found device 1d6b:0002 at /dev/bus/usb/001/001 Manufacturer=Linux 5.14.0-70.26.1.el9_0.x86_64 xhci-hcd, Product=xHCI Host Controller
Found device 0665:5161 at /dev/bus/usb/001/002 Manufacturer=INNO TECH, Product=USB to Serial
Found device 1d6b:0003 at /dev/bus/usb/002/001 Manufacturer=Linux 5.14.0-70.26.1.el9_0.x86_64 xhci-hcd, Product=xHCI Host Controller
Found device 1199:9071 at /dev/bus/usb/002/002 Manufacturer=Sierra Wireless, Incorporated, Product=EM7455
```


### Reset a reluctant USB device

```
usb_resetter -d [vendor_id]:[product_id] --reset-device
```
Example:
```
usb_resetter -d 1199:9071 --reset-device
```

Result:
```
Resetting usb device /dev/bus/usb/002/002
```

### Reset the USB hub where a device is connected in
```
usb_resetter -d [vendor_id]:[product_id] --reset-hub
```
Example:
```
usb_resetter -d 1199:9071 --reset-hub
```

Result:
```
unbind hub /sys/bus/usb/devices/2-4
bind hub /sys/bus/usb/devices/2-4
```

### Reset hubs without vendor / device ids

You can also reset a hub without knowing the device VID:PID.
List the hubs and then select the ones to reset
```
usb_resetter -l
usb_resetter --reset-hub --hub /dev/bus/usb/001/002
```

### Reset the whole USB controller (usually makes reluctant devices work again)
```
usb_resetter --reset-all
```

Result
``` 
unbind hub /sys/bus/pci/drivers/xhci_hcd/0000:00:14.0
bind hub /sys/bus/pci/drivers/xhci_hcd/0000:00:14.0
```

Afterwards, all your USB devices should work as if they were just plugged in, since this reset also temporarily cuts power from given USB device, making it reboot.

## Usual suspect: Cypress Semiconductor USB to Serial UPS

These cheap USB UPS have always the same kind of unreliable USB to serial interface.
Most of them use `blazer_usb` driver from NUT, and sometimes the driver can't start because it can't communicate with the UPS. Guess why ? No idea.

Unplugging and plugging the USB port usually fixes this, but that's not handy.

A simple USB device reset isn't sufficient for that one.

We'll need to reset the hub it's attached to.

The command for doing so is:
```
usb_resetter --reset-hub --device 0665:5161
```

While I have a couple of machines running NUT, I modified the nut-driver.service file to automatically reset the device before trying to load the driver:

In `/etc/systemd/system/nut-driver.service` I added line
```
ExecStartPre=/usr/local/bin/usb_resetter --reset-hub --device 0665:5161
```
