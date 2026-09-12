"""Tests for pyowershades protocol."""

import struct

import pytest

from pyowershades import (
    OP_GET_DEBUG_INFO,
    OP_GET_DEVICE_ID,
    OP_GET_STATUS,
    StatusReply,
    battery_percentage,
    build_json_test_payload,
    build_packet,
    build_set_limit_payload,
    build_set_name_payload,
    build_set_position_payload,
    parse_debug_info_reply,
    parse_device_id_reply,
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


def test_build_json_test_payload() -> None:
    payload = build_json_test_payload('{"foo": 1}')
    assert len(payload) == 1016
    assert payload.startswith(b'{"foo": 1}')


def test_build_json_test_payload_truncates_long_text() -> None:
    payload = build_json_test_payload("A" * 2000)
    assert len(payload) == 1016


def test_parse_debug_info_reply_real_capture() -> None:
    # Captured from a real PoE shade sitting fully open at its top limit.
    payload = bytes.fromhex(
        "07000000000000affb2f640064000000f22a0000f22a0000a0060000f22a000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010001"
    )
    pkt = build_packet(OP_GET_DEBUG_INFO, payload=payload)
    result = parse_debug_info_reply(pkt)
    assert result is not None
    assert result.battery_mv == 12283
    assert result.current_percent == 100
    assert result.hall_count == result.end_stop_top
    assert result.motor_duty_cycle == 0
    assert result.io_poe_status is True


def test_parse_debug_info_reply_wrong_op() -> None:
    pkt = build_packet(0x99, payload=b"\x01")
    assert parse_debug_info_reply(pkt) is None


def test_parse_debug_info_reply_too_short() -> None:
    pkt = build_packet(OP_GET_DEBUG_INFO, payload=b"\x00" * 10)
    assert parse_debug_info_reply(pkt) is None


def test_parse_device_id_reply_real_capture() -> None:
    # Captured from the same shade - firmware rev 109 active, rev 97 idle.
    payload = bytes.fromhex(
        "0002000000000000000061006d00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    )
    pkt = build_packet(OP_GET_DEVICE_ID, payload=payload)
    result = parse_device_id_reply(pkt)
    assert result is not None
    assert result.low_rev == 97
    assert result.high_rev == 109
    assert result.status_bits & 3 == 2  # high_rev bank is active
    assert result.dhcp_enabled is False


def test_parse_device_id_reply_wrong_op() -> None:
    pkt = build_packet(0x99, payload=b"\x01")
    assert parse_device_id_reply(pkt) is None


def test_parse_device_id_reply_too_short() -> None:
    pkt = build_packet(OP_GET_DEVICE_ID, payload=b"\x00" * 10)
    assert parse_device_id_reply(pkt) is None
