#!/usr/bin/env python3
"""
Alternative implementation: File watcher approach for real-time CSV generation
This can run alongside the scanner or as a separate process
"""

import os
import json
import csv
import time
from pathlib import Path
from datetime import datetime
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse

class AvailabilityCSVGenerator(FileSystemEventHandler):
    """
    File watcher that monitors a directory for new network response files
    and updates CSV in real-time
    """
    
    def __init__(self, watch_dir, output_csv):
        self.watch_dir = Path(watch_dir)
        self.output_csv = Path(output_csv)
        self.processed_files = set()
        self.unique_combinations = {}
        self.fieldnames = ['date', 'offeringId', 'inventoryOfferingHashKey', 'invenOffrngLabel', 'availableCount']
        self.lock = threading.Lock()
        
        # Initialize CSV
        self._initialize_csv()
        
        # Process any existing files
        self._process_existing_files()
    
    def _initialize_csv(self):
        """Initialize CSV with headers"""
        with open(self.output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()
        print(f"[CSV Watcher] Initialized CSV: {self.output_csv}")
    
    def _process_existing_files(self):
        """Process any network response files already in the directory"""
        existing_files = list(self.watch_dir.glob('*network-response*.txt'))
        if existing_files:
            print(f"[CSV Watcher] Found {len(existing_files)} existing response files")
            for file_path in sorted(existing_files):
                self._process_file(file_path)
    
    def on_created(self, event):
        """Handle new file creation events"""
        if event.is_directory:
            return
        
        # Check if this is a network response file
        if 'network-response' in event.src_path and event.src_path.endswith('.txt'):
            print(f"[CSV Watcher] New response file detected: {os.path.basename(event.src_path)}")
            time.sleep(0.5)  # Small delay to ensure file is fully written
            self._process_file(Path(event.src_path))
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        # Check if this is a network response file that was just written
        if 'network-response' in event.src_path and event.src_path.endswith('.txt'):
            file_path = Path(event.src_path)
            if file_path not in self.processed_files:
                print(f"[CSV Watcher] Response file modified: {os.path.basename(event.src_path)}")
                time.sleep(0.5)  # Small delay to ensure file is fully written
                self._process_file(file_path)
    
    def _process_file(self, file_path):
        """Process a single network response file"""
        if file_path in self.processed_files:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Parse and add to CSV
            new_rows = self._parse_response(data, os.path.basename(file_path))
            if new_rows:
                self._append_to_csv(new_rows)
            
            # Mark as processed
            self.processed_files.add(file_path)
            
        except Exception as e:
            print(f"[CSV Watcher] Error processing {file_path.name}: {e}")
    
    def _parse_response(self, data, source_name=""):
        """Parse network response data"""
        data_rows = []
        
        try:
            if not data or 'resorts' not in data or not data['resorts']:
                return data_rows
            
            for resort in data['resorts']:
                if not resort.get('hasAvailableUnits', False):
                    continue
                
                resort_offerings = resort.get('resortOfferings', [])
                
                for offering in resort_offerings:
                    offering_id = offering.get('offeringId', '')
                    offering_label = offering.get('offeringLabel', '')
                    
                    if 'Presidential Reserve' in offering_label:
                        if 'Presidential Reserve' not in offering_id:
                            display_offering_id = f"{offering_id} Presidential Reserve"
                        else:
                            display_offering_id = offering_id
                    else:
                        display_offering_id = offering_id
                    
                    accommodation_classes = offering.get('accomdationClasses', [])
                    
                    for accommodation in accommodation_classes:
                        calendar_days = accommodation.get('calendarDays', [])
                        
                        for day in calendar_days:
                            if not day.get('available', False):
                                continue
                            
                            date = day.get('date', '')
                            inventory_offerings = day.get('inventoryOfferings', [])
                            
                            for inventory in inventory_offerings:
                                available_count = inventory.get('availableCount', '0')
                                inventory_hash_key = inventory.get('inventoryOfferingHashKey', '')
                                inventory_label = inventory.get('invenOffrngLabel', '')
                                
                                if 'Presidential Reserve' in offering_label and 'Presidential Reserve' not in inventory_label:
                                    inventory_label = f"{inventory_label} (Presidential Reserve)"
                                
                                if int(available_count) > 0:
                                    row = {
                                        'date': date,
                                        'offeringId': display_offering_id,
                                        'inventoryOfferingHashKey': inventory_hash_key,
                                        'invenOffrngLabel': inventory_label,
                                        'availableCount': available_count
                                    }
                                    data_rows.append(row)
            
            if data_rows:
                print(f"[CSV Watcher] Parsed {len(data_rows)} records from {source_name}")
            
        except Exception as e:
            print(f"[CSV Watcher] Parse error: {e}")
        
        return data_rows
    
    def _append_to_csv(self, new_rows):
        """Append new unique rows to CSV"""
        with self.lock:
            unique_new_rows = []
            
            for row in new_rows:
                key = (row['date'], row['offeringId'], row['inventoryOfferingHashKey'], row['invenOffrngLabel'])
                
                if key not in self.unique_combinations:
                    self.unique_combinations[key] = row
                    unique_new_rows.append(row)
            
            if unique_new_rows:
                try:
                    with open(self.output_csv, 'a', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                        for row in unique_new_rows:
                            writer.writerow(row)
                    
                    print(f"[CSV Watcher] Added {len(unique_new_rows)} new unique rows (Total: {len(self.unique_combinations)})")
                except Exception as e:
                    print(f"[CSV Watcher] Error writing to CSV: {e}")
    
    def regenerate_sorted_csv(self):
        """Regenerate CSV with sorted data"""
        with self.lock:
            try:
                sorted_data = sorted(self.unique_combinations.values(),
                                   key=lambda x: (x['date'], x['offeringId'], x['invenOffrngLabel']))
                
                with open(self.output_csv, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                    writer.writeheader()
                    for row in sorted_data:
                        writer.writerow(row)
                
                print(f"[CSV Watcher] Regenerated sorted CSV with {len(sorted_data)} rows")
            except Exception as e:
                print(f"[CSV Watcher] Error regenerating CSV: {e}")

def run_watcher(watch_dir, output_csv, regenerate_interval=60):
    """
    Run the file watcher
    
    Args:
        watch_dir: Directory to watch for network response files
        output_csv: Path to output CSV file
        regenerate_interval: Seconds between CSV regenerations (0 to disable)
    """
    # Create event handler
    event_handler = AvailabilityCSVGenerator(watch_dir, output_csv)
    
    # Create observer
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=False)
    
    # Start watching
    observer.start()
    print(f"[CSV Watcher] Monitoring directory: {watch_dir}")
    print(f"[CSV Watcher] Press Ctrl+C to stop")
    
    try:
        last_regenerate = time.time()
        
        while True:
            time.sleep(1)
            
            # Periodically regenerate sorted CSV
            if regenerate_interval > 0:
                if time.time() - last_regenerate > regenerate_interval:
                    event_handler.regenerate_sorted_csv()
                    last_regenerate = time.time()
    
    except KeyboardInterrupt:
        observer.stop()
        print("\n[CSV Watcher] Stopping...")
        
        # Final regeneration
        event_handler.regenerate_sorted_csv()
        print(f"[CSV Watcher] Final CSV saved: {output_csv}")
        print(f"[CSV Watcher] Total unique records: {len(event_handler.unique_combinations)}")
    
    observer.join()

def main():
    """Main entry point with command line arguments"""
    parser = argparse.ArgumentParser(
        description='Real-time CSV generator for Wyndham availability data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Watch current directory's screens/NewFolder
  python wyndham_csv_watcher.py
  
  # Watch specific directory
  python wyndham_csv_watcher.py --watch-dir /path/to/responses
  
  # Custom output file
  python wyndham_csv_watcher.py --output availability_data.csv
  
  # Regenerate sorted CSV every 30 seconds
  python wyndham_csv_watcher.py --regenerate-interval 30
  
This can run alongside the scanner for real-time updates, or process
existing files after the scan is complete.
        """
    )
    
    parser.add_argument(
        '--watch-dir',
        default='screens/NewFolder',
        help='Directory to watch for network response files (default: screens/NewFolder)'
    )
    
    parser.add_argument(
        '--output',
        default='wyndham_availability_realtime.csv',
        help='Output CSV file path (default: wyndham_availability_realtime.csv)'
    )
    
    parser.add_argument(
        '--regenerate-interval',
        type=int,
        default=60,
        help='Seconds between CSV regenerations, 0 to disable (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Check if watch directory exists
    watch_dir = Path(args.watch_dir)
    if not watch_dir.exists():
        print(f"Error: Watch directory does not exist: {watch_dir}")
        print("Creating directory...")
        watch_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine output path
    if '/' in args.output or '\\' in args.output:
        output_csv = Path(args.output)
    else:
        # Put in watch directory by default
        output_csv = watch_dir / args.output
    
    print("="*60)
    print("Wyndham Real-time CSV Generator")
    print("="*60)
    print(f"Watch Directory: {watch_dir.absolute()}")
    print(f"Output CSV: {output_csv.absolute()}")
    print(f"Regenerate Interval: {args.regenerate_interval}s")
    print("="*60)
    
    # Run the watcher
    run_watcher(watch_dir, output_csv, args.regenerate_interval)

if __name__ == "__main__":
    main()
