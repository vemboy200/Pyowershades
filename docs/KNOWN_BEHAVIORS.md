# Known behaviors and limitations

This is different from [PROTOCOL.md](PROTOCOL.md), which documents the protocol's structure (opcodes, struct layouts, field meanings) from decompiled vendor source and packet captures. This file instead tracks empirically observed real-world *behaviors* - things a shade actually does on a live network - that don't yet have a confirmed root cause, so anyone debugging similar symptoms doesn't have to rediscover them from scratch.

## Green LED activity rotates across shades, mutually exclusive (unconfirmed cause)

Observed 2026-09-13 on the maintainer's own installation (15 PoE shades, tracked via Home Assistant's Logbook): the green status LED (`io_green_led` in Debug Info, exposed as the `led_color` sensor) doesn't stay idle - it lights up for roughly 110 seconds at a time, then goes dark, and rotates around the whole house over a 3-4 hour cycle. Across every shade observed (bedroom, game room, kitchen, office, etc.), only ever **one** shade's LED was lit at any given moment - no overlaps seen at all.

**Leading hypothesis:** each PoE shade also maintains a separate TCP connection to PowerShades' cloud dashboard (distinct from the local UDP protocol this library implements - see the Cloud sync note in PROTOCOL.md's command reference for `0x44`). If cloud check-ins/keep-alives are staggered across a user's devices - so they don't all hit the dashboard at once - that would explain both the mutual exclusivity and the rotation. Fifteen independent, uncoordinated per-device timers would be expected to overlap at least occasionally given the "on" duration relative to the cycle length; seeing zero overlaps across a full day strongly suggests active coordination rather than coincidence.

**Two confounding facts, both true at once for the observing installation, so this can't yet be attributed to one or the other:**

1. All shades are registered to the same PowerShades cloud/dashboard account.
2. All shades are on the same LAN/subnet.

Because both are simultaneously true, this observation alone can't distinguish "the PowerShades cloud service schedules check-ins per account" from "something about sharing a LAN causes this" (a local broadcast/discovery mechanism, switch-level behavior, or something else entirely). Confirming the real cause needs either a packet capture during an "on" window (watching for outbound TCP traffic to an external host), or a comparison case where shades share an account but not a LAN (or vice versa) - neither of which the maintainer currently has a way to test.

## Brief "Unavailable" transitions coinciding with LED activity (unconfirmed, possibly related)

This integration's local UDP polls have intermittently timed out (surfacing as `unavailable` in Home Assistant) around the same time a shade's green LED activity window is active. Hypothesis: the shade's embedded controller may not reliably service a local UDP poll while it's occupied with whatever the green LED indicates (see above) - unconfirmed, and could just as easily be unrelated network jitter.

## How to help confirm or rule these out

- A packet capture on the LAN during a green LED "on" window, checking for outbound TCP SYN packets to any external host at the moment it lights up.
- Testing with Feature Disables (`0x35`) bit 6 ("disable TCP/cloud connectivity" - not yet implemented in `pyowershades`) set, to see whether the rotation stops entirely.
- Reports from other installations: does this rotation show up for shades that *don't* share a cloud account, or that aren't all on the same LAN?
