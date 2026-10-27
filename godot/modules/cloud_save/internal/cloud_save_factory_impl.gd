## CloudSaveFactory implementation (loaded by public/cloud_save_factory.gd at this exact path).
extends CloudSaveFactory

const AutoSaveImpl := preload("res://modules/cloud_save/internal/auto_save_impl.gd")
const LocalOnlyBackend := preload("res://modules/cloud_save/internal/local_only_backend.gd")
const FakeCloudBackend := preload("res://modules/cloud_save/internal/fake_cloud_backend.gd")

## Name of the native iOS plugin singleton that the M3 ICloudBackend will use (not implemented yet).
const ICLOUD_SINGLETON := "ICloudKeyValue"


func make_auto_save() -> AutoSave:
	var auto_save: AutoSave = AutoSaveImpl.new()
	auto_save.name = "AutoSave"
	return auto_save


func make_platform_backend() -> CloudBackend:
	# --- ICloudBackend seam (Mac stage, M3) ---------------------------------------------------------------
	# When the native plugin exists, return the iCloud backend here, e.g.:
	#   if OS.get_name() == "iOS" and Engine.has_singleton(ICLOUD_SINGLETON):
	#       return preload("res://modules/cloud_save/internal/icloud_backend.gd").new(
	#               Engine.get_singleton(ICLOUD_SINGLETON))
	# The plugin and internal/icloud_backend.gd do not exist yet; until then every platform is local-only.
	# ------------------------------------------------------------------------------------------------------
	return LocalOnlyBackend.new()


func make_fake_backend(available: bool = true) -> CloudBackend:
	return FakeCloudBackend.new(available)
