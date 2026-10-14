import unittest

from system.network import WifiAddressUnavailable, _select_wifi_ipv4


class WifiAddressTests(unittest.TestCase):
    def test_wifi_address_ignores_ethernet_and_virtual_adapters(self):
        adapters = [
            (6, 1, ["192.168.0.12"]),
            (71, 1, ["192.168.1.25"]),
            (71, 1, ["192.168.1.99"]),
        ]

        self.assertEqual(_select_wifi_ipv4(adapters), "192.168.1.25")

    def test_wifi_address_requires_active_wifi_with_usable_ipv4(self):
        adapters = [
            (71, 2, ["192.168.1.25"]),
            (71, 1, ["169.254.2.10", "127.0.0.1"]),
            (6, 1, ["10.0.0.5"]),
        ]

        with self.assertRaisesRegex(WifiAddressUnavailable, "No active Wi-Fi adapter"):
            _select_wifi_ipv4(adapters)
