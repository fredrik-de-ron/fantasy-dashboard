import json
import os
import re

print("Bygger offline-dashboard...")

with open("dashboard_data.json", encoding="utf-8") as f:
    data = json.load(f)

ai_insikter = None
if os.path.exists("ai_insikter.json"):
    with open("ai_insikter.json", encoding="utf-8") as f:
        ai_insikter = json.load(f)
    print(f"  AI-insikter hittade för omgång {ai_insikter['omgang']}")
else:
    print("  Ingen ai_insikter.json hittad")

with open("dashboard.html", encoding="utf-8") as f:
    html = f.read()

data_json = json.dumps(data, ensure_ascii=False)
ai_json   = json.dumps(ai_insikter, ensure_ascii=False) if ai_insikter else "null"

injekt = f"""<script>
window.DASHBOARD_DATA = {data_json};
window.AI_INSIKTER = {ai_json};
</script>
"""

html = html.replace("<script>", injekt + "<script>", 1)

html = re.sub(
    r'fetch\("dashboard_data\.json"\)\s*\n\s*\.then\(r => r\.json\(\)\)\s*\n\s*\.then\(data =>',
    'Promise.resolve(window.DASHBOARD_DATA)\n  .then(data =>',
    html
)

html = re.sub(
    r'fetch\("ai_insikter\.json"\)\s*\n\s*\.then\(r => r\.json\(\)\)\s*\n\s*\.then\(data =>',
    'Promise.resolve(window.AI_INSIKTER || Promise.reject())\n    .then(data =>',
    html
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

ok_data = "window.DASHBOARD_DATA" in html
ok_ai   = "window.AI_INSIKTER" in html
ok_fetch_data = 'fetch("dashboard_data.json")' not in html
ok_fetch_ai   = 'fetch("ai_insikter.json")' not in html

print(f"  Data inbäddad:     {'✓' if ok_data else '✗'}")
print(f"  AI inbäddad:       {'✓' if ok_ai else '✗'}")
print(f"  Fetch data ersatt: {'✓' if ok_fetch_data else '✗'}")
print(f"  Fetch AI ersatt:   {'✓' if ok_fetch_ai else '✗'}")

storlek = os.path.getsize("index.html") / 1024
print(f"\nKlar! index.html ({storlek:.0f} KB)")