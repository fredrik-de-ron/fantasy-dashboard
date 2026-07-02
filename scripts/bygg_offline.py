import json

print("Bygger offline-dashboard...")

with open("dashboard_data.json", encoding="utf-8") as f:
    data = json.load(f)

with open("dashboard.html", encoding="utf-8") as f:
    html = f.read()

data_script = f'<script>window.DASHBOARD_DATA = {json.dumps(data, ensure_ascii=False)};</script>'

inbaddad = html.replace('<script>', data_script + '\n<script>', 1)

inbaddad = inbaddad.replace(
    'fetch("dashboard_data.json")\n  .then(r => r.json())\n  .then(data => {',
    'Promise.resolve(window.DASHBOARD_DATA)\n  .then(data => {'
)

with open("dashboard_offline.html", "w", encoding="utf-8") as f:
    f.write(inbaddad)

print("Klar! dashboard_offline.html är uppdaterad")