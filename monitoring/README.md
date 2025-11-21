# Wyndham Scanner with Real-time CSV Generation

## Overview
This project combines the Wyndham calendar UI scanner with real-time CSV generation, allowing you to see availability data as it's being collected rather than waiting until the end of the scan.

## Implementation Options

### 1. **Integrated Solution** (`wyndham_realtime_scanner.py`)
The all-in-one solution that combines scanning and CSV generation in a single script.

**Pros:**
- Single script to manage
- CSV updates happen immediately as responses are captured
- Thread-safe implementation
- Automatic CSV sorting at regular intervals

**Usage:**
```bash
python wyndham_realtime_scanner.py
```

**Features:**
- Real-time CSV updates as each network response is captured
- Automatic deduplication of data
- Periodic CSV regeneration for proper sorting
- Thread-safe operations for concurrent access
- Saves both CSV and JSON backups

### 2. **File Watcher Solution** (`wyndham_csv_watcher.py`)
A separate process that watches for new network response files and generates CSV in real-time.

**Pros:**
- Can run alongside existing scanner without modification
- Can process files after scan is complete
- Modular design - scanner and CSV generator are independent
- Can be stopped/started independently

**Usage:**
```bash
# Run in a separate terminal alongside your original scanner
python wyndham_csv_watcher.py

# Or with custom options
python wyndham_csv_watcher.py --watch-dir screens/NewFolder --output my_data.csv --regenerate-interval 30
```

**Features:**
- Monitors directory for new network response files
- Processes existing files on startup
- Real-time CSV updates as files are created
- Configurable regeneration interval for sorting
- Can run as a background service

## Installation Requirements

### Core Requirements (both solutions):
```bash
pip install selenium webdriver-manager
```

### Additional for File Watcher:
```bash
pip install watchdog
```

## How Real-time Updates Work

### Integrated Solution Flow:
1. Scanner navigates to date range
2. Network response is captured via Chrome DevTools Protocol
3. Response is immediately parsed for availability data
4. CSV is updated with new unique records
5. Screenshot and JSON backup are saved
6. Process continues to next date range

### File Watcher Flow:
1. Original scanner saves network response files
2. Watcher detects new file creation/modification
3. File is parsed for availability data
4. CSV is updated with new unique records
5. Periodic regeneration ensures proper sorting

## CSV Output Format

The CSV file contains the following columns:
- `date`: Check-in date
- `offeringId`: Resort/property identifier
- `inventoryOfferingHashKey`: Unique inventory key
- `invenOffrngLabel`: Room type description
- `availableCount`: Number of available units

## Key Improvements

### 1. **Real-time Visibility**
- See results as they're collected
- No need to wait for complete scan
- Can stop early if needed data is found

### 2. **Data Deduplication**
- Automatically removes duplicate entries
- Tracks unique combinations of date/property/room
- Only first occurrence is kept

### 3. **Thread Safety**
- CSV operations are thread-safe
- Multiple processes can read while writing occurs
- No data corruption from concurrent access

### 4. **Incremental Updates**
- CSV grows incrementally
- New data appended as discovered
- Periodic regeneration maintains sort order

## Usage Scenarios

### Scenario 1: Replace Existing Scanner
Use `wyndham_realtime_scanner.py` as a complete replacement for your current setup.

### Scenario 2: Enhance Existing Scanner
Run `wyndham_csv_watcher.py` alongside your current scanner without any modifications.

### Scenario 3: Post-Process Existing Data
Run `wyndham_csv_watcher.py` after a scan to process all collected response files.

### Scenario 4: Continuous Monitoring
Run `wyndham_csv_watcher.py` as a service that continuously monitors for new data.

## Configuration Options

### Integrated Scanner Configuration:
```python
# In wyndham_realtime_scanner.py
MONTHS_TO_SCAN = 9  # Number of months to scan
STAY_LENGTH_DAYS = 3  # Length of stay (3 = 4-day window)
CSV_OUTPUT_FILE = "wyndham_availability_realtime.csv"
SCREEN_DIR = "screens/NewFolder"
```

### File Watcher Configuration:
```python
# Command line arguments
--watch-dir: Directory to monitor (default: screens/NewFolder)
--output: Output CSV file (default: wyndham_availability_realtime.csv)
--regenerate-interval: Seconds between CSV sorts (default: 60)
```

## Advanced Features

### Custom Processing Pipeline
You can extend either solution to:
- Send notifications when specific availability is found
- Upload CSV to cloud storage in real-time
- Trigger alerts based on availability patterns
- Generate summary statistics during scan

### Integration with Other Tools
The CSV can be:
- Imported into Excel/Google Sheets in real-time
- Connected to a database for analysis
- Used by other scripts for notifications
- Visualized in a dashboard

## Troubleshooting

### Issue: CSV not updating
- Check file permissions in output directory
- Verify network responses contain availability data
- Ensure no other process has CSV file locked

### Issue: Duplicate entries
- Verify unique combination logic
- Check if multiple scanners running simultaneously
- Review deduplication key fields

### Issue: File watcher not detecting files
- Verify watch directory path is correct
- Check file naming pattern matches filter
- Ensure sufficient delay for file write completion

## Performance Considerations

- **Memory Usage**: Both solutions maintain unique combinations in memory
- **CSV Size**: Large scans may produce files with thousands of rows
- **Processing Speed**: Real-time updates add minimal overhead (<100ms per response)
- **Disk I/O**: Frequent CSV updates may impact SSD wear on very long scans

## Best Practices

1. **Regular Regeneration**: Set regeneration interval based on scan speed
2. **Backup JSON Files**: Keep network response files for debugging
3. **Monitor Progress**: Watch CSV row count to track scan progress
4. **Error Handling**: Both solutions continue on errors, logging issues
5. **Clean Shutdown**: Use Ctrl+C for proper CSV finalization

## Future Enhancements

Potential improvements to consider:
- Database backend instead of CSV for better performance
- Web interface for real-time monitoring
- Parallel scanning of multiple date ranges
- Smart scheduling based on availability patterns
- Integration with booking systems
