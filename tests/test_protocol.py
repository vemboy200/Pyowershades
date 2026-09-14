"""Tests for pyowershades protocol."""

import struct

import pytest

from pyowershades import (
    ADMIN_ACCESS_KEY,
    ADMIN_ACCESS_PAYLOAD,
    DISABLE_TCP_CLOUD,
    OP_DISABLES,
    OP_GET_DEBUG_INFO,
    OP_GET_DEVICE_ID,
    OP_GET_STATUS,
    OP_POE_MOTOR_PARAMS,
    StatusReply,
    battery_percentage,
    build_json_test_payload,
    build_packet,
    build_set_disables_payload,
    build_set_limit_payload,
    build_set_motor_speed_payload_gen1,
    build_set_name_payload,
    build_set_position_payload,
    parse_debug_info_reply,
    parse_device_id_reply,
    parse_disables_reply,
    parse_error_list,
    parse_motor_parameters_reply,
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
    from pyowershades import LIMIT_LOWER, LIMIT_UPPER

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
    assert result.error_list == []  # device had no logged errors


def test_parse_error_list_empty() -> None:
    assert parse_error_list(b"\x00" * 50) == []


def test_parse_error_list_single_code() -> None:
    raw = b"9," + b"\x00" * 48
    assert parse_error_list(raw) == [9]


def test_parse_error_list_multiple_codes() -> None:
    raw = b"9,21,33," + b"\x00" * 42
    assert parse_error_list(raw) == [9, 21, 33]


def test_parse_error_list_ignores_malformed_tokens() -> None:
    raw = b"9,,abc,21," + b"\x00" * 40
    assert parse_error_list(raw) == [9, 21]


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


def test_parse_disables_reply_tcp_cloud_enabled() -> None:
    pkt = build_packet(OP_DISABLES, payload=bytes([0x01]))
    result = parse_disables_reply(pkt)
    assert result is not None
    assert result.raw == 0x01
    assert result.tcp_cloud_disabled is False


def test_parse_disables_reply_tcp_cloud_disabled() -> None:
    pkt = build_packet(OP_DISABLES, payload=bytes([0x01 | DISABLE_TCP_CLOUD]))
    result = parse_disables_reply(pkt)
    assert result is not None
    assert result.raw == 0x41
    assert result.tcp_cloud_disabled is True


def test_parse_disables_reply_wrong_op() -> None:
    pkt = build_packet(0x99, payload=bytes([0x01]))
    assert parse_disables_reply(pkt) is None


def test_parse_disables_reply_too_short() -> None:
    pkt = build_packet(OP_DISABLES, payload=b"")
    assert parse_disables_reply(pkt) is None


def test_build_set_disables_payload_sets_bit_preserving_others() -> None:
    # bit2 (PCB button disable) already set alongside the always-on bit0
    current = 0x01 | 0x04
    payload = build_set_disables_payload(current, tcp_cloud_disabled=True)
    assert payload == bytes([current | DISABLE_TCP_CLOUD])


def test_build_set_disables_payload_clears_bit_preserving_others() -> None:
    current = 0x01 | 0x04 | DISABLE_TCP_CLOUD
    payload = build_set_disables_payload(current, tcp_cloud_disabled=False)
    assert payload == bytes([0x01 | 0x04])


def test_admin_access_payload_is_the_fixed_key() -> None:
    assert ADMIN_ACCESS_PAYLOAD == struct.pack("<I", ADMIN_ACCESS_KEY)


def _motor_params_reply_packet(
    *,
    speed_control_enable: int = 0,
    slow_down_target_input: int = 99,
    computer_motor_power_tolerance: int = 2,
    jog_dot_power_decel: int = 100,
    jog_dot_power: int = 100,
    desired_rpm_up: int = 75,
    desired_rpm_up_decel: int = 45,
    computer_motor_power_time_up: int = 25,
    computer_motor_power_time_up_decel: int = 15,
    motor_power_up: int = 100,
    motor_power_up_decel: int = 100,
    desired_rpm_down: int = 75,
    desired_rpm_down_decel: int = 45,
    computer_motor_power_time_down: int = 25,
    computer_motor_power_time_down_decel: int = 15,
    motor_power_down: int = 100,
    motor_power_down_decel: int = 100,
    soft_stop_delay: int = 3,
    soft_stop_enable: int = 0,
) -> bytes:
    """Build a reply packet matching the real, compact reply shape: a
    1-byte leading flag (0 on a real Get reply) followed by the 19-field
    struct, with no SoftStopDecelCounts/Time (see MotorParametersReply's
    docstring for why the real device doesn't send those two)."""
    payload = b"\x00" + struct.pack(
        "<3BhhIIHHhhIIHHhhBB",
        speed_control_enable,
        slow_down_target_input,
        computer_motor_power_tolerance,
        jog_dot_power_decel,
        jog_dot_power,
        desired_rpm_up,
        desired_rpm_up_decel,
        computer_motor_power_time_up,
        computer_motor_power_time_up_decel,
        motor_power_up,
        motor_power_up_decel,
        desired_rpm_down,
        desired_rpm_down_decel,
        computer_motor_power_time_down,
        computer_motor_power_time_down_decel,
        motor_power_down,
        motor_power_down_decel,
        soft_stop_delay,
        soft_stop_enable,
    )
    return build_packet(OP_POE_MOTOR_PARAMS, payload=payload)


def test_parse_motor_parameters_reply() -> None:
    pkt = _motor_params_reply_packet(
        speed_control_enable=1, desired_rpm_up=60, desired_rpm_down=55
    )
    result = parse_motor_parameters_reply(pkt)
    assert result is not None
    assert result.speed_control_enable is True
    assert result.desired_rpm_up == 60
    assert result.desired_rpm_down == 55
    assert result.soft_stop_delay == 3


def test_parse_motor_parameters_reply_matches_real_capture_defaults() -> None:
    """The helper's defaults are the exact values decoded from a real
    capture (2026-09-13, Gen 1 hardware, still at factory settings)."""
    pkt = _motor_params_reply_packet()
    result = parse_motor_parameters_reply(pkt)
    assert result is not None
    assert result.speed_control_enable is False
    assert result.slow_down_target_input == 99
    assert result.computer_motor_power_tolerance == 2
    assert result.desired_rpm_up == 75
    assert result.desired_rpm_up_decel == 45
    assert result.motor_power_up == 100  # matches the maintainer's own screenshot
    assert result.desired_rpm_down == 75
    assert result.motor_power_down == 100
    assert result.soft_stop_enable is False


def test_parse_motor_parameters_reply_wrong_op() -> None:
    pkt = build_packet(0x99, payload=b"\x00" * 42)
    assert parse_motor_parameters_reply(pkt) is None


def test_parse_motor_parameters_reply_too_short() -> None:
    pkt = build_packet(OP_POE_MOTOR_PARAMS, payload=b"\x00" * 10)
    assert parse_motor_parameters_reply(pkt) is None


def _unpack_set_payload(payload: bytes) -> tuple:
    """Unpack a Set PoE Motor Parameters payload directly - this is the
    46-byte outgoing struct (with ParamType), a different shape than
    what parse_motor_parameters_reply expects for an incoming reply."""
    return struct.unpack("<4BhhIIHHhhIIHHhhBBHH", payload)


def test_build_set_motor_speed_payload_gen1_sets_power_both_directions() -> None:
    payload = build_set_motor_speed_payload_gen1(70)
    fields = _unpack_set_payload(payload)

    assert fields[0] == 1  # ParamType: Set
    motor_power_up = fields[10]
    motor_power_down = fields[16]
    jog_dot_power_decel = fields[4]
    jog_dot_power = fields[5]
    assert motor_power_up == 70
    assert motor_power_down == 70
    assert jog_dot_power == 70
    assert jog_dot_power_decel == 70


def test_build_set_motor_speed_payload_gen1_matches_vendor_fixed_template() -> None:
    """Every field the vendor's own Gen 1 code hardcodes, not just the
    speed value, must match exactly - Gen 1 discards whatever was
    previously configured, confirmed byte-for-byte from frmMain.cs."""
    payload = build_set_motor_speed_payload_gen1(100)
    fields = _unpack_set_payload(payload)
    assert fields[0] == 1  # ParamType: Set
    (
        _param_type,
        speed_control_enable,
        slow_down_target_input,
        computer_motor_power_tolerance,
        _jog_dot_power_decel,
        _jog_dot_power,
        desired_rpm_up,
        _desired_rpm_up_decel,
        _computer_motor_power_time_up,
        _computer_motor_power_time_up_decel,
        _motor_power_up,
        motor_power_up_decel,
        desired_rpm_down,
        _desired_rpm_down_decel,
        _computer_motor_power_time_down,
        _computer_motor_power_time_down_decel,
        _motor_power_down,
        motor_power_down_decel,
        soft_stop_delay,
        soft_stop_enable,
        soft_stop_decel_counts,
        soft_stop_decel_time,
    ) = fields

    assert speed_control_enable == 0
    assert slow_down_target_input == 99
    assert computer_motor_power_tolerance == 2
    assert desired_rpm_up == 75
    assert desired_rpm_down == 75
    assert motor_power_up_decel == 50
    assert motor_power_down_decel == 50
    assert soft_stop_enable == 0
    assert soft_stop_delay == 0
    assert soft_stop_decel_counts == 0
    assert soft_stop_decel_time == 0


def test_build_set_motor_speed_payload_gen1_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="40 and 100"):
        build_set_motor_speed_payload_gen1(39)
    with pytest.raises(ValueError, match="40 and 100"):
        build_set_motor_speed_payload_gen1(101)
