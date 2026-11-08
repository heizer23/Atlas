package net.linspad.atlasphone.running.ui

import android.os.Build
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import kotlinx.coroutines.launch
import net.linspad.atlasphone.running.auth.PairingPayload
import net.linspad.atlasphone.running.session.RunController

/**
 * Pairing: code entry (typed, pasted payload or QR scan with the Google code scanner), server URL (https only,
 * prefilled from the QR payload or the last value) and device name. Shows generic error text; the token is stored
 * Keystore-encrypted by [RunController.pair] and never shown.
 */
@Composable
fun PairingScreen(onPaired: () -> Unit, onSkip: () -> Unit = {}) {
    val context = LocalContext.current
    val controller = remember { RunController.get(context) }
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf(controller.tokens.baseUrl() ?: "") }
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf(Build.MODEL ?: "Phone") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun accept(raw: String) {
        val parsed = PairingPayload.parse(raw)
        if (parsed == null) { code = raw; return }
        parsed.baseUrl?.let { url = it }
        code = parsed.code
        error = null
    }

    Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Pair this phone with Atlas", style = MaterialTheme.typography.headlineSmall)
        Text("In Atlas open Running, then Devices, then Pair phone. Enter the code or scan the QR code. Tailscale must be running on this phone.")
        OutlinedTextField(url, { url = it.trim() }, label = { Text("Server URL (https)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(code, { accept(it) }, label = { Text("Pairing code") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(name, { name = it }, label = { Text("Device name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy, onClick = {
                val parsed = PairingPayload.parse(code)
                when {
                    parsed == null -> error = "That is not a valid pairing code."
                    name.isBlank() -> error = "Enter a device name."
                    else -> {
                        busy = true; error = null
                        scope.launch {
                            val result = controller.pair(parsed.baseUrl ?: url, parsed.code, name.trim())
                            busy = false
                            if (result == null) onPaired() else error = result
                        }
                    }
                }
            }) { Text(if (busy) "Pairing..." else "Pair") }
            OutlinedButton(onClick = {
                val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
                GmsBarcodeScanning.getClient(context, options).startScan()
                    .addOnSuccessListener { barcode -> barcode.rawValue?.let { accept(it) } }
                    .addOnFailureListener { error = "Scanning is not available. Type the code instead." }
            }) { Text("Scan QR") }
        }
        OutlinedButton(onClick = onSkip) { Text("Not now (Free Run works without Atlas)") }
    }
}
