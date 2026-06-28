import httpx
import json
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
ALLSVENSKAN_ID = 67

def hamta_spelare(spelare_id):
    url = f"https://www.fotmob.com/api/data/playerData?id={spelare_id}"
    try:
        svar = httpx.get(url, headers=HEADERS, timeout=10)
        if svar.status_code != 200:
            return None
        return svar.json()
    except:
        return None

def extrahera_stats(data):
    """Plocka ut all statistik från firstSeasonStats."""
    stats = {}
    try:
        grupper = data["firstSeasonStats"]["statsSection"]["items"]
        for grupp in grupper:
            for item in grupp.get("items", []):
                nyckel = item["localizedTitleId"]
                stats[nyckel]        = item.get("statValue")
                stats[nyckel + "_p90"] = item.get("per90")
                stats[nyckel + "_pct"] = item.get("percentileRank")
    except:
        pass
    return stats

def hamta_lagkamrater(data):
    """Hämta ID:n på lagkamrater."""
    try:
        return [t["id"] for t in data["relatedLinksData"]["teammates"]]
    except:
        return []

def spelar_allsvenskan(data):
    """Kontrollera att spelaren är i Allsvenskan."""
    try:
        return data["mainLeague"]["leagueId"] == ALLSVENSKAN_ID
    except:
        return False

# --- Starta crawlen med Bjerkebo ---
att_besoka = [
    1386078, 741561, 1373211, 1280260, 120019, 1288276,
    1272349, 731267, 1276969, 1332456, 627560, 1339134,
    840708, 1114366, 859483, 173030
]
besokta     = set()
alla_spelare = {}

print("Startar FotMob-crawl för Allsvenskan 2026...")
print("(Hämtar en spelare i taget — tar några minuter)\n")

while att_besoka:
    spelare_id = att_besoka.pop(0)
    if spelare_id in besokta:
        continue
    besokta.add(spelare_id)

    data = hamta_spelare(spelare_id)
    if not data:
        continue

    # Spara bara Allsvenskan-spelare
    if spelar_allsvenskan(data):
        stats = extrahera_stats(data)
        alla_spelare[spelare_id] = {
            "fotmob_id":  spelare_id,
            "namn":       data["name"],
            "lag":        data["primaryTeam"]["teamName"],
            "lag_id":     data["primaryTeam"]["teamId"],
            **stats
        }
        print(f"  [{len(alla_spelare):>3}] {data['name']} ({data['primaryTeam']['teamName']})")

        # Lägg till lagkamrater i kön
        for kid in hamta_lagkamrater(data):
            if kid not in besokta:
                att_besoka.append(kid)

    time.sleep(0.5)  # var snäll mot FotMobs servrar

# Spara
with open("fotmob_stats.json", "w", encoding="utf-8") as f:
    json.dump(list(alla_spelare.values()), f, ensure_ascii=False, indent=2)

print(f"\nKlart! {len(alla_spelare)} spelare sparade till fotmob_stats.json")

# Snabbkoll topp 5 xG
har_xg = [s for s in alla_spelare.values() if s.get("expected_goals")]
sorterad = sorted(har_xg, key=lambda x: float(x["expected_goals"]), reverse=True)
print("\nTopp 5 på xG:")
print(f"{'Namn':<25} {'Lag':<18} {'xG':<8} {'xG p90'}")
print("-" * 60)
for s in sorterad[:5]:
    print(f"{s['namn']:<25} {s['lag']:<18} {s['expected_goals']:<8} {s.get('expected_goals_p90', '-'):.3f}")