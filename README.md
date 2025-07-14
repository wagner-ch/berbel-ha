# Berbel Skyline Edge Base - Home Assistant Integration

A Home Assistant integration for the **Berbel Skyline Edge Base** range hood with Bluetooth Low Energy (BLE) connectivity.

> **⚠️ Device Compatibility**: This integration is specifically developed and tested for the **Berbel Skyline Edge Base** model. Other Berbel range hoods may work but are not tested or officially supported.

## ✨ Features

### 🌬️ Fan Control
- **3 Speed Levels**: Precise control with 0-3 speed settings
- **Percentage Control**: Set speed as percentage (0-100%)
- **Direct On/Off**: Toggle between off and level 1
- **Postrun Status**: Monitor automatic fan postrun operation

### 💡 Dual Light Control
- **Separate Top & Bottom Lights**: Independent control of both light zones
- **Brightness Control**: 0-100% dimming for each light
- **Color Temperature**: Adjustable from 2700K (warm) to 6500K (cool)
- **Individual On/Off**: Control each light independently

### 🔧 Smart Features
- **Automatic Discovery**: Plug-and-play Bluetooth setup
- **Local Control**: No cloud connection required
- **Real-time Updates**: Status updates every 18 seconds
- **Connection Pooling**: Optimized BLE performance
- **Error Handling**: Robust connection management with automatic retry

## 🏠 Home Assistant Entities

Each Berbel Skyline Edge Base device creates **4 entities**:

1. **🌬️ Fan Entity** - Speed control and on/off switching
2. **💡 Light Top Entity** - Upper light with brightness and color temperature
3. **💡 Light Bottom Entity** - Lower light with brightness and color temperature  
4. **🔄 Postrun Binary Sensor** - Shows when automatic postrun is active

## 📋 Requirements

- **Home Assistant**: 2023.1 or newer
- **Bluetooth**: Built-in Bluetooth or USB Bluetooth adapter
- **Device**: Berbel Skyline Edge Base range hood
- **Python**: 3.10 or newer

## 🚀 Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations" 
3. Click the three dots menu → "Custom repositories"
4. Add this repository URL: `https://github.com/dirkbloessl/berbel-ha`
5. Category: "Integration"
6. Click "Add" and then "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Extract the `custom_components/berbel` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## ⚙️ Configuration

### Automatic Discovery (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Your Berbel Skyline Edge Base should appear in "Discovered" devices
3. Click "Configure" and follow the setup wizard

### Manual Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Berbel"
3. Select your device from the list
4. Complete the configuration

## 📱 Usage Examples

### Basic Fan Control
```yaml
# Turn fan on (level 1)
service: fan.turn_on
target:
  entity_id: fan.berbel_fan

# Set specific speed (33% = level 1, 66% = level 2, 100% = level 3)
service: fan.set_percentage
target:
  entity_id: fan.berbel_fan
data:
  percentage: 66
```

### Light Control
```yaml
# Turn on top light with 75% brightness and warm white
service: light.turn_on
target:
  entity_id: light.berbel_light_top
data:
  brightness_pct: 75
  color_temp: 370  # Warm white

# Turn on both lights
service: light.turn_on
target:
  entity_id: 
    - light.berbel_light_top
    - light.berbel_light_bottom
```

### Automation Examples
```yaml
# Turn on lights when cooking
automation:
  - alias: "Kitchen Hood Lights On"
    trigger:
      platform: state
      entity_id: binary_sensor.kitchen_motion
      to: 'on'
    action:
      service: light.turn_on
      target:
        entity_id: 
          - light.berbel_light_top
          - light.berbel_light_bottom
      data:
        brightness_pct: 80

# Auto fan when high humidity
automation:
  - alias: "Kitchen Hood Auto Fan"
    trigger:
      platform: numeric_state
      entity_id: sensor.kitchen_humidity
      above: 70
    action:
      service: fan.set_percentage
      target:
        entity_id: fan.berbel_fan
      data:
        percentage: 66  # Level 2
```

## 🔧 Advanced Services

The integration provides additional services for advanced control:

### `berbel.set_immediate_refresh`
Control immediate status updates after commands (for performance tuning):
```yaml
service: berbel.set_immediate_refresh
data:
  enabled: false  # Disable for better performance
```

### `berbel.disconnect_ble`
Manually disconnect BLE connection (useful for troubleshooting):
```yaml
service: berbel.disconnect_ble
```

## 🐛 Troubleshooting

### Connection Issues
- Ensure the range hood is powered on and within Bluetooth range
- Check that no other device is connected to the range hood
- Try restarting the Bluetooth service: `sudo systemctl restart bluetooth`

### Performance Issues
- Disable immediate refresh: Use `berbel.set_immediate_refresh` with `enabled: false`
- Check for interference from other Bluetooth devices
- Ensure stable power supply to the range hood

### Debug Logging
Add to your `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.berbel: debug
```

## 🔄 Version History

### v0.1.0 (Current)
- Initial release for Berbel Skyline Edge Base
- Fan control with 3 speed levels
- Dual light control with brightness and color temperature
- Postrun status monitoring
- Optimized BLE connection pooling
- Automatic device discovery

## 🤝 Contributing

Contributions are welcome! Please read the contributing guidelines before submitting pull requests.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This integration is not officially affiliated with or endorsed by berbel Ablufttechnik GmbH. It is an independent, community-driven project.

Use at your own risk. The developer is not responsible for any damage to your device or property.