import httpx
import json
import os

print("Hämtar priser och spelarstatus...")

STATUS_TEXT = {
    "a": "Tillgänglig",
    "i": "Skadad",
    "u": "Lämnat klubben",
    "n": "Ej tillgänglig",
    "s": "Avstängd",
    "d": "Osäker",
}

svar = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/")
data = svar.json()

# Bygg uppslagstabell: fantasy_id -> aktuell data
aktuell = {}
for s in data["elements"]:
    aktuell[s["id"]] = {
        "pris":                s["now_cost"] / 10,
        "prisändring_omgång":  s["cost_change_event"] / 10,
        "prisändring_säsong":  s["cost_change_start"] / 10,
        "agarskap":            float(s["selected_by_percent"]),
        "transfers_in_omgång": s["transfers_in_event"],
        "transfers_out_omgång":s["transfers_out_event"],
        "status":              s["status"],
        "status_text":         STATUS_TEXT.get(s["status"], s["status"]),
        "nyheter":             s["news"],
        "chans_spela_nästa":   s["chance_of_playing_next_round"],
        "ep_nästa":            float(s["ep_next"]),
        "ep_denna":            float(s["ep_this"]),
        "form":                float(s["form"]),
    }

print(f"  {len(aktuell)} spelare hämtade från API")

# Ladda befintlig dashboard_data.json
if not os.path.exists("dashboard_data.json"):
    print("Fel: dashboard_data.json saknas — kör bygg_dashboard_data.py först")
    exit(1)

with open("dashboard_data.json", encoding="utf-8") as f:
    spelare = json.load(f)

# Uppdatera varje spelare med nya priser och status
uppdaterade = 0
prisandringar = []

for s in spelare:
    sid = s["id"]
    if sid not in aktuell:
        continue

    ny = aktuell[sid]
    gammalt_pris = s["pris"]

    # Uppdatera fälten
    s["pris"]                = ny["pris"]
    s["prisand"]             = ny["prisändring_omgång"]
    s["agarskap"]            = ny["agarskap"]
    s["trans_in"]            = ny["transfers_in_omgång"]
    s["trans_ut"]            = ny["transfers_out_omgång"]
    s["status"]              = ny["status"]
    s["status_text"]         = ny["status_text"]
    s["nyheter"]             = ny["nyheter"]
    s["chans"]               = ny["chans_spela_nästa"] or 100
    s["ep_nasta"]            = ny["ep_nästa"]
    s["form"]                = ny["form"]

    uppdaterade += 1

    # Notera prisändringar
    if abs(ny["pris"] - gammalt_pris) >= 0.1:
        riktning = "↑" if ny["pris"] > gammalt_pris else "↓"
        prisandringar.append(f"  {riktning} {s['namn']} ({s['lag']}): {gammalt_pris:.1f} → {ny['pris']:.1f}")

print(f"  {uppdaterade} spelare uppdaterade")

if prisandringar:
    print(f"\nPrisändringar sedan senaste körning:")
    for p in prisandringar:
        print(p)
else:
    print("\nInga prisändringar sedan senaste körning")

# Visa statusändringar
ej_tillgangliga = [s for s in spelare if s["status"] != "a"]
print(f"\nSpelare ej tillgängliga: {len(ej_tillgangliga)}")
for s in sorted(ej_tillgangliga, key=lambda x: x["status"]):
    print(f"  {s['namn']:<22} {s['status_text']:<16} {s['nyheter'][:40] if s['nyheter'] else ''}")

# Spara uppdaterad fil
with open("dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(spelare, f, ensure_ascii=False, separators=(",", ":"))

print(f"\nKlart! dashboard_data.json uppdaterad med färska priser och status")