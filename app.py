from flask import Flask, request, jsonify
import re
import pandas as pd
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)

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

# Fix timezone formatting
def fix_timezone_format(dt_str):
    import re
    match = re.match(r'^(.+?)([+-]\d{4})$', dt_str.strip())
    if match:
        return f"{match.group(1).strip()} {match.group(2)}"
    return dt_str
CORS(app)
# Endpoint: filter by URL and optional method
@app.route('/byUrl')
def byUrl():
    reqUrl = request.args.get('reqUrl')
    reqMethord = request.args.get('reqMethord')  # intentionally kept typo to match your original code

    if reqUrl and reqMethord:
        df_by_url = df[(df["url"] == reqUrl) & (df["method"] == reqMethord)]
    elif reqUrl:
        df_by_url = df[df["url"] == reqUrl]
    else:
        return jsonify({"error": "NO URL PROVIDED"}), 400

    result = df_by_url[['ip', 'time', 'status']].copy()
    result['time'] = result['time'].astype(str)
    return jsonify(result.to_dict(orient='records'))

# Endpoint: filter by time range
@app.route("/timeframe")
def byTimeFrame():
    from_time_str = request.args.get("from")
    to_time_str = request.args.get("to")

    if not from_time_str or not to_time_str:
        return jsonify({"error": "Both 'from' and 'to' query parameters are required"}), 400

    from_time_str = fix_timezone_format(from_time_str)
    to_time_str = fix_timezone_format(to_time_str)

    try:
        from_time = datetime.strptime(from_time_str, '%d/%b/%Y:%H:%M:%S %z')
        to_time = datetime.strptime(to_time_str, '%d/%b/%Y:%H:%M:%S %z')
        print(from_time,"\n",to_time)
    except ValueError:
        return jsonify({
            "error": "Invalid datetime format. Use format like 17/Apr/2025:05:19:27 +0100"
        }), 400

    df_filtered = df[(df['time'] >= from_time) & (df['time'] <= to_time)]

    if df_filtered.empty:
        return jsonify({"message": "No records found in the given timeframe"}), 404

    result = df_filtered[['ip', 'url', 'method', 'time']].copy()
    result['time'] = result['time'].astype(str)

    return jsonify(result.to_dict(orient='records'))

# Run Flask
if __name__ == '__main__':
    app.run(debug=True)
