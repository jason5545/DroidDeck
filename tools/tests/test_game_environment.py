import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / "linuxfs/overlay/usr/local/bin"
MODULE = runpy.run_path(str(BIN / "bannerlator-game-env"))
COMPAT = runpy.run_path(str(BIN / "bannerlator-steam-compat"))


class GameEnvironmentTest(unittest.TestCase):
    def test_profile_precedence_and_unset(self):
        env = {"KEEP": "inherited", "REMOVE": "inherited", "CUSTOM": "launch option"}
        config = {"version": 1, "shared": {"CUSTOM": "shared"}, "games": {"42": {"REMOVE": None, "CUSTOM": "game", "EMPTY": ""}}}
        self.assertEqual(MODULE["apply_config"](env, config, "42"), {"KEEP": "inherited", "CUSTOM": "game", "EMPTY": ""})
        self.assertEqual(env["REMOVE"], "inherited")
        self.assertEqual(MODULE["apply_config"](env, config, "43")["CUSTOM"], "shared")

    def test_engine_fixes_follow_the_games_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "Godot Game"
            (game / "data_game_windows_x86_64").mkdir(parents=True)
            for name in ("Game.exe", "Game.pck", "libsentry.windows.release.x86_64.dll", "data_game_windows_x86_64/coreclr.dll"):
                (game / name).touch()
            env, extra, notes = MODULE["engine_fixes"](str(game / "Game.exe"), [])
            self.assertEqual(env["FEX_TSOENABLED"], "1")
            self.assertEqual(env["FEX_MULTIBLOCK"], "0")
            # Sentry's and tabtip's overrides both survive: two fixes, one variable.
            self.assertEqual(env["WINEDLLOVERRIDES"], "libsentry.windows.release.x86_64=d;tabtip.exe=d")
            self.assertEqual(extra, ["--rendering-driver", "vulkan"])
            self.assertEqual(MODULE["engine_fixes"](str(game / "Game.exe"), ["--rendering-driver", "opengl3"])[1], [])
            # A Godot game without Sentry still gets tabtip off.
            plain = Path(tmp) / "Plain"
            plain.mkdir()
            for name in ("Plain.exe", "Plain.pck"):
                (plain / name).touch()
            self.assertEqual(MODULE["engine_fixes"](str(plain / "Plain.exe"), [])[0], {"WINEDLLOVERRIDES": "tabtip.exe=d"})
            other = Path(tmp) / "Other"
            other.mkdir()
            (other / "Other.exe").touch()
            self.assertEqual(MODULE["engine_fixes"](str(other / "Other.exe"), []), ({}, [], []))

    def test_a_new_fix_only_needs_registering(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Game.exe").touch()
            (Path(tmp) / "engine.dll").touch()
            check = lambda game: ({"ENGINE": "1"}, ["--flag"], "engine") if "engine.dll" in game.files else None
            MODULE["FIXES"].append(check)
            try:
                self.assertEqual(MODULE["engine_fixes"](str(Path(tmp) / "Game.exe"), []), ({"ENGINE": "1"}, ["--flag"], ["engine"]))
            finally:
                MODULE["FIXES"].remove(check)

    def test_engine_fixes_sit_between_shared_and_game_profiles(self):
        env = {"WINEDLLOVERRIDES": "dxgi=n"}
        fixes = {"FEX_MULTIBLOCK": "0", "WINEDLLOVERRIDES": "libsentry=d"}
        config = {"version": 1, "shared": {"FEX_MULTIBLOCK": "1"}, "games": {"42": {"FEX_TSOENABLED": "0"}}}
        result = MODULE["apply_config"](env, config, "42", {**fixes, "FEX_TSOENABLED": "1"})
        self.assertEqual(result["FEX_MULTIBLOCK"], "0")
        self.assertEqual(result["FEX_TSOENABLED"], "0")
        self.assertEqual(result["WINEDLLOVERRIDES"], "dxgi=n;libsentry=d")

    def test_invalid_configuration_is_atomic(self):
        env = {"ORIGINAL": "unchanged"}
        for entries in ({"A": "ok", "BAD=KEY": "x"}, {"A": "bad\0value"}, {"A": 1}):
            with self.assertRaises(ValueError):
                MODULE["apply_config"](env, {"version": 1, "shared": entries}, "42")
            self.assertEqual(env, {"ORIGINAL": "unchanged"})

    def test_texture_filtering_is_appended_to_dxvk_config(self):
        options = "d3d9.samplerAnisotropy = 16; d3d11.samplerAnisotropy = 16"
        config = {"version": 1, "shared": {}, "games": {}, "dxvkConfig": options}
        self.assertEqual(MODULE["apply_config"]({}, config, "42")["DXVK_CONFIG"], options)
        own = {"DXVK_CONFIG": "dxvk.maxFrameRate = 60; "}
        self.assertEqual(MODULE["apply_config"](own, config, "42")["DXVK_CONFIG"], "dxvk.maxFrameRate = 60; " + options)
        shared = {"version": 1, "shared": {"DXVK_CONFIG": "dxvk.tearFree = True"}, "games": {}, "dxvkConfig": options}
        self.assertEqual(MODULE["apply_config"]({}, shared, "42")["DXVK_CONFIG"], "dxvk.tearFree = True; " + options)
        self.assertNotIn("DXVK_CONFIG", MODULE["apply_config"]({}, {**config, "dxvkConfig": ""}, "42"))
        for bad in (1, "a\0b", "x" * 8193):
            with self.assertRaises(ValueError):
                MODULE["apply_config"]({}, {**config, "dxvkConfig": bad}, "42")

    def test_game_ids_and_probes(self):
        for prefix in ("", "/compatdata/0", "/compatdata/0-123", "/compatdata/nope", "/compatdata/4294967296"):
            self.assertIsNone(MODULE["game_id"]({"STEAM_COMPAT_DATA_PATH": prefix}))
        self.assertEqual(MODULE["game_id"]({"STEAM_COMPAT_DATA_PATH": "/a/compatdata/42/"}), "42")
        self.assertEqual(MODULE["game_id"]({"STEAM_COMPAT_DATA_PATH": "/a/compatdata/-1"}), "4294967295")

    def test_launch_reads_updates_preserves_argv_and_does_not_execute_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config = home / ".config/droiddeck/game-environment.json"
            config.parent.mkdir(parents=True)
            probe = home / "fake-proton"
            probe.write_text("#!/usr/bin/python3\nimport json, os, sys\nprint(json.dumps([os.environ.get('CUSTOM'), sys.argv[1:]]))\n")
            probe.chmod(0o755)
            env = {**os.environ, "HOME": tmp, "STEAM_COMPAT_DATA_PATH": "/compatdata/42"}
            for value in ("first value", "$(touch " + str(home / "injected") + "); 'literal'=value"):
                config.write_text(json.dumps({"version": 1, "shared": {"CUSTOM": value}}))
                result = subprocess.check_output([sys.executable, str(BIN / "bannerlator-game-env"), str(probe), "waitforexitandrun", "path with spaces", "a=b"], env=env, text=True)
                self.assertEqual(json.loads(result), [value, ["waitforexitandrun", "path with spaces", "a=b"]])
            self.assertFalse((home / "injected").exists())
            for verb, prefix in (("run", "/compatdata/42"), ("waitforexitandrun", "/compatdata/0")):
                output = subprocess.check_output([sys.executable, str(BIN / "bannerlator-game-env"), str(probe), verb], env={**env, "STEAM_COMPAT_DATA_PATH": prefix, "CUSTOM": "original"}, text=True)
                self.assertEqual(json.loads(output)[0], "original")
            config.write_text("{broken")
            result = subprocess.run([sys.executable, str(BIN / "bannerlator-game-env"), str(probe), "waitforexitandrun"], env={**env, "CUSTOM": "original"}, text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout)[0], "original")

    def test_generated_valve_and_third_party_launchers_apply_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            steam = home / "Steam"
            tools = steam / "compatibilitytools.d"
            depot = steam / "steamapps/common" / COMPAT["SOURCES"][0]
            (depot / "files/bin-arm64").mkdir(parents=True)
            extra = tools / "custom-proton"
            extra.mkdir(parents=True)
            for base in (depot, extra):
                proton = base / "proton"
                proton.write_text("#!/usr/bin/python3\nimport json, os, sys\nprint(json.dumps([os.environ['CUSTOM'], sys.argv[1:]]))\nsys.exit(7)\n")
                proton.chmod(0o755)
            (extra / "toolmanifest.vdf").write_text('"manifest" { "commandline" "/proton %verb%" }')
            COMPAT["build_tool"](str(tools / COMPAT["TOOL"]))
            COMPAT["adopt_extras"](str(tools))
            config = home / ".config/droiddeck/game-environment.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"version": 1, "shared": {"CUSTOM": "shared"}, "games": {"42": {"CUSTOM": "specific"}}}))
            wrappers = (tools / COMPAT["TOOL"] / COMPAT["LAUNCHER"], extra / COMPAT["EXTRA_WRAPPER"])
            for wrapper in wrappers:
                wrapper.write_text(wrapper.read_text().replace("/usr/local/bin/bannerlator-game-env", str(BIN / "bannerlator-game-env")))
                result = subprocess.run([str(wrapper), "waitforexitandrun", "game with spaces.exe"],
                    env={"PATH": os.defpath, "HOME": tmp, "STEAM_COMPAT_DATA_PATH": "/compatdata/42", "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam)},
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(json.loads(result.stdout), ["specific", ["waitforexitandrun", "game with spaces.exe"]])

    def test_directaudio_selection_reaches_wine_and_leaves_when_off(self):
        good = "[Software\\\\Wine\\\\Drivers]"   # as Wine writes it: two backslashes between names
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "proton"
            (base / "files/bin-arm64").mkdir(parents=True)
            (base / "files/bin-arm64/wine").write_text("#!/bin/sh\necho wine-11.0\n")
            (base / "files/bin-arm64/wine").chmod(0o755)
            for arch in ("aarch64-windows", "i386-windows"):
                (Path(tmp) / "da/lib/wine" / arch).mkdir(parents=True)
                (Path(tmp) / "da/lib/wine" / arch / "winedirectaudio.drv").write_text(arch)
            win = Path(tmp) / "pfx/drive_c/windows"
            for d in ("system32", "syswow64"):
                (win / d).mkdir(parents=True)
            reg = Path(tmp) / "pfx/user.reg"

            def run(enabled=True):
                env = {**os.environ, "STEAM_COMPAT_DATA_PATH": tmp}
                env.pop("BL_DIRECTAUDIO", None)
                if enabled:
                    env["BL_DIRECTAUDIO"] = tmp + "/da"
                return subprocess.run(["bash", "-c", COMPAT["BL_DIRECTAUDIO_SETUP"] + '\nbl_directaudio "%s"\necho "$WINEDLLPATH"\n' % base],
                                      env=env, check=True, capture_output=True, text=True).stdout.strip()

            def keys():
                lines = reg.read_text().splitlines()
                return [(line.split("] ")[0] + "]", lines[i + 1] if i + 1 < len(lines) else "")
                        for i, line in enumerate(lines) if line.startswith("[Software")]

            reg.write_text("WINE REGISTRY Version 2\n")
            self.assertEqual(run(), tmp + "/da/lib/wine")
            run()
            self.assertEqual(keys(), [(good, '"Audio"="directaudio"')])
            # The PE goes into the prefix, where Wine's loader looks for a builtin outside prefix creation.
            self.assertEqual((win / "system32/winedirectaudio.drv").read_text(), "aarch64-windows")
            self.assertEqual((win / "syswow64/winedirectaudio.drv").read_text(), "i386-windows")
            # Off: the selection leaves, so mmdevapi goes back to its own list instead of trying nothing.
            self.assertEqual(run(enabled=False), "")
            self.assertNotIn('"Audio"="directaudio"', reg.read_text())
            # A prefix that only got the old, single-backslash key gets the real one as well.
            reg.write_text('WINE REGISTRY Version 2\n\n[Software\\Wine\\Drivers] 1\n"Audio"="directaudio"\n')
            run()
            self.assertEqual(keys(), [("[Software\\Wine\\Drivers]", '"Audio"="directaudio"'), (good, '"Audio"="directaudio"')])

    def test_both_proton_wrappers_call_environment_launcher(self):
        for script in (COMPAT["LAUNCHER_SH"], COMPAT["EXTRA_WRAPPER_SH"] % "proton"):
            subprocess.run(["bash", "-n"], input=script, text=True, check=True)
            self.assertIn('exec ${BL_TASKSET:-} /usr/local/bin/bannerlator-game-env', script)


if __name__ == "__main__":
    unittest.main()
