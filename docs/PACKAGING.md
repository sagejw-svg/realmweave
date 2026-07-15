# Packaging Realmweave as a Windows installer

Goal: players double-click one installer, get a Start Menu shortcut, and play.
No Python, no Godot, no manual setup on their side.

The installer bundles two executables plus a launcher:

1. **RealmweaveClient.exe** - the Godot client, exported to a standalone Windows
   binary (bundles the Godot runtime; no engine install needed).
2. **RealmweaveServer.exe** - the Python backend, frozen with PyInstaller
   (bundles Python and dependencies; no Python install needed).
3. **Launch-Realmweave.bat** - starts the server, then the client. The Start
   Menu shortcut points here.

`packaging/realmweave.iss` (Inno Setup) wraps all three into `RealmweaveSetup.exe`.

## Build it locally (Windows)

Prereqs once: Godot 4.3+ with **export templates** installed
(Editor -> Manage Export Templates -> Download), Python 3.10+, and
[Inno Setup 6](https://jrsoftware.org/isdl.php).

```powershell
# 1. Freeze the server -> build\RealmweaveServer.exe
cd backend
py -m pip install pyinstaller websockets
py -m PyInstaller --onefile --name RealmweaveServer --distpath ..\build --workpath ..\build\tmp --specpath ..\build\tmp run_server.py

# 2. Export the client -> build\RealmweaveClient.exe
#    (uses godot_client/export_presets.cfg; needs export templates installed)
godot --headless --path godot_client --export-release "Windows Desktop" ..\build\RealmweaveClient.exe

# 3. Build the installer -> build\RealmweaveSetup.exe
iscc packaging\realmweave.iss
```

Ship `build\RealmweaveSetup.exe`.

## Or let CI build it

`.github/workflows/release.yml` does all of the above on a Windows runner when you
push a tag like `v0.1.0`, and attaches `RealmweaveSetup.exe` to a GitHub Release.
That way you never run the Godot export by hand.

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Notes

- **LLM dialogue:** the bundled server defaults to the GPU-free stub so it always
  runs. For real local-LLM dialogue, players install Ollama separately (or a
  future installer can offer to fetch it). Config lives next to the server exe.
- **Config & saves** are written next to `RealmweaveServer.exe` (or a per-user
  data dir); the installer creates the folder.
- **Single self-contained .exe** (no Python at all) would require porting the
  simulation into Godot (GDScript/C#). That is the long-term option; this
  installer path ships the same tested Python engine today.
- Do not commit `build/` or `dist/` artifacts; they are git-ignored.
