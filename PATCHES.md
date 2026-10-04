# PATCHES.md

這份是 Jason 的 DroidDeck fork（`jason5545/DroidDeck`）相對 upstream（`Droid-Deck/DroidDeck`）保留的本地 patch 清單。測試機是 POCO F8 Ultra（SM8850、Adreno 840、HyperOS／Android 16）。

維護規則：

- 新增本地 patch：在「保留的本地改動」加一條（為什麼要改、相關檔案、測試、行為底線），在「合併衝突檢查」列出要守的檔案與函式，並更新條數。
- upstream 修了同一件事：確認該條列的測試仍通過或等價改寫，再整段換成 upstream 版，兩處一起拿掉。
- 修的是 upstream bug 時，寫明來源 commit／PR 與對應的上游 issue，方便判斷什麼時候可以拿掉。

## 建置與安裝

手機上的 DroidDeck 是 CI 版，用公開的 AOSP testkey 簽（`a40da80a…`），不是 upstream 正式金鑰。所以這個 fork 自己 build、用 testkey 簽的 APK 可以 `adb install -r` 原地覆蓋，runtime、Steam 登入和已裝的遊戲都會保留。versionCode 不能低於手機上那一版。

`tools/build_local.sh` 要 Docker 和 x86 模擬，在 Apple Silicon 上很慢。只改 Kotlin／Java 或 `tools/linuxfs` 腳本時，改用 upstream 同一個 commit 的 CI 產物當原生素材：

1. `gh run download <run id> -R Droid-Deck/DroidDeck -n droiddeck-apk`，跟本地 HEAD 同一個 commit 的那次 Build APK。
2. 把 APK 裡的 `assets/linuxfs/` 解到 `app/src/main/assets/linuxfs/`、`lib/arm64-v8a/libproot*.so` 放進 `app/src/main/jniLibs/arm64-v8a/`、`assets/pulseaudio.tzst` 蓋過同名檔（這個檔有進版控，build 完要 `git checkout` 還原）。
3. 改到 `tools/linuxfs/desktop/` 的檔案要手動複製進 `app/src/main/assets/linuxfs/usr/local/bin/`，Gradle 只會同步 `tools/linuxfs/overlay` 底下的 `bannerlator-*` 和 `usr/bin`。
4. `JAVA_HOME` 指向 openjdk@17，`./gradlew assembleRelease -PndkVersion=<已裝的 NDK>`，產物已經是 testkey 簽名。

## 保留的本地改動

目前五條：

- **中文方塊字**：runtime（Arch Linux ARM rootfs）只有 DejaVu 一個字族，Steam 介面切到繁體中文時，中文全是方塊。每次 session 開始時，App 把 Android 系統的 `/system/fonts/NotoSansCJK-Regular.ttc`（沒有就用 `DroidSansFallback*`）複製到 rootfs 的 `/usr/share/fonts/droiddeck-android/`，大小不同才重新複製，不用另外下載。同一個 ttc 裡有 JP／KR／SC／TC／HK 五個字面，fontconfig 預設的 `65-nonlatin.conf` 只在 `sans-serif` 前面列了 KR（給韓文），所以中文會選到韓文字面。App 另外寫 `/etc/fonts/conf.d/65-droiddeck-cjk.conf`：有標語言的文字選該語言的字面；沒標語言的選 Android 系統語言對應的字面（zh-TW 是 TC）。規則插在每個通用字族正前方，檔名排在 65-nonlatin 之前，所以排在 KR 前面、拉丁字型後面；另外在清單最後補一條，給沒連結預設規則的 rootfs 用。`droiddeck-desktop` 判斷「預設規則連結了沒」時，不把這個檔算進去。相關檔案：`app/src/main/java/com/droiddeck/launcher/runtime/LinuxRuntime.java`（`syncAndroidCjkFonts`、`writeCjkFontRules`、`appendCjkFaceRules`、`androidCjkFace`，從 `binds()` 呼叫）、`tools/linuxfs/desktop/droiddeck-desktop`、`tools/linuxfs/overlay/usr/local/bin/bannerlator-session`（session.log 的 `== fonts: zh-TW text uses …` 診斷行）、`app/src/test/java/com/droiddeck/launcher/runtime/AndroidCjkFaceTest.kt`。驗證：手機 session.log 從 `"Noto Sans CJK KR"` 變成 `"Noto Sans CJK TC"`；Mac 上用同一個 ttc、DejaVu 和 fontconfig 預設規則重現，zh-TW→TC、zh-CN→SC、ja→JP、ko→KR、zh-HK→HK，`sans-serif`（拉丁）仍是 DejaVu Sans。行為底線：Steam 介面的中文不會是方塊，繁中不會用到 KR／JP 字面。

- **遊戲內觸控**：Big Picture 的觸控模式是 4（直通），但遊戲一拿到焦點，Steam 就把 gamescope 的 `STEAM_TOUCH_CLICK_MODE` 設成 5（停用），手指在遊戲裡完全沒作用，只剩手把（2026-10-04 Monster Train 2 實測）。Steam 為什麼對遊戲送 5，未查證。session 腳本原本就在 `xprop -spy` 記錄這個屬性；現在遊戲在前景、而且 5 在 0.3 秒後還在時，改寫成 `BL_GAME_TOUCH_MODE`（預設 1：點哪裡就點哪裡、可拖曳，跟 WinNative／GameNative 一樣把觸控當滑鼠；4 是原生觸控）。焦點在 Steam（769）時不動，Steam 自己選的其他模式也不動。抽屜（Controls 頁）和設定選單（Touch & controls）各有一個「Touch in games」開關，預設開；App 寫 `~/.droiddeck-game-touch`，腳本每秒讀一次，關掉時把 5 還回去，不用重開 session。`BL_GAME_TOUCH_MODE=steam`（`Download/droiddeck-env`）可以整個 session 關掉。相關檔案：`tools/linuxfs/overlay/usr/local/bin/bannerlator-session`（`game_touch_on`、`touch_state`、`enable_game_touch`、`restore_game_touch`、touch watcher 和開關輪詢兩個背景迴圈）、`app/src/main/java/com/droiddeck/launcher/session/SessionPrefs.kt`（`gameTouch`、`setGameTouch`、`writeGameTouchFlag`）、`SessionService.kt`（session 開始時寫旗標）、`SessionActivity.kt`、`ui/SessionOverlay.kt`、`MainActivity.kt`、`ui/ModeSettingsDialog.kt`、`res/values*/strings.xml`（`mode_game_touch*`、`drawer_game_touch`）。驗證：手機 session.log 出現 `the client disabled touch for app 2742830; set 1 instead`，Jason 確認遊戲內可以直接觸控；開關的六種情境（Big Picture、遊戲裡送 5、關閉還原、關閉時再送 5、重新打開、Steam 選單）用假 `xprop` 模擬過。行為底線：開關打開時，Steam 停用觸控的遊戲裡，點擊照樣有效；Big Picture 和 Steam 選單維持 Steam 自己的觸控模式。

- **Slay the Spire 2**（appid 2868840，已提 upstream PR [Droid-Deck/DroidDeck#205](https://github.com/Droid-Deck/DroidDeck/pull/205)，合併後這條換成 upstream 版本）：第一次啟動失敗，是因為遊戲剛裝好就在同一個 session 啟動，跑的是 Linux 原生版；那條路要靠 Valve 的 FEX compat tool，但需要的 x86-64 RootFS（`/usr/share/guestos/fex-mesa`）不存在。Steam 重開後，upstream 的 `bannerlator-steam-compat` 會把已安裝的遊戲改指到 Bannerlator Proton，Steam 再下載 Windows 版，這部分不用改。

  Windows 版在 exe 載入後 19～41 秒崩潰，觸發點是 Proton 的 `tabtip.exe`。Proton 的 explorer.exe 在每個 prefix 開桌面時無條件啟動它（ValveSoftware/wine `experimental_11.0` 的 `programs/explorer/desktop.c`，`start_tabtip_process`，原始碼註解寫「FIXME: hack, run tabtip.exe on startup」）。tabtip 註冊 UI Automation 的焦點事件（`programs/tabtip/tabtip.c`，`add_uia_event_handler`），每次焦點改變，就讀焦點元件的五個屬性。遊戲透過 Godot 的 AccessKit 回應 `WM_GETOBJECT`（log 裡有 `UiaReturnRawElementProvider`），之後 tabtip 的呼叫就跨行程用 COM 在遊戲裡執行。只有 `SteamDeck=1` 時，tabtip 才會叫出 Steam 鍵盤；遊戲行程的 `/proc/<pid>/environ` 沒有 `SteamDeck`，Deck 模式也一樣，所以停用它不會少任何功能。

  證據（2026-10-04，POCO F8 Ultra。同一晚另一個 session 用 `.audit/` 的 log 和原始碼獨立稽核過，證據和每輪原始輸出留在本機 `/Users/jianruicheng/GitHub/DroidDeck-sts2-audit/.audit/`，不在 git 裡）：
  - 沒修正、有 log 的 4 次崩潰（14:36、16:09、16:11、17:44），都發生在 tabtip 的呼叫第一次進到遊戲時。14:36 那份有 `+pid`／`+loaddll`，呼叫方是 pid 0118，載入的是 `tabtip.exe`。
  - 14:36：遊戲的 `wine_rpcrt4_io` 執行緒建立後 6 ms 出現第一個例外，backtrace 是 rpcrt4 → combase → `coreclr.dll`+0x1DC604，另一次呼叫跳到位址 `0x726F74632E`（內容是 ASCII 的「.ctor」）；0.6 秒後另一條執行緒（01b4）出現 .NET 的 `0x80131506`，兩者之間只有時間順序，沒有直接證據。17:44：`rpcrt4.dll`+0x76E6C 的例外 0.21 秒後出現 `c0000409`（位址 `0x6ffa910b49`，在 GodotFmod 裡）。16:09、16:11：遊戲的 RPC 執行緒建立後 12～14 ms，tabtip 就收到 `0x800706ba`，表示遊戲行程已經不在。這兩份 log 裡的 `nested exception on signal stack` 是 Wine 收尾時被殺的執行緒（mmdevapi、services.exe、winedevice.exe 都有），不能當崩潰的證據。
  - 18:01 那次出現同一串 fault，還有 `stub_manager_delete Got page fault when releasing stub`，但遊戲沒死。tabtip 的呼叫是崩潰的必要條件，每次都會出 fault，死不死看運氣。
  - 反向驗證：其他設定照最小集合、只把 tabtip 放回來，3 輪全崩（35、51、52 秒），`c0000409` 位址三次都是 `0x6ffa910b49`。不停用 tabtip、改加 Godot 的 `--accessibility disabled`，3 輪全過。
  - 遊戲裡的物件為什麼會失效，未查明。
  - `=d` 對主程式有效的依據：`dlls/ntdll/unix/loader.c` 的 `open_main_image` 在 load order 是 disabled 時，用 `STATUS_DLL_NOT_FOUND` 結束行程（Win32 錯誤 126），explorer 記 `Couldn't start tabtip.exe: error 126` 後照常進訊息迴圈。ValveSoftware/Proton#4174（The Sims 4）有人給過同樣寫法，但回報者說沒有改善，不算成功案例。

  其他項目由稽核逐項拿掉測試（一輪是冷啟動後撐 150 秒，Godot log 有 `Time to main menu` 而且遊戲還活著才算過）：
  - `DOTNET_GCHeapHardLimit=0x400000000`：拿掉後 coreclr 初始化失敗（`hostfxr_get_runtime_delegate failed with code -2147450743`），2/2。原因未查證。
  - `DOTNET_EnableWriteXorExecute=0`：拿掉後卡在 .NET 啟動，主執行緒 100%，C# 那邊一行都沒輸出，2/2。原因未查證。
  - `DOTNET_TieredCompilation=0`：拿掉後進主選單 76 秒時出現 FEX 例外，1/1，是證據最弱的一項。
  - `--rendering-driver vulkan`：拿掉後 Godot 選 D3D12，swap chain 建不起來。
  - 拿掉也沒事：`icu=d`（遊戲自己的 ICU DLL 照常載入，5/5）、四個 FEX TSO 覆寫（共用的 FEX preset 就夠，10/10）。
  - 現在的最小集合（`tabtip.exe=d`、三個 `DOTNET_*`、`--rendering-driver vulkan`）5 輪全過；多加 `icu=d` 也 5 輪全過。

  相關檔案：`tools/linuxfs/overlay/usr/local/bin/bannerlator-game-env`（`KNOWN_FIXES`、`known_env`、`known_args`、`apply_config` 的三層順序、`main` 在沒有設定檔時也套用）、`tools/tests/test_game_environment.py`（`test_known_fixes_sit_between_shared_and_game_entries` 斷言 StS2 的整組設定，並用暫時加進 `KNOWN_FIXES` 的假遊戲驗證三層順序；`test_known_fix_arguments_and_launches_without_configuration`）、`docs/development/game-environment.md`（套用順序和「Known fixes」一節）。行為底線：StS2 的 Proton log 有 `Couldn't start tabtip.exe`，沒有 `fault packet`；冷啟動能進主選單，撐過 150 秒。

- **DirectAudio for games 從來沒生效（upstream bug）**：`bannerlator-steam-compat` 的 `bl_directaudio` 用 `printf` 把 `[Software\\Wine\\Drivers]` 附加到 prefix 的 `user.reg`。這段字串先經過 Python 字串、再經過 printf，各被跳脫一次，寫進檔案的是單斜線 `[Software\Wine\Drivers]`。wineserver 遇到不認得的跳脫（`\W`、`\D`）會丟掉反斜線，所以讀成名為 `SoftwareWineDrivers` 的機碼，mmdevapi 照預設清單載入 winepulse／winealsa。佐證：`+loaddll` 的 Proton log（例如 14:36 那份）只載入 `winepulse.drv`、`winealsa.drv`；每個 session 的 relay 都有 `listening`，從來沒有 `hello from`。修法分三段。第一段：機碼名稱改用 printf 的 `%s` 參數傳入；已經只有舊錯誤機碼的 prefix，會再補一個正確的。第二段：機碼修好後 mmdevapi 只試 directaudio，載入卻失敗（`c0000135`，找不到 DLL），遊戲完全沒聲音。原因在 Wine 11 的 ntdll 載入器：prefix 裡沒有實體檔案的 builtin，只有建立 prefix 時（`WINEBOOTSTRAPMODE`）才會去 `WINEDLLPATH` 找（`find_builtin_without_file`），平常開遊戲不會。所以每次啟動把 `winedirectaudio.drv` 複製進 prefix 的 `system32`（aarch64-windows 版）和 `syswow64`（i386-windows 版），內容不同才複製；Wine 認出是 builtin 後，unix 端的 `winedirectaudio.so` 照樣從 `WINEDLLPATH` 載入。只修機碼、還沒複製驅動的版本（build6），17:07、17:11 兩次啟動的 Godot log 都有 `WASAPI: init_output_device error` 和 `All audio drivers failed, falling back to the dummy driver`；加上複製以後，稽核跑的 23 輪 Godot log 都沒有這兩行，`FMOD Sound System: Successfully initialized` 都在。第三段：開關關掉時，把 prefix 裡的 `"Audio"="directaudio"` 拿掉，不然 mmdevapi 還是只試 directaudio，關掉開關反而沒聲音。截至 2026-10-04，upstream 沒有對應的 issue 或 PR（#192 是插拔耳機時聲音中斷；回報者觀察到切換「DirectAudio for games」有差，但照這個 bug，那個開關對遊戲其實是無作用的）。相關檔案：`tools/linuxfs/overlay/usr/local/bin/bannerlator-steam-compat`（`BL_DIRECTAUDIO_SETUP` 的 `bl_directaudio`、`bl_directaudio_off`）、`tools/tests/test_game_environment.py`（`test_directaudio_selection_reaches_wine_and_leaves_when_off`：雙斜線機碼、驅動複製進 system32／syswow64、重複啟動不重複附加、關掉時拿掉選用、只有舊機碼的 prefix 會補上正確的）。驗證（StS2，2026-10-04 17:16）：Proton log 有 `mmdevapi:init_driver Selecting driver L"directaudio"`，relay 的 logcat 有 `hello from SlayTheSpire2.e`、`open: buffer 576 frames (12 ms)`、`serving`。行為底線：開關打開時，prefix 的 `user.reg` 有雙斜線的 `[Software\\Wine\\Drivers]` 和 `"Audio"="directaudio"`，`system32`／`syswow64` 有跟 runtime 相同的 `winedirectaudio.drv`；開關關掉時，`user.reg` 裡沒有這個選用。

- **正體中文介面**：`app/src/main/res/values-zh-rTW/strings.xml` 翻完全部 920 條字串、2 組陣列和 4 組複數（中文只有 `other`）；`res/xml/locales_config.xml` 加上 `zh-TW`，Android 的「應用程式語言」會列出它，系統語言是正體中文時也會自動使用。用詞跟 Steam 的正體中文介面一致（控制器、工作階段、畫格生成、快速存取、元件）；提到 Android 系統畫面的地方，照 AOSP `packages/apps/Settings` 和 `frameworks/base/packages/SettingsLib` 的 zh-rTW 原文（「開發人員選項」「無線偵錯」「使用配對碼配對裝置」「IP 位址和通訊埠」「停止限制子程序」「允許這個來源的應用程式」）。側邊欄的 Setup 和工作階段抽屜的 Settings 都譯「設定」，兩者不會出現在同一個畫面；首頁的「Play Steam」譯「啟動 Steam」，提到 Play 的說明文字跟著改。還沒翻到的：檔案管理器裡 37 處直接寫在 Kotlin 的英文（`files/FileManagerScreen.kt`、`FileManagerItems.kt`、`FilePropertiesDialog.kt`），要先抽成字串資源。相關檔案：上面兩個資源檔、`tools/tests/test_translations.py`（每個英文條目都有譯文、沒有多出來的、`formatted` 等屬性一致、佔位符逐條相同；故意刪掉一條或改壞一個佔位符都會失敗）。驗證：手機首頁截圖，側邊欄的「遊戲、桌面、元件、設定、更新」放得下，按鈕是「啟動 Steam」；其他頁面還沒逐頁看。upstream 的 #202 加了簡體中文 `values-zh`，fork 還沒合進來；合併後正體中文的系統會優先用 `values-zh-rTW`，香港（zh-HK）會選哪一份未查證。行為底線：系統或 App 語言是正體中文時，介面是正體中文；`python3 -m unittest tools/tests/test_translations.py` 通過。

追 upstream 時，衝突只要守住上面幾塊，其餘一律取 upstream 版本。

## 合併衝突檢查

合併 upstream 後衝突落在下列檔案時逐項確認：

- `app/src/main/java/com/droiddeck/launcher/runtime/LinuxRuntime.java`（`binds()` 裡的 `syncAndroidCjkFonts(root)` 呼叫、`syncAndroidCjkFonts`／`writeCjkFontRules`／`appendCjkFaceRules`／`androidCjkFace`、`ANDROID_FONTS`／`CJK_FONT_RULES` 常數）
- `tools/linuxfs/desktop/droiddeck-desktop`（預設規則判斷要排除 `droiddeck` 開頭的檔，不然 desktop 永遠不連結 fontconfig 預設規則）
- `tools/linuxfs/overlay/usr/local/bin/bannerlator-session`（`== fonts:` 診斷行；touch watcher 的 `enable_game_touch`／`restore_game_touch`／`game_touch_mark`，以及「Touch in games」開關輪詢；upstream 改 touch watcher 時最容易整段蓋掉，合併後用假 `xprop` 重跑六種情境，或上手機看 session.log 的 `touch mode:` 行。upstream 的 #196 加了「Touch Off」，合併時確認它跟「Touch in games」怎麼共存）
- `app/src/main/java/com/droiddeck/launcher/session/SessionPrefs.kt`、`SessionService.kt`（`writeGameTouchFlag` 要跟 `writeForceFullscreenFlag` 一起在 session 開始時寫）
- `SessionActivity.kt`、`ui/SessionOverlay.kt`、`MainActivity.kt`、`ui/ModeSettingsDialog.kt`、`res/values/strings.xml`、`res/values-es/strings.xml`（`gameTouch`／`onGameTouch` 兩處 UI 的接線）
- `tools/linuxfs/overlay/usr/local/bin/bannerlator-game-env`（`KNOWN_FIXES` 的套用順序：共用 → 已知修正 → 單一遊戲；StS2 是 `tabtip.exe=d`、三個 `DOTNET_*`、`--rendering-driver vulkan` 五項；合併後跑 `python3 -m unittest tools/tests/test_game_environment.py`。upstream 合併 #205 後，這個檔、測試和 `docs/development/game-environment.md` 都改取 upstream 版）
- `tools/linuxfs/overlay/usr/local/bin/bannerlator-steam-compat` 的 `BL_DIRECTAUDIO_SETUP`（raw string；機碼名稱走 `%s`，不要放回 printf 的格式字串裡；驅動複製進 `system32`／`syswow64` 和 `bl_directaudio_off` 都要在；upstream 合併修正後整段換成 upstream 版）
- `docs/development/game-environment.md`（套用順序和「Known fixes」一節，跟 #205 的內容相同）
- `app/src/main/res/values-zh-rTW/strings.xml`、`res/xml/locales_config.xml`（upstream 改了英文字串就跑 `python3 -m unittest tools/tests/test_translations.py`，照失敗訊息補譯文；合併 #202 時 `locales_config.xml` 會跟 `zh` 那行衝突，兩行都留）
- `tools/tests/test_translations.py`（fork 自己加的，upstream 沒有）
