package io.github.sajadinmaker.vpnbox.engine

/**
 * Loads `libovpn3.so` exactly once. Must run before the first
 * `net.openvpn.ovpn3.ClientAPI_OpenVPNClient` instance is built: the
 * generated JNI static initializers resolve `swig_module_init` and the
 * rest of the native bindings, so the library has to be in place first
 * (same contract as ics-openvpn's `static { System.loadLibrary("ovpn3"); }`
 * in OpenVPNThreadv3).
 */
object Ovpn3Lib {
    @Volatile
    private var loaded = false

    fun ensure() {
        if (!loaded) {
            synchronized(this) {
                if (!loaded) {
                    System.loadLibrary("ovpn3")
                    loaded = true
                }
            }
        }
    }
}
