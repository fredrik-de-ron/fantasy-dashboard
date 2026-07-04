import httpx
import sys
from datetime import datetime, timezone, timedelta

print("Kollar om imorgon är omgångsdeadline...")

svar = httpx.get('https://fantasy.allsvenskan.se/api/bootstrap-static/')
data = svar.json()

nu = datetime.now(timezone.utc)
imorgon = (nu + timedelta(days=1)).date()

# Hitta nästa omgång som inte är avklarad
nasta = None
for e in data['events']:
    if not e.get('finished') and e.get('deadline_time'):
        nasta = e
        break

if not nasta:
    print("Ingen kommande omgång hittad")
    sys.exit(1)

deadline = datetime.fromisoformat(nasta['deadline_time'].replace('Z', '+00:00'))
deadline_datum = deadline.date()

print(f"Nästa omgång: GW{nasta['id']}")
print(f"Deadline: {deadline_datum} kl {deadline.strftime('%H:%M')} UTC")
print(f"Imorgon: {imorgon}")

if deadline_datum == imorgon:
    print(f"✓ Imorgon är deadline för GW{nasta['id']} — kör AI-analys!")
    sys.exit(0)
else:
    dagar_kvar = (deadline_datum - nu.date()).days
    print(f"✗ Deadline är om {dagar_kvar} dagar — hoppar över AI-analys")
    sys.exit(1)