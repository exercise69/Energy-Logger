# secrets_example.py — template. Copy to secrets.py, fill in your own values
# and put secrets.py into the root of CIRCUITPY. secrets.py is never
# committed (.gitignore).

secrets = {
    # Access point of the logger (your phone joins this one)
    "ap_ssid":     "Energy-Logger",
    "ap_password": "at-least-8-characters",   # WPA2: 8 to 63 characters

    # Wi-Fi of the Shelly (Shelly in AP mode)
    "shelly_ap_ssid":     "ShellyPlusPlugS-XXXXXXXXXXXX",
    "shelly_ap_password": "your_password",
}
