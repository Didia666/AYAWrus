# Malware Detection Mobile App Integration Plan

This plan outlines the steps to integrate the mobile app with your malware detection system, including notifications, quarantine actions, and a 15-day history log.

## User Review Required

> [!IMPORTANT]
> **Backend Integration:** This plan assumes a REST API will be available to fetch history and perform quarantine actions. I will implement the client-side logic (Retrofit) and you will need to provide the endpoint URLs.
> **Notifications:** I will set up the boilerplate for Firebase Cloud Messaging (FCM). You will need to provide the `google-services.json` file to enable actual notification delivery.

## Open Questions

- What is the endpoint for the quarantine action? (e.g., `POST /api/quarantine/{fileId}`)
- What is the format of the history log API? (e.g., `GET /api/history?days=15`)
- Does the `ScanResult` model need additional fields like `fileId` or `filePath` to uniquely identify files for quarantine?

## Proposed Changes

### Core Models & Data

#### [MODIFY] [ScanResult.java](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/java/com/ayawrus/mobile/ScanResult.java)
- Add a unique `id` field.
- Add a `status` field (e.g., `ACTIVE`, `QUARANTINED`).
- Add a `timestamp` field for easier date filtering.

#### [NEW] [MalwareApiService.java](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/java/com/ayawrus/mobile/MalwareApiService.java)
- Define Retrofit interface for `getHistory(int days)` and `quarantineFile(String id)`.

---

### User Interface

#### [MODIFY] [item_detail_bottom_sheet.xml](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/res/layout/item_detail_bottom_sheet.xml)
- Add a "Quarantine" button at the bottom of the sheet.
- The button should only be visible for items with "Malicious" or "Suspicious" verdicts that are not already quarantined.

#### [MODIFY] [ScanDetailBottomSheet.java](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/java/com/ayawrus/mobile/ScanDetailBottomSheet.java)
- Wire up the "Quarantine" button.
- Implement a callback or use a ViewModel to trigger the API call.

#### [MODIFY] [HistoryFragment.java](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/java/com/ayawrus/mobile/HistoryFragment.java)
- Implement logic to fetch history from the API.
- Add a client-side filter to ensure only the last 15 days are shown if the API doesn't support it.

---

### Notifications

#### [NEW] [MyFirebaseMessagingService.java](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/java/com/ayawrus/mobile/MyFirebaseMessagingService.java)
- Handle incoming FCM messages.
- Show a system notification that opens the app's Dashboard or History when tapped.

#### [MODIFY] [AndroidManifest.xml](file:///D:/AYAWRusMobile/AYAWRusMobile/app/src/main/AndroidManifest.xml)
- Register the new Firebase service.
- Add necessary permissions (INTERNET, POST_NOTIFICATIONS).

## Verification Plan

### Automated Tests
- Unit tests for the 15-day date filtering logic.
- Mock API tests for the quarantine action.

### Manual Verification
- Trigger a mock notification and verify it appears on the device.
- Open a "Malicious" item detail, click "Quarantine", and verify the status update.
- Verify that the history log correctly displays entries from the last 15 days only.
