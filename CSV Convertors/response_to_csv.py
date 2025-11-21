#!/usr/bin/env python3
"""
Fixed script to parse Wyndham network response files and generate CSV with proper format.
This version is compatible with both Windows and Linux systems.
This script extracts availability data from JSON network responses and creates a CSV file
with the following columns: date, offeringId, inventoryOfferingHashKey, invenOffrngLabel, availableCount
""" 

import json
import csv
import os
import sys
from pathlib import Path
from collections import defaultdict

def parse_network_response(file_path):
    """
    Parse a single network response file and extract availability data.
    
    Args:
        file_path (str): Path to the network response JSON file
    
    Returns:
        list: List of dictionaries containing parsed availability data
    """
    data_rows = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if resorts exist in the response
        if 'resorts' not in data or not data['resorts']:
            print(f"  No resort data found in {os.path.basename(file_path)}")
            return data_rows
        
        for resort in data['resorts']:
            if not resort.get('hasAvailableUnits', False):
                continue
            
            # Get resort offerings
            resort_offerings = resort.get('resortOfferings', [])
            
            for offering in resort_offerings:
                offering_id = offering.get('offeringId', '')
                offering_label = offering.get('offeringLabel', '')
                
                # Handle Presidential Reserve offerings specially
                if 'Presidential Reserve' in offering_label:
                    # Append "Presidential Reserve" to the offeringId for clarity
                    # Check if offeringId already contains "Presidential Reserve" to avoid duplication
                    if 'Presidential Reserve' not in offering_id:
                        display_offering_id = f"{offering_id} Presidential Reserve"
                    else:
                        display_offering_id = offering_id
                else:
                    display_offering_id = offering_id
                
                # Get accommodation classes
                accommodation_classes = offering.get('accomdationClasses', [])
                
                for accommodation in accommodation_classes:
                    # Get calendar days with availability
                    calendar_days = accommodation.get('calendarDays', [])
                    
                    for day in calendar_days:
                        if not day.get('available', False):
                            continue
                        
                        date = day.get('date', '')
                        
                        # Get inventory offerings for this day
                        inventory_offerings = day.get('inventoryOfferings', [])
                        
                        for inventory in inventory_offerings:
                            # Extract required fields
                            available_count = inventory.get('availableCount', '0')
                            inventory_hash_key = inventory.get('inventoryOfferingHashKey', '')
                            inventory_label = inventory.get('invenOffrngLabel', '')
                            
                            # Handle Presidential Reserve labels
                            if 'Presidential Reserve' in offering_label and 'Presidential Reserve' not in inventory_label:
                                inventory_label = f"{inventory_label} (Presidential Reserve)"
                            
                            # Only add rows with actual availability
                            if int(available_count) > 0:
                                row = {
                                    'date': date,
                                    'offeringId': display_offering_id,
                                    'inventoryOfferingHashKey': inventory_hash_key,
                                    'invenOffrngLabel': inventory_label,
                                    'availableCount': available_count
                                }
                                data_rows.append(row)
        
        print(f"  Parsed {len(data_rows)} availability records from {os.path.basename(file_path)}")
        
    except json.JSONDecodeError as e:
        print(f"  Error parsing JSON in {os.path.basename(file_path)}: {e}")
    except Exception as e:
        print(f"  Error processing {os.path.basename(file_path)}: {e}")
    
    return data_rows

def aggregate_by_date(all_data):
    """
    Aggregate data by date and room type to show the first occurrence's availability count.
    
    Args:
        all_data (list): List of all parsed data rows
    
    Returns:
        list: Aggregated data rows
    """
    # Create a dictionary to track unique combinations
    unique_combinations = {}
    
    for row in all_data:
        # Create a unique key for date + offeringId + inventoryOfferingHashKey
        key = (row['date'], row['offeringId'], row['inventoryOfferingHashKey'], row['invenOffrngLabel'])
        
        # Only keep the first occurrence
        if key not in unique_combinations:
            unique_combinations[key] = row
    
    # Sort by date, then by offeringId, then by room type
    sorted_data = sorted(unique_combinations.values(), 
                        key=lambda x: (x['date'], x['offeringId'], x['invenOffrngLabel']))
    
    return sorted_data

def process_directory(directory_path, output_file='wyndham_availability.csv'):
    """
    Process all network response files in a directory and create a single CSV output.
    
    Args:
        directory_path (str): Path to directory containing network response files
        output_file (str): Name of output CSV file
    """
    all_data = []
    
    # Find all network response files
    directory = Path(directory_path)
    response_files = list(directory.glob('*network-response*.txt'))
    
    if not response_files:
        print(f"No network response files found in {directory_path}")
        return
    
    print(f"Found {len(response_files)} network response files to process")
    print("-" * 60)
    
    # Process each file
    for file_path in sorted(response_files):
        print(f"Processing: {file_path.name}")
        file_data = parse_network_response(file_path)
        all_data.extend(file_data)
    
    print("-" * 60)
    print(f"Total records collected: {len(all_data)}")
    
    # Aggregate data to get unique combinations
    aggregated_data = aggregate_by_date(all_data)
    print(f"Unique combinations after aggregation: {len(aggregated_data)}")
    
    # Write to CSV - save in the same directory as the input files
    output_path = Path(directory_path) / output_file
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['date', 'offeringId', 'inventoryOfferingHashKey', 'invenOffrngLabel', 'availableCount']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write data rows
            for row in aggregated_data:
                writer.writerow(row)
        
        print(f"\nCSV file created: {output_path}")
        print(f"Total rows written: {len(aggregated_data)}")
        
        # Show sample of output
        if aggregated_data:
            print("\nSample of output (first 10 rows):")
            print("-" * 100)
            print(f"{'date':<12} {'offeringId':<50} {'hashKey':<12} {'label':<45} {'count':<6}")
            print("-" * 100)
            for row in aggregated_data[:10]:
                print(f"{row['date']:<12} {row['offeringId']:<50} {row['inventoryOfferingHashKey']:<12} "
                      f"{row['invenOffrngLabel']:<45} {row['availableCount']:<6}")
    
    except Exception as e:
        print(f"\nError writing CSV file: {e}")
        print(f"Attempted to write to: {output_path}")
        
        # Try alternative location (current directory)
        alt_output_path = Path.cwd() / output_file
        print(f"\nTrying alternative location: {alt_output_path}")
        
        try:
            with open(alt_output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['date', 'offeringId', 'inventoryOfferingHashKey', 'invenOffrngLabel', 'availableCount']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in aggregated_data:
                    writer.writerow(row)
            
            print(f"CSV file created successfully at: {alt_output_path}")
            print(f"Total rows written: {len(aggregated_data)}")
        except Exception as e2:
            print(f"Error writing to alternative location: {e2}")

def main():
    """Main function to run the script."""
    if len(sys.argv) > 1:
        directory_path = sys.argv[1]
    else:
        # Default to current directory
        directory_path = '.'
    
    # Check if directory exists
    if not os.path.isdir(directory_path):
        print(f"Error: Directory '{directory_path}' does not exist")
        sys.exit(1)
    
    print(f"Processing network response files in: {os.path.abspath(directory_path)}")
    print("=" * 60)
    
    process_directory(directory_path)

if __name__ == "__main__":
    main()
