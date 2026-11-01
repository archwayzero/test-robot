# iOS handoff: build The Crypt on the Mac (T023)

The package from `tools/release/make_mac_package.py` holds the Godot project with all assets. iOS export only works on
macOS. Use a real iPhone: the simulator supports only the Compatibility renderer.

## You need
- Mac with Xcode (recent enough for your iPhone's iOS version), signed in with your Apple ID.
- Godot **4.7.2 stable**, the same version as the project, plus its export templates (Editor > Manage Export Templates).
- iPhone 12 or newer on iOS 16 or later, with a cable and Developer Mode on (Settings > Privacy & Security).

## Steps
1. Unzip the package and open `godot/project.godot` in Godot 4.7.2. Let the first import finish.
2. Project > Export > iOS. The preset is ready: name The Crypt, bundle ID `com.archwayzero.cryptmaze`, minimum iOS 16.0,
   ASTC textures, and tests and previews excluded.
3. Set **App Store Team ID** to your personal team's ID (Xcode > Settings > Accounts). This is the one empty field.
4. If Godot reports missing required icons, set one under Project Settings or the preset. The project has no app icon
   yet, so the home screen may show a default. Report this rather than treating it as a build failure.
5. Export Project to an empty folder. Export Project Only is on, so it writes an `.xcodeproj` and does not build.
6. Open the `.xcodeproj` in Xcode. Under Signing & Capabilities, choose your team and enable automatic signing.
   If the bundle ID is reported as taken, change it here and note the new value.
7. Select the iPhone and press Run. On the phone, trust the developer once under Settings > General > VPN & Device
   Management. Personal-team apps expire after 7 days; run from Xcode again to renew.

## Check on the device
Report these back, as nothing so far has been measured on a device.
- Does it boot into the maze? Is the first frame near-black, and how long is the load?
- Frame rate: use Xcode's GPU report in a corridor, at a junction and in a low passage. Target is 30 FPS.
- Occlusion: is the frame rate steady when turning a corner?
- Background past the fog at the far end of long runs: any black slit?
- Touch: joystick, Jump, Stance, camera drag, and the mini-map.
- Hero: is the dark upper body readable? Does it vanish past low-passage mouths? Does a brief fade look wrong?
- Heat and memory over 10 minutes.
