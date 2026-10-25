import unittest
from unittest.mock import patch

from system.network import (
    LocalAddressUnavailable,
    WifiAddressUnavailable,
    _select_wifi_ipv4,
    get_active_local_ipv4,
)


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


class ActiveLocalAddressTests(unittest.TestCase):
    def test_uses_address_selected_by_active_route(self):
        socket_instance = unittest.mock.MagicMock()
        socket_instance.getsockname.return_value = ("192.168.1.42", 0)
        socket_factory = unittest.mock.MagicMock()
        socket_factory.return_value.__enter__.return_value = socket_instance

        with patch("system.network.socket.socket", socket_factory):
            self.assertEqual(get_active_local_ipv4(), "192.168.1.42")

        socket_instance.connect.assert_called_once_with(("8.8.8.8", 80))

    def test_falls_back_to_resolved_private_address(self):
        socket_factory = unittest.mock.MagicMock()
        socket_factory.return_value.__enter__.side_effect = OSError("No route")
        resolved = [
            (None, None, None, None, ("127.0.0.1", 0)),
            (None, None, None, None, ("10.0.0.25", 0)),
        ]

        with patch("system.network.socket.socket", socket_factory), patch(
            "system.network.socket.getaddrinfo", return_value=resolved
        ):
            self.assertEqual(get_active_local_ipv4(), "10.0.0.25")

    def test_raises_when_no_usable_address_exists(self):
        socket_factory = unittest.mock.MagicMock()
        socket_factory.return_value.__enter__.side_effect = OSError("No route")
        resolved = [(None, None, None, None, ("127.0.0.1", 0))]

        with patch("system.network.socket.socket", socket_factory), patch(
            "system.network.socket.getaddrinfo", return_value=resolved
        ):
            with self.assertRaises(LocalAddressUnavailable):
                get_active_local_ipv4()
