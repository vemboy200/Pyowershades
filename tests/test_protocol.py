"""Tests for pyowershades protocol."""

import struct

import pytest

from pyowershades import (
    OP_GET_STATUS,
    StatusReply,
    battery_percentage,
    build_packet,
    build_set_limit_payload,
    build_set_name_payload,
    build_set_position_payload,
    parse_serial_reply,
    parse_shade_name_reply,
    parse_status_reply,
)
from pyowershades.protocol import (
    HEADER_SIZE,
    PacketHeader,
    parse_header,
    verify_packet,
)


def test_build_packet_no_payload() -> None:
    pkt = build_packet(0x01)
    assert len(pkt) == HEADER_SIZE
    assert pkt[4] == 0x01  # op byte


def test_build_and_verify_packet() -> None:
    pkt = build_packet(0x05, payload=b"\x01\x02\x03")
    assert verify_packet(pkt)


def test_verify_packet_rejects_truncated() -> None:
    pkt = build_packet(0x05, payload=b"\x01\x02\x03")
    assert not verify_packet(pkt[:-1])


def test_verify_packet_rejects_corrupted_crc() -> None:
    pkt = bytearray(build_packet(0x05, payload=b"\xab"))
    pkt[2] ^= 0xFF  # flip CRC bytes
    assert not verify_packet(bytes(pkt))


def test_parse_header_roundtrip() -> None:
    pkt = build_packet(0x07, sequence=3, channel=1)
    header = parse_header(pkt)
    assert isinstance(header, PacketHeader)
    assert header.op == 0x07
    assert header.sequence == 3
    assert header.channel == 1


def test_parse_header_too_short() -> None:
    assert parse_header(b"\x00\x01\x02") is None


def test_build_set_position_payload() -> None:
    payload = build_set_position_payload(75)
    mask, percent, tilt, channel_mask = struct.unpack("<HhhI", payload)
    assert percent == 75
    assert mask == 0x0001
    assert tilt == 0


def test_build_set_limit_payload() -> None:
    from pyowershades import LIMIT_UPPER, LIMIT_LOWER

    upper = build_set_limit_payload(LIMIT_UPPER)
    lower = build_set_limit_payload(LIMIT_LOWER)
    assert upper != lower
    assert len(upper) == 2
    assert len(lower) == 2


def test_build_set_name_payload() -> None:
    payload = build_set_name_payload("Bedroom")
    assert payload[0:1] == b"\x01"  # set flag
    assert b"Bedroom" in payload
    assert len(payload) == 51  # 1 flag + 50 name bytes


def test_build_set_name_payload_truncates_long_name() -> None:
    payload = build_set_name_payload("A" * 100)
    assert len(payload) == 51


def _make_status_packet(position: int, battery_mv: int) -> bytes:
    payload = struct.pack(
        "<hhHHIIIhII",
        position,
        0,  # tilt
        0,  # memory
        battery_mv,
        0,  # time
        0,  # cycles
        0,  # stalls
        0,  # temperature
        0,  # raw_percent
        0,  # raw_tilt
    )
    return build_packet(OP_GET_STATUS, payload=payload)


def test_parse_status_reply() -> None:
    pkt = _make_status_packet(position=50, battery_mv=3800)
    result = parse_status_reply(pkt)
    assert isinstance(result, StatusReply)
    assert result.position == 50
    assert result.battery_mv == 3800


def test_parse_status_reply_out_of_range_position() -> None:
    pkt = _make_status_packet(position=255, battery_mv=3800)
    result = parse_status_reply(pkt)
    assert result is not None
    assert result.position is None


def test_parse_status_reply_wrong_op() -> None:
    pkt = build_packet(0x99)
    assert parse_status_reply(pkt) is None


def test_parse_status_reply_too_short() -> None:
    pkt = build_packet(OP_GET_STATUS, payload=b"\x00" * 5)
    assert parse_status_reply(pkt) is None


def test_parse_serial_reply() -> None:
    payload = struct.pack("<BBBBIIB", 2, 0, 0, 0, 12345, 0, 1)
    payload = payload.ljust(24 - HEADER_SIZE, b"\x00")
    pkt = build_packet(0x02, payload=payload)
    result = parse_serial_reply(pkt)
    assert result is not None
    assert result["model"] == 2
    assert result["serial"] == 12345
    assert result["dhcp_enabled"] is True


def test_parse_serial_reply_too_short() -> None:
    assert parse_serial_reply(b"\x00" * 10) is None


def test_parse_shade_name_reply() -> None:
    name = b"Living Room"
    payload = b"\x00" + name.ljust(50, b"\x00")
    pkt = build_packet(0x10, payload=payload)
    assert parse_shade_name_reply(pkt) == "Living Room"


def test_parse_shade_name_reply_empty() -> None:
    payload = b"\x00" + b"\x00" * 50
    pkt = build_packet(0x10, payload=payload)
    assert parse_shade_name_reply(pkt) is None


@pytest.mark.parametrize(
    ("mv", "expected"),
    [
        (None, None),
        (2500, 0),
        (3000, 0),
        (3600, 50),
        (4200, 100),
        (5000, 100),
    ],
)
def test_battery_percentage(mv: int | None, expected: int | None) -> None:
    assert battery_percentage(mv) == expected
