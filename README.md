# Pyowershades

Pyowershades is an asyncio Python library for communicating with [PowerShades](https://powershades.com) motorized shade controllers over UDP. It handles connection management, packet building and parsing, device discovery, and asynchronous status push callbacks. While orginally developed for use in Home Assistant it can work for any asyncio application.

## Requirements

- Python 3.12+

## Installation

```bash
pip install pyowershades
```

## Usage

### Discover devices on the network

```python
import asyncio
from pyowershades import async_discover_devices

async def main():
    devices = await async_discover_devices(["192.168.1.255"])
    for device in devices:
        print(device)  # {"ip": "192.168.1.50", "serial": 12345, "model": 1}

asyncio.run(main())
```

### Connect to a shade and control it

```python
import asyncio
from pyowershades import PowerShadesConnection, OP_SET_POSITION, build_set_position_payload

async def main():
    conn = PowerShadesConnection("192.168.1.50")
    await conn.async_connect()

    # Move to 50%
    await conn.async_request(OP_SET_POSITION, build_set_position_payload(50))

    conn.close()

asyncio.run(main())
```

### Receive live status pushes

```python
from pyowershades import PowerShadesConnection, StatusReply, parse_status_reply

def on_status(status: StatusReply) -> None:
    print(f"Position: {status.position}%  Battery: {status.battery_mv} mV")

conn = PowerShadesConnection("192.168.1.50")
conn.set_status_callback(on_status)
await conn.async_connect()
```

The shade sends status pushes to whichever UDP socket last sent it a command (the "UDP master"). As long as your connection stays active and periodically polls the device, it will receive live position updates.

## API reference

### Discovery

```python
async_discover_devices(local_addresses: list[str], timeout: float = ...) -> list[DiscoveredDevice]
async_get_device_info(ip: str, timeout: float = ...) -> PowerShadesDeviceInfo
```

### Connection

```python
class PowerShadesConnection:
    def __init__(self, ip: str) -> None
    async def async_connect(self) -> None
    async def async_request(self, op: int, payload: bytes = b"", ...) -> bytes
    def set_status_callback(self, callback: Callable[[StatusReply], None]) -> None
    def close(self) -> None
```

Raises `PowerShadesTimeoutError` if the device does not respond.

### Packet building

| Function | Description |
| -------- | ----------- |
| `build_packet(op, payload)` | Build a raw UDP packet for any opcode |
| `build_set_position_payload(percent)` | Payload for moving to a position (0–100) |
| `build_set_limit_payload(limit_type)` | Payload for setting upper/lower limits |
| `build_set_name_payload(name)` | Payload for renaming a PoE shade |

### Parsing

| Function | Description |
| -------- | ----------- |
| `parse_status_reply(data)` | Parse a status packet into a `StatusReply` |
| `parse_serial_reply(data)` | Parse a serial/model reply |
| `parse_shade_name_reply(data)` | Parse a shade name reply |
| `parse_device_name_reply(data)` | Parse a device name reply |
| `battery_percentage(battery_mv)` | Convert mV to a battery percentage (0–100) |

### Constants

Opcodes (`OP_GET_STATUS`, `OP_SET_POSITION`, `OP_JOG_UP`, `OP_JOG_DOWN`, `OP_JOG_STOP`, `OP_STEP_UP`, `OP_STEP_DOWN`, `OP_SET_LIMIT`, `OP_CLEAR_LIMITS`, `OP_INDICATE`, `OP_GET_SERIAL`, `OP_GET_SHADE_NAME`, `OP_GET_DEVICE_NAME`), limit types (`LIMIT_UPPER`, `LIMIT_LOWER`), and timing constants (`REQUEST_TIMEOUT`, `REQUEST_RETRIES`, `DISCOVERY_TIMEOUT`).

## Notes

- PowerShades devices send status pushes only to the last controller that sent them a command. If another controller (e.g. the PowerShades app or Control4) sends a command, your connection will stop receiving pushes until it sends one again.
- State inference (opening, closing, open, closed) is not done by this library (beacuse the shade does not send it) — only raw position values are reported.
- Push packets are sent every ~10 seconds by the shade while its moving
- Tested with PoE and Wi-Fi PowerShades controllers. RF hub support is unknown.

## License

MIT
