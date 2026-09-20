"""Short OUI → vendor table for survey labels (not a full IEEE database)."""

from __future__ import annotations

OUI_VENDORS = {
    "00000c": "Cisco",
    "001a2f": "Cisco",
    "001b0d": "Cisco",
    "002414": "Cisco",
    "00156d": "Ubiquiti",
    "f09fc2": "Ubiquiti",
    "00259": "Supermicro",
    "002590": "Supermicro",
    "0017c8": "Kyocera",
    "3c22fb": "Apple",
    "f01898": "Apple",
    "acde48": "Apple",
    "001b21": "Intel",
    "a4c3f0": "Samsung",
    "8c8590": "Apple",
    "b827eb": "Raspberry Pi",
    "dca632": "Raspberry Pi",
    "001122": "Cisco",
    "000c29": "VMware",
    "0050c2": "IEEE Registration",
    "e45f01": "Raspberry Pi",
    "dc4a3e": "Hewlett Packard",
    "001e14": "Cisco",
    "00226b": "Cisco-Linksys",
    "00e04c": "Realtek",
    "d8eb97": "TRENDnet",
}


def vendor_from_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    hexed = mac.replace(":", "").replace("-", "").replace(".", "").lower()
    if len(hexed) < 6:
        return None
    return OUI_VENDORS.get(hexed[:6]) or OUI_VENDORS.get(hexed[:5])
