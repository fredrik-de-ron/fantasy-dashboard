import httpx
import sys
from datetime import datetime, timezone, timedelta

print("Kollar om det spelades matcher igår...")

svar = httpx.get('https://fantasy.allsvenskan.se/api/fixtures/')
fixtures = svar.json()

# Igår i UTC
igar = (datetime.now(timezone.utc) - timedelta(days=1)).date()

matcher_igar = [
    f for f in fixtures
    if f.get('finished') and f.get('kickoff_time', '')[:10] == str(igar)
]

print(f"Datum kontrollerat: {igar}")
print(f"Antal avklarade matcher igår: {len(matcher_igar)}")

if matcher_igar:
    for m in matcher_igar:
        print(f"  GW{m['event']} | {m['kickoff_time'][:10]} | {m['team_h_score']}-{m['team_a_score']}")
    print("✓ Matchdag detekterad — kör uppdatering")
    sys.exit(0)
else:
    print("✗ Ingen match igår — hoppar över uppdatering")
    sys.exit(1)