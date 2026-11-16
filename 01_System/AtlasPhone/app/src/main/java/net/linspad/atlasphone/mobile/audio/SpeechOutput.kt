package net.linspad.atlasphone.mobile.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale

/** What a speaking client needs; [SpeechOutput] is the Android implementation, tests use a fake. */
interface SpeechPort {
    /** Starts the engine in the background if needed (idempotent, never blocks). */
    fun prepare()
    /** Queue-flush speak; false when UNAVAILABLE or not yet initialised (the caller shows the text only). Never throws. */
    fun speak(text: String): Boolean
    /** Stop speaking, release focus and the engine. Idempotent. */
    fun stop()
    fun isAvailable(): Boolean
}

/**
 * Text-to-speech through the system engine (domain-free: speaks a string, knows nothing about running). SPEECH1: utterances use
 * USAGE_ASSISTANCE_NAVIGATION_GUIDANCE and request transient audio focus that lets music duck briefly, abandoned when the utterance
 * ends. This is a scoped exception to the "no audio focus" rule, which continues to apply to ClickEngine only. No TTS engine is
 * created at construction; initialisation and speech are asynchronous; nothing here throws or touches location/HR/capture.
 */
class SpeechOutput(private val context: Context, private val log: (String) -> Unit) : SpeechPort {
    enum class State { IDLE, READY, UNAVAILABLE }

    private val _state = MutableStateFlow(State.IDLE)
    val state: StateFlow<State> = _state

    private val lock = Any()
    private var tts: TextToSpeech? = null
    private var initializing = false
    private var focus: AudioFocusRequest? = null
    private var utterance = 0L

    private val attributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()

    override fun prepare() {
        synchronized(lock) {
            if (tts != null || initializing || _state.value == State.UNAVAILABLE) return
            initializing = true
            try {
                tts = TextToSpeech(context.applicationContext) { status -> onInit(status) }
            } catch (e: Exception) {
                initializing = false
                _state.value = State.UNAVAILABLE
                log("Speech unavailable (${e.javaClass.simpleName})")
            }
        }
    }

    private fun onInit(status: Int) {
        synchronized(lock) {
            initializing = false
            val engine = tts
            if (engine == null) return   // stopped while initialising
            val ok = try {
                status == TextToSpeech.SUCCESS &&
                    engine.setLanguage(Locale.ENGLISH).let { it != TextToSpeech.LANG_MISSING_DATA && it != TextToSpeech.LANG_NOT_SUPPORTED }
            } catch (e: Exception) { false }
            if (!ok) {
                _state.value = State.UNAVAILABLE
                log("Speech unavailable (engine or language)")
                runCatching { engine.shutdown() }
                tts = null
                return
            }
            runCatching {
                engine.setAudioAttributes(attributes)
                engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {}
                    override fun onDone(utteranceId: String?) = abandonFocus()
                    @Deprecated("Deprecated in Java") override fun onError(utteranceId: String?) = abandonFocus()
                    override fun onError(utteranceId: String?, errorCode: Int) = abandonFocus()
                })
            }
            _state.value = State.READY
        }
    }

    override fun speak(text: String): Boolean {
        synchronized(lock) {
            when (_state.value) {
                State.UNAVAILABLE -> return false
                State.IDLE -> { prepare(); return false }
                State.READY -> Unit
            }
            val engine = tts ?: return false
            return try {
                requestFocus()
                engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "coach-${utterance++}") == TextToSpeech.SUCCESS
            } catch (e: Exception) {
                log("Speech failed (${e.javaClass.simpleName})")
                false
            }
        }
    }

    override fun stop() {
        synchronized(lock) {
            runCatching { tts?.stop() }
            runCatching { tts?.shutdown() }
            tts = null
            initializing = false
            if (_state.value == State.READY) _state.value = State.IDLE
            abandonFocus()
        }
    }

    override fun isAvailable(): Boolean = _state.value != State.UNAVAILABLE

    private fun requestFocus() {
        val am = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(attributes).setOnAudioFocusChangeListener { }.build()
        focus = request
        runCatching { am.requestAudioFocus(request) }
    }

    private fun abandonFocus() {
        synchronized(lock) {
            val request = focus ?: return
            focus = null
            val am = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
            runCatching { am.abandonAudioFocusRequest(request) }
        }
    }
}
