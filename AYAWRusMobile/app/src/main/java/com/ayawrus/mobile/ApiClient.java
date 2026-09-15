package com.ayawrus.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import java.io.IOException;

import okhttp3.Interceptor;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ApiClient {
    private static final String PREFS_NAME = "ayawrus_mobile_state";
    private static final String KEY_BASE_URL = "base_url";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_SYSTEM_ID = "system_id";
    private static final String KEY_DEVICE_NAME = "device_name";
    private static final String DEFAULT_BASE_URL = "http://10.0.2.2:5000/";

    public static String BASE_URL = normalizeBaseUrl(DEFAULT_BASE_URL);
    private static Context appContext;
    private static Retrofit retrofit = null;

    public static void init(Context context) {
        if (context == null) return;
        appContext = context.getApplicationContext();
        String savedBaseUrl = getPrefs().getString(KEY_BASE_URL, DEFAULT_BASE_URL);
        BASE_URL = normalizeBaseUrl(savedBaseUrl);
        retrofit = null;
    }

    public static void saveConnection(String host, int port) {
        String url = "http://" + host + ":" + port + "/";
        saveBaseUrl(url);
        BASE_URL = normalizeBaseUrl(url);
        retrofit = null;
    }

    public static void saveBaseUrl(String url) {
        getPrefs().edit().putString(KEY_BASE_URL, url).apply();
        BASE_URL = normalizeBaseUrl(url);
        retrofit = null;
    }

    public static String getBaseUrl() {
        return BASE_URL;
    }

    public static void saveAccessToken(String token) {
        getPrefs().edit().putString(KEY_ACCESS_TOKEN, token).apply();
    }

    public static void clearSession() {
        getPrefs().edit().remove(KEY_ACCESS_TOKEN).remove(KEY_SYSTEM_ID).apply();
    }

    public static boolean hasSession() {
        return getPrefs().getString(KEY_ACCESS_TOKEN, "") != null
                && !getPrefs().getString(KEY_ACCESS_TOKEN, "").isEmpty();
    }

    public static String getAccessToken() {
        return getPrefs().getString(KEY_ACCESS_TOKEN, "");
    }

    public static String getSystemId() {
        return getPrefs().getString(KEY_SYSTEM_ID, "");
    }

    public static void saveSystemId(String systemId) {
        getPrefs().edit().putString(KEY_SYSTEM_ID, systemId).apply();
    }

    public static void saveDeviceName(String deviceName) {
        getPrefs().edit().putString(KEY_DEVICE_NAME, deviceName).apply();
    }

    public static String getDeviceName() {
        return getPrefs().getString(KEY_DEVICE_NAME, "AYAWrus Mobile");
    }

    private static SharedPreferences getPrefs() {
        if (appContext == null) {
            throw new IllegalStateException("ApiClient.init(Context) must be called before use");
        }
        return appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    private static String normalizeBaseUrl(String baseUrl) {
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            return DEFAULT_BASE_URL;
        }
        String normalized = baseUrl.trim();
        if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
            normalized = "http://" + normalized;
        }
        return normalized.endsWith("/") ? normalized : normalized + "/";
    }

    public static MalwareApiService getService() {
        if (appContext == null) {
            throw new IllegalStateException("ApiClient.init(Context) must be called before use");
        }
        if (retrofit == null) {
            String effectiveUrl = getPrefs().getString(KEY_BASE_URL, BASE_URL);
            BASE_URL = normalizeBaseUrl(effectiveUrl);
            OkHttpClient client = new OkHttpClient.Builder()
                    .addInterceptor(new Interceptor() {
                        @Override
                        public Response intercept(Chain chain) throws IOException {
                            Request original = chain.request();
                            String token = getPrefs().getString(KEY_ACCESS_TOKEN, "");
                            if (token == null || token.trim().isEmpty()) {
                                return chain.proceed(original);
                            }
                            Request updated = original.newBuilder()
                                    .header("Authorization", "Bearer " + token)
                                    .build();
                            return chain.proceed(updated);
                        }
                    })
                    .build();
            retrofit = new Retrofit.Builder()
                    .baseUrl(BASE_URL)
                    .client(client)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build();
        }
        return retrofit.create(MalwareApiService.class);
    }
}
