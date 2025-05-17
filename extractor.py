import re
import pandas as pd
from datetime import datetime

# Regex to parse log lines
log_pattern = re.compile(
    r'(?P<ip>\S+) - - \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<url>\S+) \S+" (?P<status>\d+) (?P<size>\d+) ".+?" "(?P<user_agent>.+?)"'
)

# Function to parse a single line
def parse_log_line(line):
    match = log_pattern.match(line)
    if match:
        data = match.groupdict()
        try:
            data['time'] = datetime.strptime(data['time'], '%d/%b/%Y:%H:%M:%S %z')
            data['status'] = int(data['status'])
            return data
        except Exception as e:
            print("Time parse error:", e)
    return None

# Read and parse the log file
file_name = "access.log"
parsed = []
with open(file_name) as f:
    for line in f:
        log = parse_log_line(line)
        if log:
            parsed.append(log)

# Create DataFrame
df = pd.DataFrame(parsed)

# Function to filter logs by time frame
def byTimeFrame(from_time_str, to_time_str):
    if not from_time_str or not to_time_str:
        return {"error": "Both 'from' and 'to' query parameters are required"}

    # Ensure timezone offset has a space (e.g., "+0100" -> " +0100")
    def fix_timezone_format(s):
        import re
        match = re.match(r'^(.+?)([+-]\d{4})$', s.strip())
        if match:
            return f"{match.group(1).strip()} {match.group(2)}"
        return s

    from_time_str = fix_timezone_format(from_time_str)
    to_time_str = fix_timezone_format(to_time_str)

    try:
        from_time = datetime.strptime(from_time_str, '%d/%b/%Y:%H:%M:%S %z')
        to_time = datetime.strptime(to_time_str, '%d/%b/%Y:%H:%M:%S %z')
    except ValueError:
        return {
            "error": "Invalid datetime format. Use format like 17/Apr/2025:05:19:27 +0100"
        }

    df_filtered = df[(df['time'] >= from_time) & (df['time'] <= to_time)]

    if df_filtered.empty:
        return {"message": "No records found in the given timeframe"}

    result = df_filtered[['ip', 'url', 'method', 'time']].copy()
    result['time'] = result['time'].astype(str)
    return result.to_dict(orient='records')

# Test the function
output = byTimeFrame("17/Apr/2025:05:15:00+0100", "17/Apr/2025:05:17:00+0100")
print(output)

