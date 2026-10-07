package com.ayawrus.mobile

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.gson.Gson
import com.google.zxing.integration.android.IntentIntegrator
import org.json.JSONObject
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.util.UUID

class ConnectActivity : AppCompatActivity() {
    private lateinit var statusText: TextView
    private lateinit var connectButton: Button
    private lateinit var retryButton: Button

    private enum class PairingUiState {
        FRESH,
        VERIFYING,
        UNREACHABLE_REMEMBERED,
        INVALIDATED
    }

    private var currentUiState = PairingUiState.FRESH

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_connect)
        ApiClient.init(applicationContext)

        statusText = findViewById(R.id.tvConnectionStatus)
        connectButton = findViewById(R.id.btnConnectToAyawrus)
        retryButton = findViewById(R.id.btnRetryConnection)

        val deviceName = android.os.Build.MODEL ?: "AYAWrus Mobile"
        ApiClient.saveDeviceName(deviceName)

        val savedUrl = ApiClient.getBaseUrl()
        val hasSavedHost = savedUrl != "http://10.0.2.2:5000/"
        val hasAnyPairingData = hasSavedHost || ApiClient.getSystemId().isNotBlank() || ApiClient.hasSession()

        if (hasAnyPairingData) {
            setUiState(PairingUiState.VERIFYING)
            statusText.text = "Verifying saved connection to AYAWrus desktop…"
            verifySavedConnectionAndLaunch()
        } else {
            setUiState(PairingUiState.FRESH)
            statusText.text = "Ready to pair using a QR code from the AYAWrus desktop."
        }

        retryButton.setOnClickListener {
            setUiState(PairingUiState.VERIFYING)
            statusText.text = "Re-checking connection to AYAWrus desktop…"
            verifySavedConnectionAndLaunch()
        }

        connectButton.setOnClickListener {
            if (currentUiState == PairingUiState.UNREACHABLE_REMEMBERED) {
                ApiClient.clearAllPairing()
            }
            openQrScanner()
        }
    }

    private fun setUiState(state: PairingUiState) {
        currentUiState = state
        runOnUiThread {
            when (state) {
                PairingUiState.FRESH -> {
                    retryButton.visibility = android.view.View.GONE
                    connectButton.text = "Scan QR Code"
                    connectButton.isEnabled = true
                }
                PairingUiState.VERIFYING -> {
                    retryButton.visibility = android.view.View.GONE
                    connectButton.text = "Scan QR Code"
                    connectButton.isEnabled = false
                }
                PairingUiState.UNREACHABLE_REMEMBERED -> {
                    retryButton.visibility = android.view.View.VISIBLE
                    connectButton.text = "Pair New Desktop"
                    connectButton.isEnabled = true
                }
                PairingUiState.INVALIDATED -> {
                    retryButton.visibility = android.view.View.GONE
                    connectButton.text = "Scan QR Code"
                    connectButton.isEnabled = true
                }
            }
        }
    }

    private fun goToMain() {
        val intent = Intent(this@ConnectActivity, MainActivity::class.java)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        startActivity(intent)
        finish()
    }

    private fun verifySavedConnectionAndLaunch() {
        val hasToken = ApiClient.hasSession()
        val hasSystemId = ApiClient.getSystemId().isNotBlank()
        val hasSavedHost = ApiClient.getBaseUrl() != "http://10.0.2.2:5000/"

        if (!hasSavedHost || !hasSystemId) {
            Log.w("ConnectActivity", "Partial/incomplete pairing state found (no host or no system_id). Clearing and staying on QR.")
            ApiClient.clearAllPairing()
            setUiState(PairingUiState.INVALIDATED)
            statusText.text = "Ready to pair using a QR code from the AYAWrus desktop."
            return
        }

        if (hasToken) {
            Log.i("ConnectActivity", "Saved token found — verifying validity via /api/mobile/status before launching dashboard.")
            try {
                ApiClient.getService().getMobileStatus().enqueue(object : Callback<MalwareApiService.MobileStatusResponse> {
                    override fun onResponse(
                        call: Call<MalwareApiService.MobileStatusResponse>,
                        response: Response<MalwareApiService.MobileStatusResponse>
                    ) {
                        if (response.isSuccessful && response.body() != null) {
                            Log.i("ConnectActivity", "/api/mobile/status OK (HTTP 2xx) — session is still valid, going to dashboard.")
                            runOnUiThread { goToMain() }
                        } else if (response.code() == 401) {
                            Log.w("ConnectActivity", "/api/mobile/status returned 401 — token expired. Clearing full pairing state and staying on QR.")
                            ApiClient.clearAllPairing()
                            setUiState(PairingUiState.INVALIDATED)
                            runOnUiThread {
                                statusText.text = "Session expired. Re-scan the QR code from the desktop to pair again."
                                Toast.makeText(this@ConnectActivity, "Session expired. Please re-scan the QR code.", Toast.LENGTH_LONG).show()
                            }
                        } else {
                            Log.w("ConnectActivity", "/api/mobile/status returned HTTP ${response.code()} — clearing stale state and staying on QR.")
                            ApiClient.clearAllPairing()
                            setUiState(PairingUiState.INVALIDATED)
                            runOnUiThread {
                                statusText.text = "Saved connection is no longer valid. Re-scan the QR code to pair again."
                            }
                        }
                    }

                    override fun onFailure(call: Call<MalwareApiService.MobileStatusResponse>, t: Throwable) {
                        Log.w("ConnectActivity", "/api/mobile/status call failed (network unreachable): ${t.message}. KEEPING saved pairing state — desktop may be offline temporarily.")
                        setUiState(PairingUiState.UNREACHABLE_REMEMBERED)
                        val rememberedHost = try {
                            java.net.URI(ApiClient.getBaseUrl()).host ?: "your desktop"
                        } catch (_: Throwable) { "your desktop" }
                        runOnUiThread {
                            statusText.text = "Can't reach AYAWrus desktop ($rememberedHost).\nIt may be turned off, asleep, or on a different Wi-Fi.\n\nTap Retry when your desktop is back on, or Pair New Desktop to scan a new QR."
                            Toast.makeText(
                                this@ConnectActivity,
                                "Desktop not reachable right now. Saved pairing kept — tap Retry later.",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                })
            } catch (t: Throwable) {
                Log.w("ConnectActivity", "verifySavedConnection crashed (status path): ${t.message}")
                setUiState(PairingUiState.UNREACHABLE_REMEMBERED)
                statusText.text = "Can't reach AYAWrus desktop. It may be turned off — tap Retry when it's back on."
            }
        } else {
            tryReconnect()
        }
    }

    private fun tryReconnect() {
        val refresh = ApiClient.getService()
        try {
            refresh.refreshSession().enqueue(object : Callback<MalwareApiService.MobilePairingResponse> {
                override fun onResponse(
                    call: Call<MalwareApiService.MobilePairingResponse>,
                    response: Response<MalwareApiService.MobilePairingResponse>
                ) {
                    if (response.isSuccessful && response.body() != null) {
                        val body = response.body()!!
                        if (body.success && !body.access_token.isNullOrBlank()) {
                            ApiClient.saveAccessToken(body.access_token)
                            if (!body.system_id.isNullOrBlank()) {
                                ApiClient.saveSystemId(body.system_id)
                            }
                            Log.i("ConnectActivity", "Session refresh succeeded — going to MainActivity.")
                            runOnUiThread { goToMain() }
                            return
                        }
                    }
                    Log.w("ConnectActivity", "Session refresh failed (HTTP ${response.code()}) — clearing partial state and staying on QR.")
                    ApiClient.clearAllPairing()
                    setUiState(PairingUiState.INVALIDATED)
                    runOnUiThread {
                        statusText.text = "Saved connection is no longer valid. Re-scan the QR code from the desktop."
                    }
                }

                override fun onFailure(call: Call<MalwareApiService.MobilePairingResponse>, t: Throwable) {
                    Log.w("ConnectActivity", "Session refresh call failed (network unreachable): ${t.message}. KEEPING saved state — desktop is probably offline temporarily.")
                    setUiState(PairingUiState.UNREACHABLE_REMEMBERED)
                    val rememberedHost = try {
                        java.net.URI(ApiClient.getBaseUrl()).host ?: "your desktop"
                    } catch (_: Throwable) { "your desktop" }
                    runOnUiThread {
                        statusText.text = "Can't reach AYAWrus desktop ($rememberedHost).\nIt may be turned off or asleep.\n\nTap Retry when it's back on, or Pair New Desktop to scan a new QR."
                    }
                }
            })
        } catch (t: Throwable) {
            Log.w("ConnectActivity", "tryReconnect crashed: ${t.message}")
            setUiState(PairingUiState.UNREACHABLE_REMEMBERED)
            statusText.text = "Can't reach AYAWrus desktop. It may be turned off — tap Retry when it's back on."
        }
    }

    private fun openQrScanner() {
        val integrator = IntentIntegrator(this)
        integrator.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
        integrator.setPrompt("Scan the AYAWrus pairing QR code")
        integrator.setBeepEnabled(true)
        integrator.setOrientationLocked(true)
        integrator.setCaptureActivity(ScannerActivity::class.java)
        integrator.initiateScan()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data)
        if (result == null) {
            Toast.makeText(this, "Scan cancelled.", Toast.LENGTH_SHORT).show()
            return
        }
        if (result.contents == null) {
            Toast.makeText(this, "Unable to read the QR code.", Toast.LENGTH_SHORT).show()
            return
        }
        handleQrPayload(result.contents)
    }

    private fun handleQrPayload(payloadText: String) {
        try {
            var pairingToken = ""
            var host = ""
            var port = 5000
            var systemId = ""
            if (payloadText.startsWith("http://") || payloadText.startsWith("https://")) {
                val uri = Uri.parse(payloadText)
                pairingToken = uri.getQueryParameter("pairing_token") ?: ""
                host = uri.host ?: ""
                port = uri.getQueryParameter("port")?.toIntOrNull() ?: uri.port.takeIf { it > 0 } ?: 5000
                systemId = uri.getQueryParameter("system_id") ?: ""
            } else {
                val json = JSONObject(payloadText)
                pairingToken = json.optString("pairing_token", "")
                host = json.optString("host", "")
                port = json.optInt("port", 5000)
                systemId = json.optString("system_id", "")
            }
            if (pairingToken.isBlank()) {
                statusText.text = "Invalid pairing code. Please scan the AYAWrus QR again."
                return
            }
            statusText.text = "Connecting to AYAWrus…"

            ApiClient.saveConnection(host, port)
            val request = MalwareApiService.MobilePairingRequest(pairingToken, ApiClient.getDeviceName(), UUID.randomUUID().toString())
            ApiClient.getService().pairDevice(request).enqueue(object : Callback<MalwareApiService.MobilePairingResponse> {
                override fun onResponse(
                    call: Call<MalwareApiService.MobilePairingResponse>,
                    response: Response<MalwareApiService.MobilePairingResponse>
                ) {
                    if (response.isSuccessful && response.body() != null) {
                        val body = response.body()!!
                        if (body.success && !body.access_token.isNullOrBlank()) {
                            ApiClient.saveAccessToken(body.access_token)
                            if (!body.system_id.isNullOrBlank()) {
                                ApiClient.saveSystemId(body.system_id)
                            }
                            Toast.makeText(this@ConnectActivity, "Connected to AYAWrus", Toast.LENGTH_SHORT).show()
                            val intent = Intent(this@ConnectActivity, MainActivity::class.java)
                            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                            startActivity(intent)
                            finish()
                            return
                        }
                        val errorText = body.message ?: body.error ?: "Unable to connect to AYAWrus."
                        runOnUiThread { statusText.text = errorText }
                    } else {
                        val errorText = when (response.code()) {
                            401 -> "Pairing code has expired or is invalid."
                            409 -> "Pairing code has already been used."
                            else -> "AYAWrus server rejected the connection."
                        }
                        runOnUiThread { statusText.text = errorText }
                    }
                }

                override fun onFailure(call: Call<MalwareApiService.MobilePairingResponse>, t: Throwable) {
                    Log.w("ConnectActivity", "Pairing failed: ${t.message}")
                    runOnUiThread {
                        statusText.text = "Unable to connect to AYAWrus on this Wi-Fi network."
                        Toast.makeText(this@ConnectActivity, "AYAWrus is not reachable on this Wi-Fi network.", Toast.LENGTH_LONG).show()
                    }
                }
            })
        } catch (ex: Exception) {
            statusText.text = "This QR code is not a valid AYAWrus pairing code."
            Log.w("ConnectActivity", "Bad QR payload: ${ex.message}")
        }
    }
}
