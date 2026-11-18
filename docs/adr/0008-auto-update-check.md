# Update check runs on every command; the notice is protect-only

Every invocation of `protect` or `password` performs an update check (latest release from GitHub, at most once per hour via a TTL cache in the config dir, 5 s timeout, silent on any failure). The "update available" notice is printed only by `protect`, on stdout, after a successful run.

Chosen to keep `password`'s stdout machine-readable (it is the bare password and users pipe it), while surfacing the notice where the output is already human-facing. The TTL cache bounds the network cost to ~1 call/hour/user and keeps offline use completely quiet.

## Consequences

- `protect` makes a network call (bounded by the TTL) on cold checks; a slow network adds up to the 5 s timeout once per hour.
- `password` and `update` run the check to keep the cache warm but print no notice.
- Any failure (offline, rate limit, API error) is silent: the command proceeds exactly as if no check ran, falling back to a stale cached version when one exists.
- A build newer than the latest stable release (e.g. built from master) never sees a notice, since the check only reports when the latest stable release is strictly newer.
