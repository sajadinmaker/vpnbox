package io.github.sajadinmaker.vpnbox.engine

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Process-wide bus between [VpnboxVpnService] (which hosts the OpenVPN 3
 * core, and therefore must own the tun fd itself) and the app's engine
 * wrapper + ViewModel. Everything that changes tunnel state crosses this
 * object; there is exactly one tunnel per process, as in the CLI.
 */
object EngineBus {

    interface ClientHandle {
        /** Ask the core to stop; core exit then tears the tun down. */
        fun stop()
    }

    private val _events = MutableSharedFlow<EngineEvent>(
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val events = _events.asSharedFlow()

    /** True from service start until the OpenVPN3 client thread exits. */
    val tunnelUp = MutableStateFlow(false)

    /** Server label currently shown in the foreground notification. */
    val serverLabel = MutableStateFlow("")

    /** Latest handshake outcome, reset by the service before each attempt. */
    internal val handshake: MutableStateFlow<EngineEvent?> = MutableStateFlow(null)

    internal fun emit(e: EngineEvent) {
        if (e is EngineEvent.HandshakeOk || e is EngineEvent.HandshakeFailed) {
            handshake.value = e
        }
        _events.tryEmit(e)
    }

    fun markStarting(label: String) {
        serverLabel.value = label
        handshake.value = null
    }

    fun markRunning(up: Boolean) {
        tunnelUp.value = up
    }

    /** The OpenVPN3 client instance the service is hosting right now. */
    @Volatile
    private var client: ClientHandle? = null

    fun attach(c: ClientHandle?) {
        client = c
    }

    fun currentClient(): ClientHandle? = client

    fun currentClientClear() {
        client = null
        handshake.value = null
    }
}
