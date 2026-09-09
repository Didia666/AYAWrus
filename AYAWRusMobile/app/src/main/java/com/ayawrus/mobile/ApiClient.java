package com.ayawrus.mobile;

import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ApiClient {

    private static final String CONFIGURED_BASE_URL = "http://10.167.14.150:5000/"; // Laptop Wi-Fi address reachable by the phone
    public static final String BASE_URL = normalizeBaseUrl(CONFIGURED_BASE_URL);
    private static Retrofit retrofit = null;

    private static String normalizeBaseUrl(String baseUrl) {
        String normalized = baseUrl.trim().replaceFirst("^(https?://)\\s+", "$1");
        return normalized.endsWith("/") ? normalized : normalized + "/";
    }

    public static MalwareApiService getService() {
        if (retrofit == null) {
            retrofit = new Retrofit.Builder()
                    .baseUrl(BASE_URL)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build();
        }
        return retrofit.create(MalwareApiService.class);
    }
}
