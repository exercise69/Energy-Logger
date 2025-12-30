# rename this file to --> secrets_shelly.py 
# fill in your own data in the relevant fields
# and save it in the root of your CIRCUITPY drive
# =========================

secrets = { 
    # Access Point settings for the QT-Py Board
    "ap_ssid": "QT-LOGGER",           # Name of the board's Access Point
    "ap_password": "your_password",   # Password for the board's AP

    # Shelly Wi-Fi connection data
    "shelly_ap_ssid": "ShellyPlusPlugS-XXXXXX", # SSID of your Shelly device
    "shelly_ap_password": "your_password",      # Password for Shelly AP (if any)
    "shelly_ip": "192.168.33.1",                # Default Shelly AP IP this is the default by Shelly

    # Hardware Pins
    "sd_cs_pin": "A1",                # Chip-Select Pin for SD card module

    # MQTT Settings (Optional)
    "mqtt_enabled": False,            # Set to True to enable MQTT
    "mqtt_broker": "mqtt.example.com",# MQTT Broker address
    "mqtt_port": 1883,                # Standard MQTT port or custom port
    "mqtt_username": "user",          # MQTT username
    "mqtt_password": "password",      # MQTT password
    "mqtt_topic": "shelly/energy",    # Topic to publish data

    # Timing and Logging
    "poll_interval": 10,              # How often to poll Shelly (seconds)
    "logging_enabled": True,          # Set to True to enable SD card logging
}