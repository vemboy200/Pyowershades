# PowerShades UDP protocol reference

This is a reference for the UDP protocol `pyowershades` speaks to PowerShades PoE shades and RF gateways. It exists so contributors can see the full picture of what the protocol supports, not just what this library currently implements, and to give anyone reverse-engineering compatibility (or writing a new client) a single place to check field layouts before capturing packets themselves.

## Provenance and scope

This isn't guesswork. It comes from three sources, cross-checked against each other:

1. **Live packet captures and interoperability testing** against real PowerShades hardware, done by this project's maintainer.
2. **PowerShades Config.NET**, the vendor's own official Windows configuration app, decompiled for research purposes to confirm field layouts and to find protocol surface this library didn't implement yet.
3. **[`developer-powershades/savant-powershades-profile`](https://github.com/developer-powershades/savant-powershades-profile)**, the vendor's own published driver for the Savant home-automation platform, which contains working reference code for the same protocol.

The library only ever *sends and parses this protocol locally on your own network to control devices you own* — nothing here talks to PowerShades' cloud, and this project has no affiliation with PowerShades. Documenting the full command set (including commands this library doesn't use) is standard practice for interoperability libraries in this space; see projects like `python-kasa`, `pychromecast`, or any Home Assistant custom component for similar vendor-protocol references.

**A safety note on the commands below marked "destructive" or "admin-gated":** these exist in the vendor's own app and are being documented for completeness and transparency, not encouragement to use them. Some of them (factory reset, serial number rewrite, firmware image revert) can put real hardware into a bad state. `pyowershades` does not implement or expose any of them today, and there's no plan to add them to the Home Assistant integration.

## Packet format

All packets are a single UDP datagram to/from port 42, little-endian:

| Bytes | Field | Notes |
| --- | --- | --- |
| 0–1 | Length | length of `Op` + `Sequence` + `Channel` + `Reserved` + payload |
| 2–3 | CRC16 (XMODEM) | covers the same range as Length |
| 4 | Op | command/opcode, see table below |
| 5 | Sequence | rolling counter, wraps before 255 |
| 6 | Channel | device index — which paired shade on an RF gateway a command targets; `0` for PoE shades and gateway-wide commands |
| 7 | Reserved | unused, `0` |
| 8+ | Payload | shape depends on `Op`, see per-command notes |

Replies use the same envelope, echoed back with data appended after the header.

## Device models

The model byte in a Get Serial Number reply has exactly two real values (confirmed against both official sources — there's no third, "Wi-Fi," model despite that claim circulating in some secondhand PowerShades documentation):

| Value | Model |
| --- | --- |
| `1` | PoE Shade |
| `100` | RF Gateway |

## Command reference

"Implemented" means `pyowershades` builds/parses this command today. "Implemented (raw)" means it can send the command and/or return the reply's raw bytes, but doesn't parse a typed result yet — usually because the exact field layout lives in a shared library that wasn't available to decompile, so it needs verifying against a real device first. "Candidate" means it's real, confirmed protocol surface that isn't wired up yet but could become a future feature. "Destructive/admin-gated" is called out separately below the table.

| Op (hex / dec) | Name | Status | Notes |
| --- | --- | --- | --- |
| `0x00` / 0 | Get Serial Number | Implemented | returns model, serial, direction, DHCP flag; also carries an optional trailing hostname string if one is set |
| `0x01` / 1 | Set Limit | Implemented | sets the upper or lower travel limit to the current position |
| `0x03` / 3 | Jog Up | Implemented | |
| `0x04` / 4 | Jog Down | Implemented | |
| `0x05` / 5 | Jog Stop | Implemented | |
| `0x06` / 6 | Pair Device | Candidate | RF only |
| `0x07` / 7 | Unpair Device | Candidate | RF only; not wired to a visible button in the vendor app, may be legacy |
| `0x08` / 8 | Indicate / Beep | Implemented | |
| `0x0B` / 11 | Set Server Hostname | Candidate | sets a custom DNS hostname on the device |
| `0x0C` / 12 | Set IP Settings | Candidate | DHCP vs. static, IP/subnet/gateway |
| `0x0E` / 14 | Set Serial Number | Destructive/admin-gated | overwrites the device's own identity |
| `0x13` / 19 | IP Whitelisting | Candidate | get/set up to 4 allowed controller IPv4 addresses plus an enable flag; separate access-control feature from Set IP Settings |
| `0x16` / 22 | RF Program Button | Candidate | RF only, simulates the physical remote's pairing button |
| `0x18` / 24 | Reboot | Implemented | |
| `0x1A` / 26 | Set Position | Implemented | move to a 0–100% target; also has an RF-gateway group-broadcast form addressing multiple paired channels at once |
| `0x1D` / 29 | Get Status | Implemented | position, moving state, and voltage; several fields the vendor's own source marks reserved/future (memory, time, cycles, stalls, temperature) aren't populated on current firmware |
| `0x1E` / 30 | Clear Limits | Implemented | |
| `0x1F` / 31 | Save Limits | Implemented | |
| `0x21` / 33 | RF Link Feedback (pair, 2-way ack) | Candidate | RF only; distinct from Pair Device — the RF pairing state machine isn't fully mapped out yet |
| `0x23` / 35 | Step Up | Implemented | |
| `0x24` / 36 | Step Down | Implemented | |
| `0x25` / 37 | Reverse Direction | Candidate | side effect: clears travel limits when sent |
| `0x26` / 38 | Debug/Extended Status | Implemented (raw) | includes end-stop and PoE I/O status fields not exposed by Get Status; field names are confirmed but exact byte widths aren't (shared-library gap, see below), so `pyowershades` returns the raw payload pending a typed parser |
| `0x27` / 39 | PoE Motor Parameters (get/set) | Candidate | speed and motor-tuning surface, admin-gated — see below |
| `0x28` / 40 | Broadcast Status Request | Candidate | status query sent to the broadcast address rather than a specific device |
| `0x2A` / 42 | RF Unlink Feedback | Candidate | RF only, disables 2-way ack; distinct from Unpair Device |
| `0x2D` / 45 | Set System Clock | Candidate | timezone offset, DST flag, and a Unix timestamp — the device keeps its own clock |
| `0x2E` / 46 | Get Device ID | Implemented (raw) | firmware revision, active flash bank, and a model-version byte that gates other behaviors; same shared-library gap as Debug/Extended Status, so `pyowershades` returns the raw payload pending a typed parser |
| `0x2F` / 47 | PoE Cycle Test | Candidate | repeatedly runs the shade for a set dwell period and cycle count; a manufacturing/QA burn-in feature, not part of normal operation |
| `0x30` / 48 | Firmware Update | Destructive/admin-gated | flashes new firmware over UDP in 64-byte chunks with an address/ack handshake; a botched transfer can require vendor support to recover |
| `0x34` / 52 | Get/Set Shade Name (PoE) | Implemented | |
| `0x35` / 53 | Feature Disables | Candidate | bitfield: PCB button, PCB "special" behavior, dry-contact input, dry-contact "special" behavior, TCP/cloud connectivity, and PCB-button-triggered IP change can each be independently disabled |
| `0x36` / 54 | Auto-Set Limits | Candidate | computes travel limits from a target height in inches |
| `0x3A` / 58 | Get Device Name (generic/gateway) | Implemented | |
| `0x3B` / 59 | Set Device Name | Candidate | |
| `0x3C` / 60 | Admin Access | Destructive/admin-gated | privileged-access handshake required before other admin-gated commands are accepted — see below |
| `0x3D` / 61 | Revert to Alternate Firmware Image | Destructive/admin-gated | the vendor app itself shows a warning dialog before sending this |
| `0x3E` / 62 | Add Remote | Candidate | RF only, not wired to a visible button in the vendor app, possibly legacy |
| `0x40` / 64 | JSON Test Message | Implemented (raw send) | an alternate JSON envelope over the same UDP port; `pyowershades` can frame and send an arbitrary payload in the wire format the vendor app uses, but the JSON schema the firmware actually accepts is undocumented anywhere, so this is a raw exploration tool rather than a defined feature |
| `0x41` / 65 | Factory Reset | Destructive/admin-gated | |
| `0x44` / 68 | Cloud Update Check/Trigger | Candidate | payload flag 1 = check for a newer version (device replies with a result field after querying its cloud dashboard), 2 = trigger an install; the device does its own fetch, so this fits the same "device-initiated update" pattern used by many local-first integrations (WLED, Reolink) — not gated behind Admin Access |
| `0x83` / 131 | Raw Test Command | Candidate | generic debug/test op with an arbitrary payload |

## Admin access and the factory key

Several commands above — most notably PoE Motor Parameters (speed/motor tuning) — are rejected unless an Admin Access (`0x3C`) command was sent to the device immediately beforehand, unlocking a privileged window for the commands that follow. The vendor's own app sends these as a fixed pair every time (admin-access command, then the actual privileged command), never separately.

The key the vendor's app sends is a fixed numeric constant baked into every published copy of the software: `179097173`. This isn't real authentication — it's identical for every device and every install of the app, and it also happens to be the same mechanism gating the app's own local "Advanced" settings panel (itself protected by a plain hardcoded password, not tied to your device at all). It reads as a dealer/installer footgun-prevention gate rather than a security boundary, so replicating it here for interoperability is reasonable — the same reasoning that applies to every other command in this reference.

If `pyowershades` ever implements a command that needs this, it should send both operations as a single atomic call (e.g. one `async_set_motor_speed()` helper) rather than exposing the admin-access step separately, so callers can't forget it and have the device silently ignore their command.

## Known gaps and uncertainties

- The RF pairing model (Pair Device, RF Link Feedback, RF Unlink Feedback, Unpair Device, Add Remote) is not fully disambiguated — some of these may be legacy paths not reachable from the current app UI. This needs real RF hardware to verify.
- A few byte offsets in the Get Serial Number reply (IP/subnet/gateway, when present) are flagged as uncertain even in the vendor's own source, which contains a comment questioning whether its own documentation matches its sample data.
- Fields in the Get Status reply marked reserved/future by the vendor (memory, time, cycle count, stall count, temperature) should not be assumed populated on real firmware without checking first.
- Anything on this page not already implemented in `pyowershades` should be verified against a real packet capture before being relied on in code — decompiled/vendor-driver behavior and live wire behavior aren't guaranteed to be identical across firmware versions.
