from flask import Flask, request, jsonify
import re
import pandas as pd
from datetime import datetime

app = Flask(__name__)

log_pattern = re.compile(
    r'(?P<ip>\S+) - - \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<url>\S+) \S+" (?P<status>\d+) (?P<size>\d+) ".+?" "(?P<user_agent>.+?)"'
)

def parse_log_line(line):
    match = log_pattern.match(line)
    if match:
        data = match.groupdict()
        data['time'] = datetime.strptime(data['time'], '%d/%b/%Y:%H:%M:%S %z')
        data['status'] = int(data['status'])
        return data
    return None

file_name = "access.log"
with open(file_name) as f:
    parsed = [parse_log_line(line) for line in f if parse_log_line(line)]

df = pd.DataFrame(parsed)

@app.route('/byUrl')
def byUrl():
    reqUrl = request.args.get('reqUrl')
    reqMethord = request.args.get('reqMethord')  # fix spelling here if needed

    if reqUrl and reqMethord:
        df_by_url = df[(df["url"] == reqUrl) & (df["method"] == reqMethord)]
        # Convert to list of dicts
        result = df_by_url[['ip', 'time', 'status']].copy()
        # Convert datetime to string for JSON serialization
        result['time'] = result['time'].astype(str)
        return jsonify(result.to_dict(orient='records'))

    elif reqUrl and reqMethord is None:
        df_by_url = df[df["url"] == reqUrl]
        result = df_by_url[['ip', 'time', 'status']].copy()
        # Convert datetime to string for JSON serialization
        result['time'] = result['time'].astype(str)
        return jsonify(result.to_dict(orient='records'))

    else:
        return jsonify({"error": "NO URL PROVIDED"}), 400

@app.route("/timeframe")
def byTimeFrame():
    fromTime=request.args.get("from")
    toTime=request.args.get("to")




if __name__ == '__main__':
    app.run(debug=True)
