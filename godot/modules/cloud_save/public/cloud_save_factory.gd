## Owner: orchestrator. Implemented by internal/cloud_save_factory_impl.gd.
@abstract
class_name CloudSaveFactory
extends RefCounted

const _IMPL_PATH := "res://modules/cloud_save/internal/cloud_save_factory_impl.gd"


static func create() -> CloudSaveFactory:
	return load(_IMPL_PATH).new()


@abstract func make_auto_save() -> AutoSave


## The best backend for this platform: ICloudBackend on iOS when the plugin is present, else LocalOnlyBackend.
@abstract func make_platform_backend() -> CloudBackend


## In-memory backend for tests. `available` = false simulates no iCloud.
@abstract func make_fake_backend(available: bool = true) -> CloudBackend
