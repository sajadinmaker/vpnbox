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

# --- misc ------------------------------------------------------------------
-dontwarn org.slf4j.**
