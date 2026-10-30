# vpnbox release rules (R8)
# Compose itself needs no rules under the Compose compiler plugin; the
# reflective parts that must survive shrinking are kotlinx.serialization
# (Server/Domain cache) and DataStore.

-keepattributes AnnotationDefault, InnerClasses, Signature, *Annotation*

# --- kotlinx.serialization -------------------------------------------------
-dontnote kotlinx.serialization.AnnotationsKt
# Keep the generated *$serializer classes for app models
-keep,includedescriptorclasses class io.github.sajadinmaker.vpnbox.**$$serializer { *; }
-keepclassmembers class io.github.sajadinmaker.vpnbox.** {
    *** Companion;
}
-keepclasseswithmembers class io.github.sajadinmaker.vpnbox.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-dontwarn kotlinx.serialization.**

# --- OpenVPN 3 SWIG bindings ----------------------------------------------
# The native core resolves the generated JNI callbacks by exact name at
# swig_module_init time (SwigDirector_* statics with ovpn3 class names in
# their signatures) — renaming or dropping any of them crashes
# NoSuchMethodError at the first connect. Keep the whole generated package
# untouched (small; ~250 kB), exactly as ics-openvpn does.
-keep class net.openvpn.ovpn3.** { *; }

# --- misc ------------------------------------------------------------------
-dontwarn org.slf4j.**
