#!/usr/bin/env python3
"""
Multi-Bitaxe Gamma 601 Time-Based Scheduler
Automatically adjusts voltage and frequency based on time of day for multiple units
"""

import requests
import time
import json
import signal
import sys
from datetime import datetime, time as dtime
import argparse
import logging
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ANSI Color Codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

# Default Configuration
DEFAULT_CONFIG = {
    "miners": [
        {
            "name": "Bitaxe-1",
            "ip": "http://192.168.1.100",
            "enabled": True,
            # Optional: Override global settings for specific miners
            "day_settings": None,  # Use global if None
            "night_settings": None  # Use global if None
        },
        {
            "name": "Bitaxe-2", 
            "ip": "http://192.168.1.101",
            "enabled": True
        }
    ],
    
    # Global settings applied to all miners (unless overridden)
    "global_day_settings": {
        "start_time": "07:30",
        "end_time": "20:00",
        "voltage": 1150,  # mV - Lower voltage for reduced power
        "frequency": 450   # MHz - Lower frequency for reduced noise/heat
    },
    
    "global_night_settings": {
        "start_time": "20:00",
        "end_time": "07:30",
        "voltage": 1250,  # mV - Higher voltage for better performance
        "frequency": 550   # MHz - Higher frequency for maximum hashrate
    },
    
    # Safety limits
    "max_voltage": 1300,  # mV - Maximum safe voltage
    "max_frequency": 600,  # MHz - Maximum safe frequency
    "max_temp": 70,       # °C - Maximum temperature before safety throttle
    "max_power": 15,      # W - Maximum power consumption
    
    # Monitoring settings
    "check_interval": 60,  # seconds - How often to check time and adjust
    "temp_check_interval": 30,  # seconds - How often to monitor temperature
    "log_stats_interval": 300,  # seconds - How often to log statistics
    
    # Transition settings
    "smooth_transition": True,  # Gradually transition between settings
    "transition_steps": 5,      # Number of steps for smooth transition
    "transition_delay": 10,     # seconds between transition steps
    
    # Multi-miner settings
    "parallel_operations": True,  # Apply changes to all miners simultaneously
    "max_workers": 5,            # Maximum number of parallel threads
    "retry_attempts": 3,         # Number of retry attempts for failed operations
    "retry_delay": 5            # seconds between retry attempts
}

class MinerStatus:
    """Track individual miner status"""
    def __init__(self, name: str, ip: str, enabled: bool = True):
        self.name = name
        self.ip = ip
        self.enabled = enabled
        self.online = False
        self.current_period = None
        self.last_settings = {"voltage": None, "frequency": None}
        self.last_update = None
        self.error_count = 0
        self.stats = {
            "day_hashrate_sum": 0,
            "day_power_sum": 0,
            "day_samples": 0,
            "night_hashrate_sum": 0,
            "night_power_sum": 0,
            "night_samples": 0
        }

class MultiBitaxeScheduler:
    def __init__(self, config: Dict):
        self.config = config
        self.miners = {}
        self.running = True
        self.lock = threading.Lock()
        
        # Initialize miners
        for miner_config in config["miners"]:
            if miner_config["enabled"]:
                miner = MinerStatus(
                    miner_config["name"],
                    miner_config["ip"],
                    miner_config["enabled"]
                )
                self.miners[miner_config["name"]] = miner
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('multi_bitaxe_scheduler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Thread pool for parallel operations
        self.executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 5))
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n{YELLOW}Shutdown signal received. Saving state and exiting...{RESET}")
        self.running = False
        self.executor.shutdown(wait=True)
        self.save_all_stats()
        sys.exit(0)
    
    def get_miner_settings(self, miner_name: str, period: str) -> Dict:
        """Get settings for a specific miner and period"""
        # Check for miner-specific override
        for miner_config in self.config["miners"]:
            if miner_config["name"] == miner_name:
                if period == "day" and miner_config.get("day_settings"):
                    return miner_config["day_settings"]
                elif period == "night" and miner_config.get("night_settings"):
                    return miner_config["night_settings"]
        
        # Use global settings
        if period == "day":
            return self.config["global_day_settings"]
        else:
            return self.config["global_night_settings"]
    
    def get_system_info(self, miner: MinerStatus) -> Optional[Dict]:
        """Fetch current system information from a specific Bitaxe"""
        try:
            response = requests.get(f"{miner.ip}/api/system/info", timeout=10)
            response.raise_for_status()
            miner.online = True
            miner.error_count = 0
            return response.json()
        except requests.exceptions.RequestException as e:
            miner.online = False
            miner.error_count += 1
            self.logger.error(f"[{miner.name}] Error fetching system info: {e}")
            return None
    
    def set_system_settings(self, miner: MinerStatus, voltage: int, frequency: int) -> bool:
        """Apply voltage and frequency settings to a specific Bitaxe"""
        for attempt in range(self.config.get("retry_attempts", 3)):
            try:
                # Set voltage
                voltage_data = {"coreVoltage": voltage}
                response = requests.patch(
                    f"{miner.ip}/api/system",
                    json=voltage_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                response.raise_for_status()
                
                # Set frequency
                freq_data = {"frequency": frequency}
                response = requests.patch(
                    f"{miner.ip}/api/system",
                    json=freq_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                response.raise_for_status()
                
                self.logger.info(f"[{miner.name}] Settings applied: {voltage}mV @ {frequency}MHz")
                miner.last_settings = {"voltage": voltage, "frequency": frequency}
                miner.last_update = datetime.now()
                return True
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[{miner.name}] Attempt {attempt+1} failed: {e}")
                if attempt < self.config.get("retry_attempts", 3) - 1:
                    time.sleep(self.config.get("retry_delay", 5))
                else:
                    return False
        return False
    
    def restart_system(self, miner: MinerStatus):
        """Restart a specific Bitaxe system"""
        try:
            response = requests.post(f"{miner.ip}/api/system/restart", timeout=10)
            response.raise_for_status()
            self.logger.info(f"[{miner.name}] System restart initiated")
            time.sleep(30)  # Wait for system to restart
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[{miner.name}] Error restarting system: {e}")
    
    def smooth_transition(self, miner: MinerStatus, target_voltage: int, target_frequency: int) -> bool:
        """Gradually transition a miner to new settings"""
        if not self.config["smooth_transition"]:
            return self.set_system_settings(miner, target_voltage, target_frequency)
        
        current_info = self.get_system_info(miner)
        if not current_info:
            return self.set_system_settings(miner, target_voltage, target_frequency)
        
        current_voltage = current_info.get("coreVoltage", target_voltage)
        current_frequency = current_info.get("frequency", target_frequency)
        
        steps = self.config["transition_steps"]
        voltage_step = (target_voltage - current_voltage) / steps
        freq_step = (target_frequency - current_frequency) / steps
        
        self.logger.info(f"[{miner.name}] Starting smooth transition over {steps} steps...")
        
        for i in range(1, steps + 1):
            intermediate_voltage = int(current_voltage + (voltage_step * i))
            intermediate_freq = int(current_frequency + (freq_step * i))
            
            if not self.set_system_settings(miner, intermediate_voltage, intermediate_freq):
                return False
            
            if i < steps:
                time.sleep(self.config["transition_delay"])
        
        self.logger.info(f"[{miner.name}] Transition complete!")
        return True
    
    def is_in_time_range(self, start_str: str, end_str: str) -> bool:
        """Check if current time is within specified range"""
        current_time = datetime.now().time()
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        
        # Handle ranges that cross midnight
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    
    def get_current_period(self) -> str:
        """Determine if we're in day or night period"""
        day_config = self.config["global_day_settings"]
        
        if self.is_in_time_range(day_config["start_time"], day_config["end_time"]):
            return "day"
        else:
            return "night"
    
    def check_safety_limits(self, miner: MinerStatus, system_info: Dict) -> bool:
        """Check if a miner is within safety limits"""
        temp = system_info.get("temp", 0)
        power = system_info.get("power", 0)
        
        if temp > self.config["max_temp"]:
            self.logger.warning(f"[{miner.name}] Temperature too high: {temp}°C > {self.config['max_temp']}°C")
            return False
        
        if power > self.config["max_power"]:
            self.logger.warning(f"[{miner.name}] Power too high: {power}W > {self.config['max_power']}W")
            return False
        
        return True
    
    def apply_period_settings_to_miner(self, miner: MinerStatus, period: str) -> bool:
        """Apply settings for the specified period to a single miner"""
        settings = self.get_miner_settings(miner.name, period)
        
        target_voltage = settings["voltage"]
        target_frequency = settings["frequency"]
        
        # Validate against safety limits
        target_voltage = min(target_voltage, self.config["max_voltage"])
        target_frequency = min(target_frequency, self.config["max_frequency"])
        
        # Check if settings need to change
        if (miner.last_settings["voltage"] == target_voltage and 
            miner.last_settings["frequency"] == target_frequency):
            return True
        
        self.logger.info(f"[{miner.name}] Switching to {period.upper()} mode: {target_voltage}mV @ {target_frequency}MHz")
        
        # Apply settings with smooth transition if enabled
        success = self.smooth_transition(miner, target_voltage, target_frequency)
        if success:
            miner.current_period = period
        return success
    
    def apply_period_settings_all(self, period: str):
        """Apply settings to all miners"""
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{YELLOW}Switching all miners to {period.upper()} mode{RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")
        
        if self.config.get("parallel_operations", True):
            # Apply settings to all miners in parallel
            futures = []
            for miner in self.miners.values():
                if miner.enabled and miner.online:
                    future = self.executor.submit(
                        self.apply_period_settings_to_miner, miner, period
                    )
                    futures.append((future, miner))
            
            # Wait for all operations to complete
            for future, miner in futures:
                try:
                    success = future.result(timeout=60)
                    if success:
                        print(f"{GREEN}[{miner.name}] Successfully switched to {period} mode{RESET}")
                    else:
                        print(f"{RED}[{miner.name}] Failed to switch to {period} mode{RESET}")
                except Exception as e:
                    print(f"{RED}[{miner.name}] Error during switch: {e}{RESET}")
        else:
            # Apply settings sequentially
            for miner in self.miners.values():
                if miner.enabled and miner.online:
                    success = self.apply_period_settings_to_miner(miner, period)
                    if success:
                        print(f"{GREEN}[{miner.name}] Successfully switched to {period} mode{RESET}")
                    else:
                        print(f"{RED}[{miner.name}] Failed to switch to {period} mode{RESET}")
    
    def collect_stats(self, miner: MinerStatus, system_info: Dict, period: str):
        """Collect performance statistics for a miner"""
        hashrate = system_info.get("hashRate", 0)
        power = system_info.get("power", 0)
        
        with self.lock:
            if period == "day":
                miner.stats["day_hashrate_sum"] += hashrate
                miner.stats["day_power_sum"] += power
                miner.stats["day_samples"] += 1
            else:
                miner.stats["night_hashrate_sum"] += hashrate
                miner.stats["night_power_sum"] += power
                miner.stats["night_samples"] += 1
    
    def update_miner_status(self, miner: MinerStatus) -> Optional[Dict]:
        """Update status for a single miner"""
        system_info = self.get_system_info(miner)
        if system_info:
            # Check safety limits
            if not self.check_safety_limits(miner, system_info):
                self.logger.warning(f"[{miner.name}] Safety limits exceeded, applying day settings")
                self.apply_period_settings_to_miner(miner, "day")
            
            # Collect statistics
            current_period = self.get_current_period()
            self.collect_stats(miner, system_info, current_period)
            
            return system_info
        return None
    
    def update_all_miners(self):
        """Update status for all miners in parallel"""
        futures = []
        for miner in self.miners.values():
            if miner.enabled:
                future = self.executor.submit(self.update_miner_status, miner)
                futures.append((future, miner))
        
        results = {}
        for future, miner in futures:
            try:
                system_info = future.result(timeout=30)
                if system_info:
                    results[miner.name] = system_info
            except Exception as e:
                self.logger.error(f"[{miner.name}] Error updating status: {e}")
        
        return results
    
    def print_status_table(self, miner_info: Dict):
        """Print status table for all miners"""
        print(f"\n{CYAN}{'='*100}{RESET}")
        print(f"{CYAN}Miner Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
        print(f"{CYAN}{'='*100}{RESET}")
        
        # Header
        print(f"{'Name':<15} {'Status':<10} {'Hashrate':<12} {'Temp':<8} {'Power':<10} "
              f"{'Efficiency':<12} {'Settings':<20}")
        print("-" * 100)
        
        total_hashrate = 0
        total_power = 0
        online_count = 0
        
        for miner in self.miners.values():
            if miner.name in miner_info:
                info = miner_info[miner.name]
                hashrate = info.get("hashRate", 0)
                temp = info.get("temp", 0)
                power = info.get("power", 0)
                voltage = info.get("coreVoltage", 0)
                frequency = info.get("frequency", 0)
                efficiency = power / (hashrate / 1000) if hashrate > 0 else 0
                
                status_color = GREEN if miner.online else RED
                temp_color = RED if temp > self.config["max_temp"] - 5 else YELLOW if temp > self.config["max_temp"] - 10 else GREEN
                
                print(f"{miner.name:<15} "
                      f"{status_color}{'Online':<10}{RESET} "
                      f"{hashrate:>8.1f} GH/s "
                      f"{temp_color}{temp:>6.1f}°C{RESET} "
                      f"{power:>8.2f}W "
                      f"{efficiency:>10.2f} J/TH "
                      f"{voltage:>4}mV @ {frequency:>3}MHz")
                
                total_hashrate += hashrate
                total_power += power
                online_count += 1
            else:
                print(f"{miner.name:<15} "
                      f"{RED}{'Offline':<10}{RESET} "
                      f"{'--':>11} "
                      f"{'--':>8} "
                      f"{'--':>10} "
                      f"{'--':>12} "
                      f"{'--':>20}")
        
        # Summary
        print("-" * 100)
        total_efficiency = total_power / (total_hashrate / 1000) if total_hashrate > 0 else 0
        print(f"{MAGENTA}TOTAL:{RESET} {online_count}/{len(self.miners)} online | "
              f"{total_hashrate:.1f} GH/s | {total_power:.2f}W | {total_efficiency:.2f} J/TH")
        print(f"{CYAN}{'='*100}{RESET}")
    
    def save_all_stats(self):
        """Save statistics for all miners"""
        stats_file = "multi_bitaxe_stats.json"
        
        all_stats = {
            "timestamp": datetime.now().isoformat(),
            "miners": {}
        }
        
        for miner in self.miners.values():
            # Calculate averages
            if miner.stats["day_samples"] > 0:
                day_avg_hashrate = miner.stats["day_hashrate_sum"] / miner.stats["day_samples"]
                day_avg_power = miner.stats["day_power_sum"] / miner.stats["day_samples"]
            else:
                day_avg_hashrate = 0
                day_avg_power = 0
            
            if miner.stats["night_samples"] > 0:
                night_avg_hashrate = miner.stats["night_hashrate_sum"] / miner.stats["night_samples"]
                night_avg_power = miner.stats["night_power_sum"] / miner.stats["night_samples"]
            else:
                night_avg_hashrate = 0
                night_avg_power = 0
            
            all_stats["miners"][miner.name] = {
                "ip": miner.ip,
                "online": miner.online,
                "last_update": miner.last_update.isoformat() if miner.last_update else None,
                "day_performance": {
                    "avg_hashrate": day_avg_hashrate,
                    "avg_power": day_avg_power,
                    "samples": miner.stats["day_samples"]
                },
                "night_performance": {
                    "avg_hashrate": night_avg_hashrate,
                    "avg_power": night_avg_power,
                    "samples": miner.stats["night_samples"]
                }
            }
        
        with open(stats_file, 'w') as f:
            json.dump(all_stats, f, indent=2)
        
        self.logger.info(f"Statistics saved to {stats_file}")
    
    def run(self):
        """Main scheduler loop"""
        print(f"{GREEN}Multi-Bitaxe Scheduler Started{RESET}")
        print(f"Managing {len(self.miners)} miners")
        print(f"Day period: {self.config['global_day_settings']['start_time']} - {self.config['global_day_settings']['end_time']}")
        print(f"Night period: {self.config['global_night_settings']['start_time']} - {self.config['global_night_settings']['end_time']}")
        
        # Initial miner discovery
        print(f"\n{CYAN}Discovering miners...{RESET}")
        self.update_all_miners()
        
        online_miners = [m for m in self.miners.values() if m.online]
        print(f"{GREEN}Found {len(online_miners)}/{len(self.miners)} miners online{RESET}")
        
        last_stats_time = time.time()
        last_status_print = time.time()
        last_period = None
        
        while self.running:
            try:
                # Check current period
                current_period = self.get_current_period()
                
                # Apply settings if period changed
                if current_period != last_period:
                    self.apply_period_settings_all(current_period)
                    last_period = current_period
                
                # Update all miners
                miner_info = self.update_all_miners()
                
                # Print status periodically
                if time.time() - last_status_print >= 60:
                    self.print_status_table(miner_info)
                    last_status_print = time.time()
                
                # Save statistics periodically
                if time.time() - last_stats_time >= self.config["log_stats_interval"]:
                    self.save_all_stats()
                    last_stats_time = time.time()
                
                # Sleep before next check
                time.sleep(self.config["check_interval"])
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(30)  # Wait before retrying

def load_config(config_file: str) -> Dict:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{YELLOW}Config file not found, creating default config...{RESET}")
        with open(config_file, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"{GREEN}Default config saved to {config_file}{RESET}")
        print(f"{YELLOW}Please edit the config file with your miners and settings, then restart.{RESET}")
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(f"{RED}Error parsing config file: {e}{RESET}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Multi-Bitaxe Time-Based Scheduler')
    parser.add_argument('--config', default='multi_scheduler_config.json',
                       help='Path to configuration file (default: multi_scheduler_config.json)')
    parser.add_argument('--add-miner', nargs=2, metavar=('NAME', 'IP'),
                       help='Add a new miner (name and IP address)')
    parser.add_argument('--list-miners', action='store_true',
                       help='List all configured miners')
    parser.add_argument('--disable-miner', metavar='NAME',
                       help='Disable a specific miner')
    parser.add_argument('--enable-miner', metavar='NAME',
                       help='Enable a specific miner')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Handle miner management commands
    if args.add_miner:
        name, ip = args.add_miner
        if not ip.startswith("http"):
            ip = f"http://{ip}"
        
        # Check if miner already exists
        for miner in config["miners"]:
            if miner["name"] == name:
                print(f"{YELLOW}Miner {name} already exists{RESET}")
                sys.exit(1)
        
        # Add new miner
        config["miners"].append({
            "name": name,
            "ip": ip,
            "enabled": True
        })
        
        with open(args.config, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"{GREEN}Added miner {name} at {ip}{RESET}")
        sys.exit(0)
    
    if args.list_miners:
        print(f"\n{CYAN}Configured Miners:{RESET}")
        for miner in config["miners"]:
            status = "Enabled" if miner["enabled"] else "Disabled"
            print(f"  {miner['name']}: {miner['ip']} [{status}]")
        sys.exit(0)
    
    if args.disable_miner:
        for miner in config["miners"]:
            if miner["name"] == args.disable_miner:
                miner["enabled"] = False
                with open(args.config, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"{YELLOW}Disabled miner {args.disable_miner}{RESET}")
                sys.exit(0)
        print(f"{RED}Miner {args.disable_miner} not found{RESET}")
        sys.exit(1)
    
    if args.enable_miner:
        for miner in config["miners"]:
            if miner["name"] == args.enable_miner:
                miner["enabled"] = True
                with open(args.config, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"{GREEN}Enabled miner {args.enable_miner}{RESET}")
                sys.exit(0)
        print(f"{RED}Miner {args.enable_miner} not found{RESET}")
        sys.exit(1)
    
    # Create and run scheduler
    scheduler = MultiBitaxeScheduler(config)
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Scheduler stopped by user{RESET}")
    finally:
        scheduler.executor.shutdown(wait=True)
        scheduler.save_all_stats()

if __name__ == "__main__":
    main()