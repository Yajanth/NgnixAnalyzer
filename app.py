from flask import Flask, request, jsonify
import re
import requests
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

import io

# Endpoint: Top IPs
@app.route("/top-ips")
def top_ips():
    ip_counts = df['ip'].value_counts().reset_index()
    ip_counts.columns = ['ip', 'request_count']
    return jsonify(ip_counts.to_dict(orient='records'))

# Endpoint: Status Code Summary
@app.route("/status-summary")
def status_summary():
    status_counts = df['status'].value_counts().sort_index().reset_index()
    status_counts.columns = ['status_code', 'count']
    return jsonify(status_counts.to_dict(orient='records'))

# Endpoint: Traffic Over Time
@app.route("/traffic-trend")
def traffic_trend():
    df_time = df.copy()
    df_time['minute'] = df_time['time'].dt.strftime('%Y-%m-%d %H:%M')
    trend = df_time.groupby('minute').size().reset_index(name='requests')
    return jsonify(trend.to_dict(orient='records'))

# Endpoint: Anomalous IPs (many requests)
@app.route("/anomalies/high-volume")
def high_volume_ips():
    threshold = int(request.args.get("threshold", 3))  # default = 3 requests
    ip_counts = df['ip'].value_counts()
    suspicious = ip_counts[ip_counts > threshold].reset_index()
    suspicious.columns = ['ip', 'request_count']
    return jsonify(suspicious.to_dict(orient='records'))

# Endpoint: Burst of errors (4xx or 5xx)
@app.route("/anomalies/error-spike")
def error_spike():
    df_error = df[df['status'] >= 400].copy()
    df_error['minute'] = df_error['time'].dt.strftime('%Y-%m-%d %H:%M')
    grouped = df_error.groupby('minute').size().reset_index(name='error_count')
    spikes = grouped[grouped['error_count'] > 2]  # tweak threshold as needed
    return jsonify(spikes.to_dict(orient='records'))

# Endpoint: Most requested URLs
@app.route("/top-urls")
def top_urls():
    url_counts = df['url'].value_counts().reset_index()
    url_counts.columns = ['url', 'request_count']
    return jsonify(url_counts.to_dict(orient='records'))

# Endpoint: Top User Agents
@app.route("/top-agents")
def top_user_agents():
    ua_counts = df['user_agent'].value_counts().head(10).reset_index()
    ua_counts.columns = ['user_agent', 'count']
    return jsonify(ua_counts.to_dict(orient='records'))

# Endpoint: Export Summary Report
@app.route("/report")
def summary_report():
    summary = {
        "total_requests": len(df),
        "unique_ips": df['ip'].nunique(),
        "status_summary": df['status'].value_counts().to_dict(),
        "top_urls": df['url'].value_counts().head(5).to_dict(),
        "top_ips": df['ip'].value_counts().head(5).to_dict()
    }

    return jsonify(summary)

# Add derived columns
df['minute'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
df['status_category'] = df['status'] // 100 * 100



IPINFO_TOKEN = 'e1188bd09c6e03'  # replace with your real token

def get_ip_location(ip):
    try:
        url = f"https://ipinfo.io/{ip}?token={IPINFO_TOKEN}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            loc = data.get("loc", ",").split(",")  # 'lat,long' format
            return data.get('country')+","+ data.get('city'),

                # 'city': data.get('city'),
                # 'region': data.get('region'),
                # 'latitude': float(loc[0]) if loc[0] else None,
                # 'longitude': float(loc[1]) if len(loc) > 1 else None
            
    except Exception as e:
        print(f"IPINFO lookup failed for {ip}: {e}")
    return {
        'city': None, 'region': None, 'country': None,
        'latitude': None, 'longitude': None
    }

@app.route("/anomalies/ip-spike")
def detect_ip_spike():
    threshold = int(request.args.get("threshold", 3))
    ip_minute_counts = df.groupby(['ip', 'minute']).size().reset_index(name='count')
    spikes = ip_minute_counts[ip_minute_counts['count'] > threshold]

    enriched = []
    for _, row in spikes.iterrows():
        ip = row['ip']
        location = get_ip_location(ip)

        enriched.append({
            'ip': ip,
            'minute': row['minute'],
            'count': row['count'],
            'location': location[0]
        })

    return jsonify(enriched)

# 🔥 Error burst detection (4xx/5xx)
@app.route("/anomalies/error-burst")
def detect_error_burst():
    errors = df[df['status_category'].isin([400, 500])]
    burst = errors.groupby('minute').size().reset_index(name='error_count')
    burst = burst[burst['error_count'] > 15]  # tweak threshold
    return jsonify(burst.to_dict(orient='records'))

# 🎯 Hot path detection (rare URLs that spike)
@app.route("/anomalies/hot-path")
def detect_hot_path():
    url_counts = df['url'].value_counts()
    rare_urls = url_counts[url_counts < 3].index
    url_minute_counts = df[df['url'].isin(rare_urls)].groupby(['url', 'minute']).size().reset_index(name='count')
    hot_paths = url_minute_counts[url_minute_counts['count'] > 1]
    return jsonify(hot_paths.to_dict(orient='records'))

# 🕵️ Suspicious User-Agent detection
@app.route("/anomalies/suspicious-agents")
def detect_suspicious_agents():
    pattern = r'bot|crawl|scan|WordPress'
    sus = df[df['user_agent'].str.contains(pattern, flags=re.I, regex=True)]
    return jsonify(sus[['ip', 'user_agent', 'time']].astype(str).to_dict(orient='records'))

# ⏱️ POST flood detection
@app.route("/anomalies/post-flood")
def detect_post_flood():
    threshold = int(request.args.get("threshold", 2))  # POSTs per minute
    post_df = df[df['method'] == 'POST']
    post_counts = post_df.groupby(['ip', 'minute']).size().reset_index(name='post_count')
    floods = post_counts[post_counts['post_count'] > threshold]
    return jsonify(floods.to_dict(orient='records'))

# 🌍 Geo-anomalies (mocked – flags specific IP ranges)
@app.route("/anomalies/geo-anomalies")
def geo_anomalies():
    suspicious = df[df['ip'].str.startswith(('20.', '84.'))]
    return jsonify(suspicious[['ip', 'time', 'url']].astype(str).to_dict(orient='records'))




def search_logs_by_regex(log_file_path, input_regex):
    try:
        pattern = re.compile(input_regex)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    matches = []
    with open(log_file_path, 'r') as file:
        for line in file:
            if pattern.search(line):
                matches.append(line.strip())

    return matches if matches else ["No matches found."]
# Run Flask
if __name__ == '__main__':
    app.run(debug=True)
