# Multi-Bitaxe Gamma 601 Time-Based Scheduler

A comprehensive Python-based scheduling system for automatically managing multiple Bitaxe Gamma 601 Bitcoin miners based on time of day. Optimize power consumption during peak hours and maximize performance during off-peak times.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Command Line Options](#command-line-options)
- [Running as a Service](#running-as-a-service)
- [Monitoring and Logs](#monitoring-and-logs)
- [Troubleshooting](#troubleshooting)
- [Performance Optimization](#performance-optimization)
- [Safety Considerations](#safety-considerations)

## Features

### Core Functionality
- **Time-Based Scheduling**: Automatically switch between day and night settings
- **Multi-Miner Support**: Manage unlimited Bitaxe units from a single scheduler
- **Parallel Operations**: Apply settings to all miners simultaneously
- **Smooth Transitions**: Gradual voltage/frequency changes to prevent instability
- **Individual Overrides**: Custom settings per miner for different requirements
- **Safety Limits**: Temperature, power, and voltage protection
- **Performance Tracking**: Detailed statistics for day/night periods
- **Automatic Recovery**: Retry failed operations and recover from errors
- **Real-time Monitoring**: Live status table showing all miners

### Safety Features
- Maximum temperature monitoring with automatic throttling
- Power consumption limits
- Voltage/frequency validation
- Graceful shutdown on errors
- Automatic fallback to safe settings

## Requirements

### Hardware
- One or more Bitaxe Gamma 601 miners
- Network connectivity to all miners
- Computer/Raspberry Pi to run the scheduler

### Software
- Python 3.7 or higher
- pip (Python package manager)
- Network access to Bitaxe API endpoints

### Python Dependencies
- `requests` library for API communication

## Installation

### Step 1: Create Project Directory
```bash
# Create and navigate to project directory
mkdir ~/multi-bitaxe-scheduler
cd ~/multi-bitaxe-scheduler
```

### Step 2: Set Up Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
# Install required Python packages
pip install requests

# Create requirements.txt for future reference
pip freeze > requirements.txt
```

### Step 4: Download the Scheduler Script
Save the Python script as `bitaxe_scheduler.py` in your project directory.

### Step 5: Generate Default Configuration
```bash
# Run once to create default config file
python bitaxe_scheduler.py

# This creates multi_scheduler_config.json
```

## Configuration

### Basic Configuration File Structure

Edit `multi_scheduler_config.json`:

```json
{
  "miners": [
    {
      "name": "Bitaxe-1",
      "ip": "http://192.168.1.100",
      "enabled": true,
      "day_settings": null,    // Uses global settings if null
      "night_settings": null   // Uses global settings if null
    },
    {
      "name": "Bitaxe-2",
      "ip": "http://192.168.1.101",
      "enabled": true
    },
    {
      "name": "Bitaxe-3",
      "ip": "http://192.168.1.102",
      "enabled": true,
      // Custom settings for this specific miner
      "day_settings": {
        "voltage": 1100,
        "frequency": 425
      },
      "night_settings": {
        "voltage": 1200,
        "frequency": 525
      }
    }
  ],
  
  "global_day_settings": {
    "start_time": "07:30",     // 24-hour format
    "end_time": "20:00",
    "voltage": 1150,           // millivolts
    "frequency": 450           // MHz
  },
  
  "global_night_settings": {
    "start_time": "20:00",
    "end_time": "07:30",
    "voltage": 1250,
    "frequency": 550
  },
  
  "max_voltage": 1300,         // Safety limit (mV)
  "max_frequency": 600,        // Safety limit (MHz)
  "max_temp": 70,             // °C - triggers safety throttle
  "max_power": 15,            // Watts - maximum power draw
  
  "check_interval": 60,        // Seconds between status checks
  "temp_check_interval": 30,   // Seconds between temperature checks
  "log_stats_interval": 300,   // Seconds between statistics saves
  
  "smooth_transition": true,   // Enable gradual transitions
  "transition_steps": 5,       // Number of steps in transition
  "transition_delay": 10,      // Seconds between transition steps
  
  "parallel_operations": true, // Apply changes simultaneously
  "max_workers": 5,           // Maximum parallel threads
  "retry_attempts": 3,        // Retry count for failed operations
  "retry_delay": 5            // Seconds between retries
}
```

### Recommended Settings by Use Case

#### Quiet Home Mining (Residential)
```json
"global_day_settings": {
  "voltage": 1100,
  "frequency": 400
},
"global_night_settings": {
  "voltage": 1200,
  "frequency": 500
}
```

#### Maximum Efficiency (Cool Environment)
```json
"global_day_settings": {
  "voltage": 1150,
  "frequency": 450
},
"global_night_settings": {
  "voltage": 1250,
  "frequency": 575
}
```

#### Maximum Performance (Good Cooling)
```json
"global_day_settings": {
  "voltage": 1200,
  "frequency": 500
},
"global_night_settings": {
  "voltage": 1300,
  "frequency": 600
}
```

## Usage

### Basic Operation

1. **Start the scheduler**:
```bash
cd ~/multi-bitaxe-scheduler
source venv/bin/activate
python bitaxe_scheduler.py
```

2. **Run with custom config**:
```bash
python bitaxe_scheduler.py --config my_config.json
```

### Managing Miners

#### Add a New Miner
```bash
python bitaxe_scheduler.py --add-miner Bitaxe-4 192.168.1.103
```

#### List All Miners
```bash
python bitaxe_scheduler.py --list-miners

# Output:
# Configured Miners:
#   Bitaxe-1: http://192.168.1.100 [Enabled]
#   Bitaxe-2: http://192.168.1.101 [Enabled]
#   Bitaxe-3: http://192.168.1.102 [Disabled]
```

#### Enable/Disable Miners
```bash
# Disable a miner (keeps config but stops managing it)
python bitaxe_scheduler.py --disable-miner Bitaxe-2

# Re-enable a miner
python bitaxe_scheduler.py --enable-miner Bitaxe-2
```

## Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--config FILE` | Specify config file | `--config production.json` |
| `--add-miner NAME IP` | Add new miner | `--add-miner Bitaxe-5 192.168.1.105` |
| `--list-miners` | List all configured miners | `--list-miners` |
| `--disable-miner NAME` | Disable specific miner | `--disable-miner Bitaxe-2` |
| `--enable-miner NAME` | Enable specific miner | `--enable-miner Bitaxe-2` |

## Running as a Service

### Linux (systemd)

1. **Create service file**:
```bash
sudo nano /etc/systemd/system/multi-bitaxe-scheduler.service
```

2. **Add service configuration**:
```ini
[Unit]
Description=Multi-Bitaxe Scheduler
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/multi-bitaxe-scheduler
ExecStart=/home/pi/multi-bitaxe-scheduler/venv/bin/python /home/pi/multi-bitaxe-scheduler/bitaxe_scheduler.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/multi-bitaxe-scheduler/service.log
StandardError=append:/home/pi/multi-bitaxe-scheduler/service-error.log

[Install]
WantedBy=multi-user.target
```

3. **Enable and start service**:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable multi-bitaxe-scheduler

# Start service
sudo systemctl start multi-bitaxe-scheduler

# Check status
sudo systemctl status multi-bitaxe-scheduler

# View logs
sudo journalctl -u multi-bitaxe-scheduler -f
```

### Raspberry Pi (Additional Steps)

1. **Ensure Python 3 and pip are installed**:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

2. **Set up auto-start on boot** (alternative to systemd):
```bash
# Edit crontab
crontab -e

# Add line:
@reboot sleep 30 && cd /home/pi/multi-bitaxe-scheduler && /home/pi/multi-bitaxe-scheduler/venv/bin/python bitaxe_scheduler.py >> /home/pi/multi-bitaxe-scheduler/cron.log 2>&1
```

### Windows (Task Scheduler)

1. Create batch file `start_scheduler.bat`:
```batch
@echo off
cd C:\Users\YourUser\multi-bitaxe-scheduler
venv\Scripts\activate && python bitaxe_scheduler.py
```

2. Set up Task Scheduler:
   - Open Task Scheduler
   - Create Basic Task
   - Trigger: "When the computer starts"
   - Action: Start the batch file
   - Check "Run with highest privileges"

## Monitoring and Logs

### Log Files

The scheduler creates several log files:

| File | Description |
|------|-------------|
| `multi_bitaxe_scheduler.log` | Main application log |
| `multi_bitaxe_stats.json` | Performance statistics |
| `service.log` | Systemd service output (if using service) |

### Real-time Monitoring

1. **Watch logs live**:
```bash
tail -f multi_bitaxe_scheduler.log
```

2. **Monitor specific miner**:
```bash
grep "\[Bitaxe-1\]" multi_bitaxe_scheduler.log | tail -20
```

3. **View aggregate performance**:
```bash
grep "TOTAL:" multi_bitaxe_scheduler.log | tail -10
```

### Status Display

The scheduler shows a real-time status table:
```
====================================================================================================
Miner Status - 2025-01-21 14:30:00
====================================================================================================
Name            Status     Hashrate     Temp     Power      Efficiency    Settings
----------------------------------------------------------------------------------------------------
Bitaxe-1        Online      450.5 GH/s   65.2°C    11.50W      25.53 J/TH   1150mV @ 450MHz
Bitaxe-2        Online      448.3 GH/s   64.8°C    11.30W      25.21 J/TH   1150mV @ 450MHz
Bitaxe-3        Offline     --           --        --          --           --
----------------------------------------------------------------------------------------------------
TOTAL: 2/3 online | 898.8 GH/s | 22.80W | 25.37 J/TH
====================================================================================================
```

### Performance Statistics

View saved statistics:
```bash
cat multi_bitaxe_stats.json | python -m json.tool
```

Example output:
```json
{
  "timestamp": "2025-01-21T14:30:00",
  "miners": {
    "Bitaxe-1": {
      "ip": "http://192.168.1.100",
      "online": true,
      "day_performance": {
        "avg_hashrate": 450.5,
        "avg_power": 11.5,
        "samples": 480
      },
      "night_performance": {
        "avg_hashrate": 550.2,
        "avg_power": 14.8,
        "samples": 720
      }
    }
  }
}
```

## Troubleshooting

### Common Issues and Solutions

#### Miner Not Responding
```bash
# Check network connectivity
ping 192.168.1.100

# Test API endpoint
curl http://192.168.1.100/api/system/info

# Check firewall rules
sudo ufw status
```

#### Permission Denied Errors
```bash
# Ensure proper ownership
sudo chown -R $USER:$USER ~/multi-bitaxe-scheduler

# Make script executable
chmod +x bitaxe_scheduler.py
```

#### Service Won't Start
```bash
# Check service status
sudo systemctl status multi-bitaxe-scheduler

# View detailed logs
sudo journalctl -u multi-bitaxe-scheduler -n 50

# Test script directly
cd ~/multi-bitaxe-scheduler
source venv/bin/activate
python bitaxe_scheduler.py
```

#### High Temperature Warnings
- Reduce voltage and frequency settings
- Improve cooling (fans, ventilation)
- Increase `max_temp` limit (with caution)
- Enable smooth transitions to prevent spikes

### Debug Mode

Add verbose logging by modifying the script:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    ...
)
```

## Performance Optimization

### Finding Optimal Settings

1. **Use existing benchmark tools** first to find your miners' sweet spots
2. **Start conservative** with lower voltages/frequencies
3. **Monitor temperatures** closely during the first 24 hours
4. **Adjust gradually** based on performance data

### Efficiency Guidelines

| Goal | Voltage (mV) | Frequency (MHz) | Expected Efficiency |
|------|--------------|-----------------|-------------------|
| Maximum Efficiency | 1100-1150 | 400-450 | 22-24 J/TH |
| Balanced | 1150-1200 | 450-500 | 24-26 J/TH |
| Maximum Performance | 1200-1300 | 500-600 | 26-30 J/TH |

### Tips for Multiple Miners

1. **Group by location**: Miners in hot areas need lower settings
2. **Stagger transitions**: Prevent power spikes by adding delays
3. **Monitor total power**: Ensure circuit capacity isn't exceeded
4. **Use individual overrides**: Customize for each miner's capabilities

## Safety Considerations

### Important Warnings

⚠️ **Voltage Limits**: Never exceed 1300mV on Bitaxe Gamma 601
⚠️ **Temperature**: Sustained temperatures above 70°C can damage hardware
⚠️ **Power Supply**: Ensure adequate power supply capacity (15W per unit)
⚠️ **Ventilation**: Proper airflow is critical for stable operation

### Best Practices

1. **Start Low**: Begin with conservative settings and increase gradually
2. **Monitor Closely**: Watch temperatures during the first week
3. **Regular Maintenance**: Clean fans and heatsinks monthly
4. **Backup Config**: Keep copies of working configurations
5. **Test Changes**: Make setting changes during supervised periods

## Helper Scripts

### Quick Status Check
Create `check_status.sh`:
```bash
#!/bin/bash
cd ~/multi-bitaxe-scheduler
source venv/bin/activate
python -c "
import json
with open('multi_bitaxe_stats.json', 'r') as f:
    stats = json.load(f)
    print(f\"Last Update: {stats['timestamp']}\")
    for name, data in stats['miners'].items():
        status = 'Online' if data['online'] else 'Offline'
        print(f\"{name}: {status}\")
"
```

### Add Multiple Miners
Create `add_miners.sh`:
```bash
#!/bin/bash
cd ~/multi-bitaxe-scheduler
source venv/bin/activate

# Add your miners here
python bitaxe_scheduler.py --add-miner Bitaxe-1 192.168.1.100
python bitaxe_scheduler.py --add-miner Bitaxe-2 192.168.1.101
python bitaxe_scheduler.py --add-miner Bitaxe-3 192.168.1.102

python bitaxe_scheduler.py --list-miners
```

### Emergency Stop
Create `emergency_stop.sh`:
```bash
#!/bin/bash
# Stop the scheduler service
sudo systemctl stop multi-bitaxe-scheduler

# Apply safe settings to all miners
cd ~/multi-bitaxe-scheduler
source venv/bin/activate
python -c "
import requests
import json

with open('multi_scheduler_config.json', 'r') as f:
    config = json.load(f)
    
for miner in config['miners']:
    if miner['enabled']:
        try:
            # Apply minimum safe settings
            url = miner['ip']
            requests.patch(f'{url}/api/system', 
                          json={'coreVoltage': 1100, 'frequency': 400})
            print(f\"Safe settings applied to {miner['name']}\")
        except:
            print(f\"Failed to reach {miner['name']}\")
"
```

## Support and Contributing

### Getting Help
- Check the logs first: `tail -n 100 multi_bitaxe_scheduler.log`
- Verify network connectivity to all miners
- Ensure Bitaxe firmware is up to date
- Test with a single miner first if having issues

### Future Enhancements
- Web UI for remote management
- Historical performance graphs
- Automatic optimization based on efficiency targets
- Pool switching based on time/profitability
- Integration with mining pool APIs
- Temperature-based dynamic adjustment
- Email/SMS alerts for offline miners

## License

This tool is provided as-is for the Bitaxe community. Use at your own risk. Always monitor your miners and ensure proper cooling and power delivery.

## Acknowledgments

- Bitaxe community for the open-source hardware
- Based on concepts from various Bitaxe optimization tools