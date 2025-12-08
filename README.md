# Python Badge Launcher

A MicroPython-based launcher for the Badge, using LVGL (Light and Versatile Graphics Library) for the UI. This project provides a robust application launcher with games, tools, and media players.

## Prerequisites

- **Hardware**: BeagleBadge (or compatible Linux-based badge device)
- **OS**: Linux distribution with `systemd` (e.g., Debian, Yocto)
- **Host System Requirements**:
    - `gcc` (for compiling asset tools)
    - `sshpass` (optional, for easier deployment scripts)

## System Requirements on Device

The following system packages are recommended for full functionality:

- `i2c-tools` (for I2C Scanner)
  - Install via: `apt install i2c-tools` or `opkg install i2c-tools`

## Installation

### 1. Build Asset Tools
The project uses raw binary files for images to optimize loading speed on the badge. To convert images, compile the `img2bin` tool on your host machine:

```bash
gcc img2bin.c -o img2bin -lm
```

**Usage:**
```bash
./img2bin <input_image.(jpg|png)> <output_file.bin>
```
The output `.bin` files should be placed in the `Menu_Items` or `assets` directories as required by your apps.

### 2. Deploy to Device
Deploy the project files to the target device. Replace `192.168.1.xxx` with your device's IP address.

**Directory Structure:**
The launcher expects to run from `~/badge_launcher`.

```bash
# Create directory
ssh root@192.168.1.xxx "mkdir -p ~/badge_launcher"

# Copy files (recursive for directories applications/, drivers/, assets/, etc.)
scp -r * root@192.168.1.xxx:~/badge_launcher/
```

### 3. Permissions
Ensure the launcher script and micropython binary are executable:

```bash
ssh root@192.168.1.xxx "chmod +x ~/badge_launcher/run.sh ~/badge_launcher/micropython"
```

*(Note: You must provide your own LVGL-enabled MicroPython binary named `micropython` in the root of the project directory)*

## Running the Launcher

### Manual Start
To run the launcher manually (useful for debugging):

```bash
ssh root@192.168.1.xxx
cd ~/badge_launcher
./run.sh
```

### Autolaunch Configuration (systemd)
To configure the launcher to start automatically on boot:

1. **Deploy the Service File**:
   Copy the provided `badge-launcher.service` to the systemd directory:
   ```bash
   scp badge-launcher.service root@192.168.1.xxx:/etc/systemd/system/
   ```

2. **Enable and Start the Service**:
   Run the following commands on the device:
   ```bash
   # Reload systemd to recognize the new service
   systemctl daemon-reload
   
   # Enable the service to start on boot
   systemctl enable badge-launcher.service
   
   # Start the service immediately
   systemctl start badge-launcher.service
   ```

3. **Check Status**:
   ```bash
   systemctl status badge-launcher.service
   ```

## Troubleshooting

- **Input Not Working**: The launcher reads directly from `/dev/input/event*`. Ensure the user running the script (usually `root`) has permissions to read these devices.
- **MicroPython Error**: If you see "ImportError", ensure `micropython` was built with LVGL bindings and all python drivers are in the `drivers/` folder.
- **Images Not Loading**: Ensure assets were converted using `img2bin` and are in the correct path.
