## Where save data is mirrored off-device. Implementations (internal/): `LocalOnlyBackend` (always available, does
## nothing), `FakeCloudBackend` (in-memory, for tests; can simulate unavailability), and `ICloudBackend`
## (iOS only, iCloud key-value store through a native plugin; added at the Mac stage, M3).
## Owner: orchestrator.
@abstract
class_name CloudBackend
extends RefCounted


## False when the cloud cannot be used right now (not signed in, offline, plugin missing).
@abstract func is_available() -> bool


## Stores `data` for `slot`. OK, or an Error (never blocks the game for more than a frame).
@abstract func push(slot: int, data: PackedByteArray) -> Error


## Returns the stored data for `slot`, or an empty array if none / unavailable.
@abstract func pull(slot: int) -> PackedByteArray
