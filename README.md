# usb_resetter
small tool to reset USB controllers or devices

## So here we are, with sh*TTY built usb devices, that don't work properly.

I've had numerous problems with USB devices that simply don't work unless you disconnect / reconnect them.
While I'd probably like to throw away those devices, sometimes there's no choice than the rejoice of using those devices.

Three solutions:

1. Buy a robot hand that unplugs / plugs the device :) - Nice solution but costly... But again, very nice...
2. Reset the USB device (works sometimes)
3. Reset all USB controllers (a bit broad, but works miracles on reluctant devices)

I've scripted solutions 2 and 3 in order to achieve what I need into a Python script.

## Setup

Grab yourself a copy of `usb_reset.py` on the release page or download via

```
curl -o /usr/local/bin/usb_reset.py -L https://raw.githubusercontent.com/netinvent/usb_resetter/main/usb_reset.py && chmod +x /usr/local/bin/usb_reset.py
```

## Usage

### List all USB devices
```
usb_reset.py -l
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
usb_reset.py -d [vendor_id]:[product_id]
```
Example:
```
usb_reset.py -d 1199:9071
```

Result:
```
Resetting usb device /dev/bus/usb/002/002
```


### Reset the whole USB controller (usually makes reluctant devices work again)
```
usb_reset --reset
```

Result
``` 
Resetting controller /sys/bus/pci/drivers/xhci_hcd/0000:00:14.0
```

Afterwards, all your USB devices should work as if they were just plugged in, since this reset also temporarily cuts power from given USB device, making it reboot.
