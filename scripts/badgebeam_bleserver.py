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


class Advertisement(dbus.service.Object):
    def __init__(self, bus, index, advertising_type):
        self.path = f'/org/bluez/example/advertisement{index}'
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = [BADGE_SERVICE_UUID]
        self.local_name = 'BeagleBadge'
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            'org.bluez.LEAdvertisement1': {
                'Type': self.ad_type,
                'ServiceUUIDs': dbus.Array(self.service_uuids, signature='s'),
                'LocalName': dbus.String(self.local_name),
                'Discoverable': dbus.Boolean(True)
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        return {self.path: self.get_properties()}

    @dbus.service.method('org.bluez.LEAdvertisement1')
    def Release(self):
        pass

def register_app_cb():
    print('GATT application registered')

def register_app_error_cb(error):
    print(f'Failed to register application: {error}')
    sys.exit(1)

def register_ad_cb():
    print('Advertisement registered')

def register_ad_error_cb(error):
    print(f'Failed to register advertisement: {error}')
    sys.exit(1)

def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()

    for o, props in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in props:
            return dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, o), LE_ADVERTISING_MANAGER_IFACE), \
                   dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, o), GATT_MANAGER_IFACE), \
                   dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, o), 'org.freedesktop.DBus.Properties')
    return None, None, None

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    ad_manager, gatt_manager, adapter_props = find_adapter(bus)
    if not ad_manager:
        print('LEAdvertisingManager1 interface not found')
        return

    # Ensure power is on
    adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(1))

    app = Application(bus)
    gatt_manager.RegisterApplication(app.get_path(), {},
                                    reply_handler=register_app_cb,
                                    error_handler=register_app_error_cb)

    ad = Advertisement(bus, 0, 'peripheral')
    ad_manager.RegisterAdvertisement(ad.get_path(), {},
                                     reply_handler=register_ad_cb,
                                     error_handler=register_ad_error_cb)

    print("BadgeBeam BLE Profile started.")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nExiting")

if __name__ == '__main__':
    main()
