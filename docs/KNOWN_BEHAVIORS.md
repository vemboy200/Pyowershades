# Known behaviors and limitations

This is different from [PROTOCOL.md](PROTOCOL.md), which documents the protocol's structure (opcodes, struct layouts, field meanings) from decompiled vendor source and packet captures. This file instead tracks empirically observed real-world *behaviors* - things a shade actually does on a live network - that don't yet have a confirmed root cause, so anyone debugging similar symptoms doesn't have to rediscover them from scratch.

## Green LED activity: overlapping, with occasional all-shades-at-once events (unconfirmed cause)

First observed 2026-09-13 on the maintainer's own installation (15 PoE shades, tracked via Home Assistant's Logbook): the green status LED (`io_green_led` in Debug Info, exposed as the `led_color` sensor) doesn't stay idle - it lights up for roughly 110 seconds at a time, then goes dark, on shades all around the house (bedroom, game room, kitchen, office, etc.).

**Correction - it is not one shade at a time.** The first observation suggested only one shade's LED was ever lit at once, rotating around the house. A week of history for a Home Assistant template sensor counting how many of the 15 shades have their green LED lit (2026-09-17 to 2026-09-24) disproves that: overlaps of 2-7 shades are common.

**Coordination is confirmed, though.** In that same week, all 15 green LEDs lit at the same time on five separate occasions (around Sep 17, Sep 18, Sep 21, and twice on Sep 24). Fifteen independent per-device timers wouldn't line up exactly like that, so something is triggering every shade at once. The timing of these all-at-once events looks sporadic - no fixed interval or time of day is apparent yet.

**Leading hypothesis:** each PoE shade also maintains a separate TCP connection to PowerShades' cloud dashboard (distinct from the local UDP protocol this library implements - see the Cloud sync note in PROTOCOL.md's command reference for `0x44`). A server-side event that reaches every shade on an account at once (a dashboard sync, a broadcast command, a reconnect after a server restart) would explain the all-at-once events, with the smaller overlaps being each shade's own routine check-ins. The earlier theory that check-ins were deliberately staggered one shade at a time no longer fits.

**Two confounding facts, both true at once for the observing installation, so this can't yet be attributed to one or the other:**

1. All shades are registered to the same PowerShades cloud/dashboard account.
2. All shades are on the same LAN/subnet.

Because both are simultaneously true, this observation alone can't distinguish "the PowerShades cloud service triggers every shade on an account" from "something on the shared LAN triggers them" (a local broadcast/discovery mechanism, switch-level behavior, or something else entirely). Confirming the real cause needs either a packet capture during an all-at-once event (watching for outbound TCP traffic to an external host), or a comparison case where shades share an account but not a LAN (or vice versa) - neither of which the maintainer currently has a way to test.

## Brief "Unavailable" transitions end exactly when the green LED lights up (cause unconfirmed)

Local UDP polls intermittently time out, which shows up in Home Assistant as a shade going `unavailable` for anywhere from about 10 seconds to a couple of minutes before recovering on its own.

In 24 hours of history from the maintainer's installation (2026-09-23 to 2026-09-24), all 12 of these unavailable blips, spread across 11 different shades and lasting 10 to 156 seconds, ended at the exact moment that same shade's green LED lit up (often a short 10-60 second green blip, then a normal ~110-120 second window right after). So the shade stops answering local UDP just *before* its green LED activity, then comes back as the LED turns on - not during the LED window, as first assumed.

It doesn't happen every time: the same day had 81 green LED windows in total, and only 12 were preceded by an unavailable blip. Whatever the shade is doing right before its green LED lights up (most likely the same cloud connection activity described above) seems to sometimes block it from answering local polls for long enough to miss one or more.

## How to help confirm or rule these out

- A packet capture on the LAN during a green LED "on" window (ideally an all-at-once event), checking for outbound TCP SYN packets to any external host at the moment it lights up - and in the seconds *before* it lights up, when local polls sometimes stop being answered.
- Testing with Feature Disables (`0x35`) bit 6 (`DISABLE_TCP_CLOUD`, "disable TCP/cloud connectivity") set on some shades, to see whether they drop out of the all-at-once events or stop lighting up entirely.
- Reports from other installations: does this activity show up for shades that *don't* share a cloud account, or that aren't all on the same LAN?
