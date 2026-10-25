package com.droiddeck.launcher.runtime

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AndroidCjkFaceTest {
    private fun face(tag: String): String? = LinuxRuntime.androidCjkFace(Locale.forLanguageTag(tag))

    @Test fun chineseByRegionAndScript() {
        assertEquals("TC", face("zh-TW"))
        assertEquals("TC", face("zh-Hant"))
        assertEquals("TC", face("zh-Hant-TW"))
        assertEquals("HK", face("zh-HK"))
        assertEquals("HK", face("zh-Hant-MO"))
        assertEquals("SC", face("zh-CN"))
        assertEquals("SC", face("zh-Hans-SG"))
        assertEquals("SC", face("zh"))
    }

    @Test fun japaneseKoreanAndOthers() {
        assertEquals("JP", face("ja-JP"))
        assertEquals("KR", face("ko-KR"))
        assertNull(face("en-US"))
        assertNull(face("es"))
    }
}
