import ctypes
import ipaddress
import socket
from ctypes import wintypes


_IF_TYPE_IEEE80211 = 71
_IF_OPER_STATUS_UP = 1
_ERROR_BUFFER_OVERFLOW = 111


class WifiAddressUnavailable(RuntimeError):
    """Raised when no usable IPv4 address belongs to an active Wi-Fi adapter."""


class LocalAddressUnavailable(RuntimeError):
    """Raised when no usable local IPv4 address can be determined."""


class _SocketAddress(ctypes.Structure):
    _fields_ = [
        ("sockaddr", ctypes.c_void_p),
        ("sockaddr_length", ctypes.c_int),
    ]


class _AdapterUnicastAddress(ctypes.Structure):
    pass


_AdapterUnicastAddressPointer = ctypes.POINTER(_AdapterUnicastAddress)
_AdapterUnicastAddress._fields_ = [
    ("length", wintypes.ULONG),
    ("flags", wintypes.DWORD),
    ("next", _AdapterUnicastAddressPointer),
    ("address", _SocketAddress),
]


class _AdapterAddresses(ctypes.Structure):
    pass


_AdapterAddressesPointer = ctypes.POINTER(_AdapterAddresses)
_AdapterAddresses._fields_ = [
    ("length", wintypes.ULONG),
    ("if_index", wintypes.DWORD),
    ("next", _AdapterAddressesPointer),
    ("adapter_name", ctypes.c_char_p),
    ("first_unicast_address", _AdapterUnicastAddressPointer),
    ("first_anycast_address", ctypes.c_void_p),
    ("first_multicast_address", ctypes.c_void_p),
    ("first_dns_server_address", ctypes.c_void_p),
    ("dns_suffix", wintypes.LPWSTR),
    ("description", wintypes.LPWSTR),
    ("friendly_name", wintypes.LPWSTR),
    ("physical_address", ctypes.c_ubyte * 8),
    ("physical_address_length", wintypes.DWORD),
    ("flags", wintypes.DWORD),
    ("mtu", wintypes.DWORD),
    ("if_type", wintypes.DWORD),
    ("oper_status", wintypes.DWORD),
    ("ipv6_if_index", wintypes.DWORD),
    ("zone_indices", wintypes.DWORD * 16),
    ("first_prefix", ctypes.c_void_p),
]


class _SockaddrIn(ctypes.Structure):
    _fields_ = [
        ("family", wintypes.USHORT),
        ("port", wintypes.USHORT),
        ("address", ctypes.c_ubyte * 4),
        ("zero", ctypes.c_ubyte * 8),
    ]


def _windows_ipv4_adapters():
    if not hasattr(ctypes, "WinDLL"):
        raise WifiAddressUnavailable(
            "Wi-Fi adapter detection is currently supported only on Windows."
        )

    iphlpapi = ctypes.WinDLL("iphlpapi")
    get_adapters = iphlpapi.GetAdaptersAddresses
    get_adapters.argtypes = [
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        _AdapterAddressesPointer,
        ctypes.POINTER(wintypes.ULONG),
    ]
    get_adapters.restype = wintypes.ULONG

    buffer_size = wintypes.ULONG(15 * 1024)
    for _ in range(3):
        buffer = ctypes.create_string_buffer(buffer_size.value)
        adapters = ctypes.cast(buffer, _AdapterAddressesPointer)
        result = get_adapters(
            socket.AF_INET, 0, None, adapters, ctypes.byref(buffer_size)
        )
        if result == _ERROR_BUFFER_OVERFLOW:
            continue
        if result != 0:
            raise OSError(result, ctypes.FormatError(result))
        break
    else:
        raise OSError(_ERROR_BUFFER_OVERFLOW, "Network adapter list kept changing")

    entries = []
    adapter = adapters
    while adapter:
        addresses = []
        unicast = adapter.contents.first_unicast_address
        while unicast:
            address = unicast.contents.address
            if address.sockaddr and address.sockaddr_length >= ctypes.sizeof(_SockaddrIn):
                sockaddr = ctypes.cast(address.sockaddr, ctypes.POINTER(_SockaddrIn)).contents
                if sockaddr.family == socket.AF_INET:
                    addresses.append(socket.inet_ntoa(bytes(sockaddr.address)))
            unicast = unicast.contents.next
        entries.append((adapter.contents.if_type, adapter.contents.oper_status, addresses))
        adapter = adapter.contents.next
    return entries


def _select_wifi_ipv4(adapters):
    for if_type, oper_status, addresses in adapters:
        if if_type != _IF_TYPE_IEEE80211 or oper_status != _IF_OPER_STATUS_UP:
            continue
        for address in addresses:
            parsed = ipaddress.IPv4Address(address)
            if not (parsed.is_loopback or parsed.is_link_local or parsed.is_unspecified or parsed.is_multicast):
                return str(parsed)
    raise WifiAddressUnavailable(
        "No active Wi-Fi adapter with a usable IPv4 address was found. "
        "Connect this computer to Wi-Fi and generate a new pairing QR code."
    )


def get_active_wifi_ipv4():
    """Return an IPv4 address from an operational 802.11 adapter, never Ethernet."""
    return _select_wifi_ipv4(_windows_ipv4_adapters())


def get_active_local_ipv4():
    """Return the IPv4 address selected by the system's active network route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route_socket:
            route_socket.connect(("8.8.8.8", 80))
            route_ip = route_socket.getsockname()[0]
            parsed = ipaddress.IPv4Address(route_ip)
            if not (parsed.is_loopback or parsed.is_link_local or parsed.is_unspecified or parsed.is_multicast):
                return str(parsed)
    except OSError:
        pass

    candidates = []
    try:
        addresses = socket.getaddrinfo(
            socket.gethostname(), None, family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        for address in addresses:
            ip = ipaddress.IPv4Address(address[4][0])
            if not (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast):
                candidates.append(ip)
    except OSError:
        pass

    private_addresses = [ip for ip in candidates if ip.is_private]
    if private_addresses:
        return str(private_addresses[0])
    if candidates:
        return str(candidates[0])
    raise LocalAddressUnavailable("No active network interface with a usable IPv4 address was found.")
