package net.linspad.atlasphone.mobile.service

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Domain-free hook: the foreground notification can carry ONE app-supplied action without RecordingService knowing about
 * running. The owner sets label + handler; the service renders the action and calls [invoke] when it is tapped.
 */
class QuickAction {
    private val _label = MutableStateFlow<String?>(null)
    val label: StateFlow<String?> = _label
    @Volatile private var handler: (() -> Unit)? = null

    /** Replaces label and handler together; (null, null) clears. */
    @Synchronized
    fun set(label: String?, handler: (() -> Unit)?) {
        this.handler = handler
        _label.value = label
    }

    fun invoke() { handler?.invoke() }
}
