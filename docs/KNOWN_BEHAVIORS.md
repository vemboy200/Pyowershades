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

**Update, November 2026: the 2-minute light is a new cloud connection.** With a logging relay standing in for PowerShades' server (see [The cloud connection](#the-cloud-connection-tcp-port-60) below), every 2-minute green window on the relayed shades started a few seconds after the shade opened a new TCP connection to it. Data flowing over an already-open connection never lit it: one shade's 18-hour session carried about 2,300 server messages with no LED activity. Failed connection attempts show as short 10-20 second green blips instead. This still doesn't explain the all-at-once events, though a server-side restart that drops every shade's connection at once would fit. Not every flash is a cloud connection either: one shade also flashed twice in a day with no connection and no DNS lookup, cause unknown.

## Brief "Unavailable" transitions end exactly when the green LED lights up (cause unconfirmed)

Local UDP polls intermittently time out, which shows up in Home Assistant as a shade going `unavailable` for anywhere from about 10 seconds to a couple of minutes before recovering on its own.

In 24 hours of history from the maintainer's installation (2026-09-23 to 2026-09-24), all 12 of these unavailable blips, spread across 11 different shades and lasting 10 to 156 seconds, ended at the exact moment that same shade's green LED lit up (often a short 10-60 second green blip, then a normal ~110-120 second window right after). So the shade stops answering local UDP just *before* its green LED activity, then comes back as the LED turns on - not during the LED window, as first assumed.

It doesn't happen every time: the same day had 81 green LED windows in total, and only 12 were preceded by an unavailable blip. Whatever the shade is doing right before its green LED lights up (most likely the same cloud connection activity described above) seems to sometimes block it from answering local polls for long enough to miss one or more.

**Update, November 2026:** relay logs show the daily blip is the shade reconnecting its cloud session (see below). The shade stops answering local UDP for about 10-30 seconds while it does.

## Turning cloud off makes the daily check-in drop the shade over and over (Gen 1, observed once)

Every PoE shade normally drops off local UDP for about 15-30 seconds once a day, at what looks like its cloud check-in. That moment drifts about 6-7 minutes later each day (about every 24h06m).

On 2026-11-15 at 23:33 UTC, the maintainer set Feature Disables (`0x35`) bit 6 (`DISABLE_TCP_CLOUD`) on one Gen 1 shade. At its next check-in time (about 22:30 UTC on 2026-11-16, right where the daily drift put it), the shade did not drop off once. It went unavailable every 1-2 minutes, for 10-60 seconds each time, for 80 minutes straight. Clearing the bit again stopped it right away.

Clearing the bit was itself hard during the loop. The read-modify-write (Get, Set, then Get to confirm) failed twice because the shade dropped out partway through, and only the third attempt landed.

The cause is unconfirmed. The pattern fits the shade's firmware still trying its cloud connection on schedule, failing because TCP/cloud is disabled, and retrying in a loop that blocks local UDP each time. A packet capture during the loop would confirm or rule that out. This was seen on one shade, once, so it isn't known whether it happens every time or on Gen 2.

**Practical advice:** don't set bit 6. Home Assistant's `hass-powershades` integration removed its Allow Cloud Connection switch for this reason. If a shade is dropping off every minute or two instead of about once a day, check whether bit 6 is set and clear it, retrying until a Get confirms it.

## Cloud Update Check (`0x44`, flag 1) never replies (Gen 1)

The vendor's Config.NET app sends the check once and waits 10 seconds for a reply. On the maintainer's Gen 1 shades, no shade has ever answered it.

On 2026-11-16, a direct test on one shade waited 30 seconds with no retries and got no reply. At the time:

- the shade's cloud connection was on (Disables read `0x00`);
- Debug Info showed `ClientState` 7 and an empty error list;
- the shade was answering every other command normally;
- from the same LAN, `dashboard.powershades.com` and `cloudserver.powershades.com` both resolved and accepted TCP connections on port 60.

So a longer timeout won't fix this. Why the shade doesn't answer is unknown. Possible causes include the firmware ignoring the op, the check needing the shade registered a certain way on PowerShades' dashboard, or the dashboard not answering it. None of these have been tested. `parse_cloud_update_reply` is still unverified against a real reply for the same reason.

## The cloud connection (TCP port 60)

Observed in November 2026 on Gen 1 shades, by pointing powershades.com at a logging relay on the LAN with a DNS rewrite:

- Each shade keeps one **persistent** TCP connection to its Server Hostname on port 60 (`dashboard.powershades.com` on Gen 1). It isn't a once-a-day connection: the server sends a 16-byte message about every minute and the shade answers.
- **The server speaks first** (32 bytes). The handshake that follows always has the same shape (32, 48, 16, 112, 32, then 16-byte messages), but different bytes every time.
- **It's encrypted.** Every message is a multiple of 16 bytes and looks random, which suggests a 16-byte block cipher (AES is likely but unconfirmed).
- **It's real challenge-response.** Replaying a recorded server handshake fails: the shade's replies differ every attempt even with an identical server opener, and it hangs up after the third message. So a stand-in server can't complete the handshake without the key and algorithm.
- **Once a day the shade reconnects.** It opens a new connection while the old one is still open, sometimes a second one a couple of minutes later, and keeps the last one for about a day. The time drifts about 6-7 minutes later each day.
- **Changing the Server Hostname** (`0x0B`) makes the shade drop its connection and look up the new value within seconds.
- **The hostname always goes through DNS.** Set to a LAN IP address or an mDNS `.local` name, the shade sent it to its DNS server as an ordinary `A` query (the IP literally, as if it were a name), got NXDOMAIN, and never connected. So only a name your DNS server resolves works.

## Keeping a shade off the PowerShades cloud (Gen 1)

The shade needs *something* to connect to, or it drops off local UDP more often. What was tried, each on one or two shades:

| Method | Result |
|---|---|
| Cloud reachable (normal) | 1-2 short drops a day, at the daily reconnect |
| Feature Disables bit 6 (`DISABLE_TCP_CLOUD`) | Dropped off every 1-2 minutes, for 80 minutes (see above) |
| DNS block (NXDOMAIN for powershades.com) | Dropped off for about 12-14 seconds every 5-10 minutes |
| Server Hostname set to a LAN IP or `.local` name | Lookup fails the same way as a DNS block (see above) |
| Local server replaying a recorded handshake | No drops, but the handshake fails within seconds and the shade reconnects every 5-10 seconds (about 8,400 times a day), so its green LED stays lit |
| Local server that accepts the connection and never replies | Same as the real cloud: about one 12-second drop and one or two 2-minute green LED windows a day, over two days on two shades. While connected, the shade sends a 48-byte message about every 2 minutes and doesn't seem to need an answer. |

The last one is what [powershades-cloud-stub](https://github.com/vemboy200/powershades-cloud-stub) does in its `listen` mode, with a DNS rewrite pointing powershades.com at it. None of this has been tested on Gen 2, which uses `cloudserver.powershades.com`.

## How to help confirm or rule these out

- A packet capture on the LAN during a green LED "on" window (ideally an all-at-once event), checking for outbound TCP SYN packets to any external host at the moment it lights up - and in the seconds *before* it lights up, when local polls sometimes stop being answered.
- A packet capture while a shade with Feature Disables bit 6 set is stuck in the dropout loop above, to see what it's actually retrying. Expect it to disturb that shade until the bit is cleared.
- A reply to Cloud Update Check from any shade (any generation or firmware), with the raw reply bytes.
- Reports from other installations: does this activity show up for shades that *don't* share a cloud account, or that aren't all on the same LAN?
- Any of the cloud connection or "keeping a shade off the cloud" results above repeated on a Gen 2 shade.
