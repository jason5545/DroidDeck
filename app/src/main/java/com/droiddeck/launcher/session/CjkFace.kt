package com.droiddeck.launcher.session

import java.util.Locale

/**
 * The Noto Sans CJK face for a language: the session hands it to droiddeck-session as
 * BL_CJK_FACE, which puts that face first for CJK text that names no language - most of Wine's.
 * Text that names its language already gets that language's face (66-droiddeck-device-fonts.conf);
 * without this, untagged Chinese fell to the Korean face that 65-nonlatin.conf lists.
 */
object CjkFace {
    /** "SC", "TC", "HK", "JP" or "KR", or null for a language that is none of them. */
    fun forLocale(locale: Locale): String? = when (locale.language) {
        "ja" -> "JP"
        "ko" -> "KR"
        "zh" -> when {
            locale.country == "HK" || locale.country == "MO" -> "HK"
            locale.country == "TW" || locale.script == "Hant" -> "TC"
            else -> "SC"
        }
        else -> null
    }
}
