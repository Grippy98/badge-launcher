#!/usr/bin/env python3
import sys
import os
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# We use standard BlueZ dbus constants
BLUEZ_SERVICE_NAME = 'org.bluez'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'

BADGE_SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
DISPLAY_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef1'

# The path to write the 15,000 byte payload
PAYLOAD_DIR = "/opt/badge_launcher/applications/apps/badgebeam"
PAYLOAD_PATH = os.path.join(PAYLOAD_DIR, "latest.bin")

buffer_cache = bytearray()

class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        self.add_service(BadgeService(bus, 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response

class Service(dbus.service.Object):
    def __init__(self, bus, index, uuid, primary):
        self.path = f'/org/bluez/example/service{index}'
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array([c.get_path() for c in self.characteristics], signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristics(self):
        return self.characteristics

class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + f'/char{index}'
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

class BadgeService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, BADGE_SERVICE_UUID, True)
        self.add_characteristic(DisplayCharacteristic(bus, 0, self))

class DisplayCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, DISPLAY_CHAR_UUID, ['write', 'write-without-response'], service)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        # We don't support reading
        return []

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        global buffer_cache
        bytes_val = bytes(value)
        
        # If we got a large chunk starting 15000 byte sequence, OR
        # if the buffer is somehow > 15000, we clear it.
        # But commonly we just append until we hit 15000 bytes.
        
        buffer_cache.extend(bytes_val)
        
        if len(buffer_cache) == 15000:
            # We have a full image!
            print("Received full 15,000 byte image payload!")
            try:
                os.makedirs(PAYLOAD_DIR, exist_ok=True)
                with open(PAYLOAD_PATH, 'wb') as f:
                    f.write(buffer_cache)
                print("Payload written successfully to", PAYLOAD_PATH)
            except Exception as e:
                print("Error writing payload:", e)
            
            # Reset cache for next image
            buffer_cache = bytearray()
        elif len(buffer_cache) > 15000:
            print(f"Warning: Buffer overrun {len(buffer_cache)}. Resetting.")
            # We missed the exact boundary, start over with this chunk
            buffer_cache = bytearray(bytes_val)


    # We NO LONGER register an Advertisement via BlueZ because BlueZ 5.82
    # incorrectly attempts to wrap it in an unsupported Extended Advertising Opcode
    # which causes the CC33xx firmware to silently drop the packet.
    # Advertising is handled cleanly via our custom legacy badgebeam_hcid.sh script.

    print("BadgeBeam BLE Profile started.")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nExiting")

if __name__ == '__main__':
    main()
