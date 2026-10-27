package io.github.sajadinmaker.vpnbox.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map

/** Theme selection: follow the OS, or force light/dark. */
enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** Persisted UI settings, backed by Preferences DataStore. */
data class AppUiSettings(
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val dynamicColor: Boolean = true,
)

// single-instance delegate — one DataStore per process context
val Context.settingsStore: DataStore<Preferences> by preferencesDataStore(
    name = "ui_settings",
)

private val KEY_THEME = stringPreferencesKey("theme_mode")
private val KEY_DYNAMIC = booleanPreferencesKey("dynamic_color")

/** Reads the settings; a missing or damaged store yields safe defaults. */
fun Context.observeSettings(): Flow<AppUiSettings> = settingsStore.data
    .catch { emit(emptyPreferences()) }
    .map { p ->
        AppUiSettings(
            themeMode = p[KEY_THEME]?.let { n ->
                ThemeMode.entries.firstOrNull { it.name == n }
            } ?: ThemeMode.SYSTEM,
            dynamicColor = p[KEY_DYNAMIC] ?: true,
        )
    }

/** Persist the theme mode; failures surface to the caller (VM logs them). */
suspend fun Context.setThemeMode(mode: ThemeMode) {
    settingsStore.edit { it[KEY_THEME] = mode.name }
}

/** Persist the dynamic-color toggle; failures surface to the caller. */
suspend fun Context.setDynamicColor(on: Boolean) {
    settingsStore.edit { it[KEY_DYNAMIC] = on }
}
