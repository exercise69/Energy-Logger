## iOS Shortcut: ChangeWIFI

This shortcut allows the Energy Logger PWA to open the **Wi-Fi settings** directly on an iPhone or iPad.  

> **Note:** The user must create this shortcut manually. Works only on iOS.

### 1. Create the Shortcut

1. Open the **Shortcuts** app on your iPhone/iPad.  
2. Tap **+ → Create Shortcut**.  
3. Name the shortcut: **ChangeWIFI**. (ensure correct spelling or change in code)
4. Add action:
   - Search for **“Open URL”**.  
   - Enter the URL:  
     ```
     prefs:root=WIFI
     ```  
5. Optional: Customize the icon (e.g., Wi-Fi symbol).  
6. Tap **Done** / **Save**.  

Once created, the Energy Logger PWA button will trigger this shortcut to open the Wi-Fi settings automatically.
