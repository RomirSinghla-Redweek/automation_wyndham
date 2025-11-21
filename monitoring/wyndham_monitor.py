#!/usr/bin/env python3
"""
Real-time monitoring dashboard for Wyndham availability CSV
Displays statistics and updates as the CSV file grows
"""

import csv
import time
import os
from datetime import datetime
from pathlib import Path
import argparse
from collections import defaultdict, Counter

class CSVMonitor:
    """Monitor and display statistics from the growing CSV file"""
    
    def __init__(self, csv_file):
        self.csv_file = Path(csv_file)
        self.last_modified = 0
        self.last_row_count = 0
        self.start_time = time.time()
        
    def read_csv_stats(self):
        """Read CSV and calculate statistics"""
        stats = {
            'total_rows': 0,
            'unique_dates': set(),
            'unique_properties': set(),
            'room_types': Counter(),
            'availability_by_date': defaultdict(int),
            'availability_by_property': defaultdict(int),
            'presidential_count': 0,
            'latest_date': None,
            'earliest_date': None,
            'file_size': 0
        }
        
        try:
            if not self.csv_file.exists():
                return stats
            
            stats['file_size'] = self.csv_file.stat().st_size
            
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    stats['total_rows'] += 1
                    
                    # Collect unique values
                    date = row.get('date', '')
                    offering_id = row.get('offeringId', '')
                    room_label = row.get('invenOffrngLabel', '')
                    available = int(row.get('availableCount', 0))
                    
                    if date:
                        stats['unique_dates'].add(date)
                        stats['availability_by_date'][date] += available
                        
                        # Track date range
                        if not stats['earliest_date'] or date < stats['earliest_date']:
                            stats['earliest_date'] = date
                        if not stats['latest_date'] or date > stats['latest_date']:
                            stats['latest_date'] = date
                    
                    if offering_id:
                        stats['unique_properties'].add(offering_id)
                        stats['availability_by_property'][offering_id] += available
                    
                    if room_label:
                        stats['room_types'][room_label] += 1
                        
                        if 'Presidential' in room_label or 'Presidential' in offering_id:
                            stats['presidential_count'] += 1
            
        except Exception as e:
            print(f"Error reading CSV: {e}")
        
        return stats
    
    def display_dashboard(self, stats, clear_screen=True):
        """Display formatted dashboard"""
        if clear_screen:
            os.system('cls' if os.name == 'nt' else 'clear')
        
        # Calculate runtime
        runtime = time.time() - self.start_time
        hours, remainder = divmod(runtime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Calculate rates
        rows_per_minute = stats['total_rows'] / (runtime / 60) if runtime > 0 else 0
        new_rows = stats['total_rows'] - self.last_row_count
        
        # Format file size
        size_mb = stats['file_size'] / (1024 * 1024)
        
        # Display dashboard
        print("=" * 80)
        print("                    WYNDHAM AVAILABILITY SCANNER MONITOR")
        print("=" * 80)
        
        print(f"\n📊 SCAN PROGRESS")
        print(f"   Runtime: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
        print(f"   CSV File: {self.csv_file.name} ({size_mb:.2f} MB)")
        print(f"   Status: {'🟢 ACTIVE' if new_rows > 0 else '🔴 IDLE'}")
        
        print(f"\n📈 STATISTICS")
        print(f"   Total Records: {stats['total_rows']:,}")
        print(f"   New Records (last update): {new_rows:,}")
        print(f"   Rate: {rows_per_minute:.1f} records/minute")
        
        print(f"\n📅 DATE COVERAGE")
        print(f"   Unique Dates: {len(stats['unique_dates'])}")
        if stats['earliest_date'] and stats['latest_date']:
            print(f"   Date Range: {stats['earliest_date']} to {stats['latest_date']}")
        print(f"   Total Availability: {sum(stats['availability_by_date'].values()):,} units")
        
        print(f"\n🏨 PROPERTIES")
        print(f"   Unique Properties: {len(stats['unique_properties'])}")
        print(f"   Presidential Reserve: {stats['presidential_count']:,} records")
        
        # Top properties by availability
        if stats['availability_by_property']:
            print(f"\n   Top 5 Properties by Availability:")
            top_properties = sorted(stats['availability_by_property'].items(), 
                                  key=lambda x: x[1], reverse=True)[:5]
            for prop, count in top_properties:
                prop_display = prop[:50] + "..." if len(prop) > 50 else prop
                print(f"     • {prop_display}: {count:,} units")
        
        print(f"\n🛏️ ROOM TYPES")
        print(f"   Unique Room Types: {len(stats['room_types'])}")
        
        # Top room types
        if stats['room_types']:
            print(f"\n   Top 5 Room Types:")
            for room_type, count in stats['room_types'].most_common(5):
                room_display = room_type[:45] + "..." if len(room_type) > 45 else room_type
                print(f"     • {room_display}: {count} records")
        
        # Dates with most availability
        if stats['availability_by_date']:
            print(f"\n📊 TOP AVAILABILITY DATES")
            top_dates = sorted(stats['availability_by_date'].items(), 
                             key=lambda x: x[1], reverse=True)[:5]
            for date, count in top_dates:
                print(f"     • {date}: {count:,} units available")
        
        print("\n" + "=" * 80)
        print("Press Ctrl+C to exit | Updates every 5 seconds")
        
        # Update for next iteration
        self.last_row_count = stats['total_rows']
    
    def run(self, update_interval=5, clear_screen=True):
        """Run the monitoring dashboard"""
        print("Starting CSV monitor...")
        print(f"Watching: {self.csv_file.absolute()}")
        
        try:
            while True:
                # Check if file has been modified
                if self.csv_file.exists():
                    current_modified = self.csv_file.stat().st_mtime
                    
                    if current_modified != self.last_modified or time.time() - self.start_time < 10:
                        self.last_modified = current_modified
                        
                        # Read stats and display
                        stats = self.read_csv_stats()
                        self.display_dashboard(stats, clear_screen)
                    elif time.time() % 30 < update_interval:
                        # Refresh display every 30 seconds even if no changes
                        stats = self.read_csv_stats()
                        self.display_dashboard(stats, clear_screen)
                else:
                    if clear_screen:
                        os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"Waiting for CSV file: {self.csv_file}")
                
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitor stopped.")
            
            # Display final stats
            stats = self.read_csv_stats()
            print(f"\nFinal Statistics:")
            print(f"  Total Records: {stats['total_rows']:,}")
            print(f"  Unique Dates: {len(stats['unique_dates'])}")
            print(f"  Unique Properties: {len(stats['unique_properties'])}")
            print(f"  File Size: {stats['file_size'] / (1024*1024):.2f} MB")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Real-time monitoring dashboard for Wyndham availability CSV'
    )
    
    parser.add_argument(
        'csv_file',
        nargs='?',
        default='wyndham_availability_realtime.csv',
        help='Path to CSV file to monitor (default: wyndham_availability_realtime.csv)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Update interval in seconds (default: 5)'
    )
    
    parser.add_argument(
        '--no-clear',
        action='store_true',
        help='Do not clear screen between updates'
    )
    
    args = parser.parse_args()
    
    # Find CSV file
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        # Try in screens/NewFolder
        alt_path = Path('screens/NewFolder') / args.csv_file
        if alt_path.exists():
            csv_path = alt_path
        else:
            print(f"Warning: CSV file not found: {csv_path}")
            print("Monitor will wait for file to be created...")
    
    # Run monitor
    monitor = CSVMonitor(csv_path)
    monitor.run(update_interval=args.interval, clear_screen=not args.no_clear)

if __name__ == "__main__":
    main()
