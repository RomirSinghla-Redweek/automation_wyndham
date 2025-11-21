#!/usr/bin/env python3
"""
Quick setup and launcher for Wyndham Scanner with Real-time CSV
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_requirements():
    """Check if required packages are installed"""
    required = {
        'selenium': False,
        'webdriver_manager': False,
        'watchdog': False
    }
    
    for package in required:
        try:
            __import__(package.replace('_', '-'))
            required[package] = True
        except ImportError:
            required[package] = False
    
    return required

def install_requirements():
    """Install missing requirements"""
    print("Installing required packages...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    print("✅ All requirements installed!")

def display_menu():
    """Display main menu"""
    print("\n" + "="*60)
    print("       WYNDHAM SCANNER WITH REAL-TIME CSV")
    print("="*60)
    print("\nSelect operation mode:\n")
    print("1. 🚀 Run Integrated Scanner (All-in-one solution)")
    print("2. 📊 Run File Watcher (For existing scanner)")
    print("3. 📈 Run Monitor Dashboard (View real-time stats)")
    print("4. 🔧 Run Scanner + Monitor (Two windows)")
    print("5. 🛠️  Run Original Scanner + Watcher + Monitor (Three windows)")
    print("6. 📦 Install Requirements")
    print("7. ❌ Exit")
    print("\n" + "-"*60)

def run_integrated_scanner():
    """Run the integrated scanner with real-time CSV"""
    print("\n Starting Integrated Scanner with Real-time CSV...")
    print("-"*60)
    try:
        subprocess.run([sys.executable, 'wyndham_realtime_scanner.py'])
    except KeyboardInterrupt:
        print("\nScanner stopped by user.")

def run_file_watcher():
    """Run the file watcher for CSV generation"""
    print("\n Starting File Watcher for Real-time CSV...")
    print("-"*60)
    print("Options:")
    print("1. Watch default directory (screens/NewFolder)")
    print("2. Watch custom directory")
    
    choice = input("\nSelect option [1]: ").strip() or "1"
    
    cmd = [sys.executable, 'wyndham_csv_watcher.py']
    
    if choice == "2":
        watch_dir = input("Enter directory path to watch: ").strip()
        cmd.extend(['--watch-dir', watch_dir])
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nWatcher stopped by user.")

def run_monitor():
    """Run the monitoring dashboard"""
    print("\n Starting Monitoring Dashboard...")
    print("-"*60)
    
    # Check for CSV file
    default_csv = 'wyndham_availability_realtime.csv'
    alt_csv = Path('screens/NewFolder') / default_csv
    
    if alt_csv.exists():
        csv_file = str(alt_csv)
    else:
        csv_file = default_csv
    
    try:
        subprocess.run([sys.executable, 'wyndham_monitor.py', csv_file])
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")

def run_scanner_with_monitor():
    """Run scanner and monitor in separate processes"""
    print("\n Starting Scanner + Monitor Mode...")
    print("-"*60)
    
    # Windows-specific
    if os.name == 'nt':
        # Start scanner in new window
        subprocess.Popen(['start', 'cmd', '/k', 'python', 'wyndham_realtime_scanner.py'], shell=True)
        
        # Wait a moment
        time.sleep(2)
        
        # Start monitor in new window
        subprocess.Popen(['start', 'cmd', '/k', 'python', 'wyndham_monitor.py'], shell=True)
        
        print("✅ Scanner and Monitor started in separate windows!")
        print("   Close this window when done.")
        
    # Unix-like systems
    else:
        print("Opening new terminals...")
        
        # Try different terminal emulators
        terminals = [
            ['gnome-terminal', '--', 'python3', 'wyndham_realtime_scanner.py'],
            ['xterm', '-e', 'python3', 'wyndham_realtime_scanner.py'],
            ['konsole', '-e', 'python3', 'wyndham_realtime_scanner.py'],
        ]
        
        scanner_started = False
        for term_cmd in terminals:
            try:
                subprocess.Popen(term_cmd)
                scanner_started = True
                break
            except:
                continue
        
        if scanner_started:
            time.sleep(2)
            
            # Start monitor
            for term_cmd in terminals:
                term_cmd[-1] = 'wyndham_monitor.py'
                try:
                    subprocess.Popen(term_cmd)
                    break
                except:
                    continue
            
            print("✅ Scanner and Monitor started!")
        else:
            print("❌ Could not open new terminal windows.")
            print("   Please run the scripts manually in separate terminals:")
            print("   Terminal 1: python3 wyndham_realtime_scanner.py")
            print("   Terminal 2: python3 wyndham_monitor.py")

def run_triple_mode():
    """Run original scanner + watcher + monitor"""
    print("\n Starting Triple Mode (Scanner + Watcher + Monitor)...")
    print("-"*60)
    
    if os.name == 'nt':
        # Start original scanner
        subprocess.Popen(['start', 'cmd', '/k', 'python', 'wyndham_scan_with_network.py'], shell=True)
        
        time.sleep(2)
        
        # Start watcher
        subprocess.Popen(['start', 'cmd', '/k', 'python', 'wyndham_csv_watcher.py'], shell=True)
        
        time.sleep(1)
        
        # Start monitor
        subprocess.Popen(['start', 'cmd', '/k', 'python', 'wyndham_monitor.py'], shell=True)
        
        print("✅ All three components started in separate windows!")
    else:
        print("Please run these commands in separate terminals:")
        print("Terminal 1: python3 wyndham_scan_with_network.py")
        print("Terminal 2: python3 wyndham_csv_watcher.py")
        print("Terminal 3: python3 wyndham_monitor.py")

def main():
    """Main entry point"""
    print("\nWyndham Scanner Setup & Launcher")
    print("Checking requirements...")
    
    # Check requirements
    status = check_requirements()
    
    print("\nPackage Status:")
    for package, installed in status.items():
        icon = "✅" if installed else "❌"
        print(f"  {icon} {package}")
    
    # Check if all required for basic operation
    if not (status['selenium'] and status['webdriver_manager']):
        print("\n⚠️  Missing required packages!")
        response = input("Install now? [Y/n]: ").strip().lower()
        if response != 'n':
            install_requirements()
            print("\nRequirements installed! Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    
    # Main loop
    while True:
        display_menu()
        
        choice = input("\nSelect option [1-7]: ").strip()
        
        if choice == '1':
            run_integrated_scanner()
        elif choice == '2':
            if not status['watchdog']:
                print("\n⚠️  Watchdog not installed!")
                response = input("Install now? [Y/n]: ").strip().lower()
                if response != 'n':
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'watchdog'])
                    status['watchdog'] = True
                else:
                    continue
            run_file_watcher()
        elif choice == '3':
            run_monitor()
        elif choice == '4':
            run_scanner_with_monitor()
        elif choice == '5':
            if not status['watchdog']:
                print("\n⚠️  Watchdog not installed!")
                response = input("Install now? [Y/n]: ").strip().lower()
                if response != 'n':
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'watchdog'])
                    status['watchdog'] = True
                else:
                    continue
            run_triple_mode()
        elif choice == '6':
            install_requirements()
            # Update status
            status = check_requirements()
        elif choice == '7':
            print("\nGoodbye!")
            break
        else:
            print("\n❌ Invalid option. Please select 1-7.")
        
        if choice in ['1', '2', '3']:
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        input("Press Enter to exit...")
