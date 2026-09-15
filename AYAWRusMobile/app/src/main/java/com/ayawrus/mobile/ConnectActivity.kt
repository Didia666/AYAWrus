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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_connect)
        ApiClient.init(applicationContext)

        statusText = findViewById(R.id.tvConnectionStatus)
        connectButton = findViewById(R.id.btnConnectToAyawrus)

        val deviceName = android.os.Build.MODEL ?: "AYAWrus Mobile"
        ApiClient.saveDeviceName(deviceName)

        connectButton.setOnClickListener {
            openQrScanner()
        }
        statusText.text = "Ready to pair using a QR code from the AYAWrus desktop."
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
