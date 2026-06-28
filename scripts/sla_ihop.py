import json
from rapidfuzz import fuzz

with open("spelare_komplett.json", encoding="utf-8") as f:
    fantasy = json.load(f)

with open("fotmob_stats.json", encoding="utf-8") as f:
    fotmob = json.load(f)

print(f"Fantasy: {len(fantasy)} spelare")
print(f"FotMob:  {len(fotmob)} spelare")

def norm(s):
    return s.lower().strip()

def efternamn(namn):
    delar = namn.strip().split()
    return norm(delar[-1]) if delar else norm(namn)

# Bygg FotMob-uppslagstabell: (efternamn, lag) -> spelare
fm_efter = {}
for s in fotmob:
    key = (efternamn(s["namn"]), norm(s["lag"]))
    fm_efter[key] = s

# Lagnamns-mappning Fantasy -> FotMob
# (eftersom lagen kan heta lite olika i de två källorna)
LAG_MAP = {
    "malmö ff":     "malmö ff",
    "ik sirius":    "sirius",
    "hammarby":     "hammarby",
    "djurgården":   "djurgården",
    "ifk göteborg": "ifk göteborg",
    "if elfsborg":  "elfsborg",
    "bk häcken":    "häcken",
    "häcken":       "häcken",
    "aik":          "aik",
    "kalmar ff":    "kalmar ff",
    "mjällby aif":  "mjällby",
    "mjällby":      "mjällby",
    "gais":         "gais",
    "halmstads bk": "halmstads bk",
    "degerfors if": "degerfors",
    "bp":           "brommapojkarna",
    "västerås sk":  "västerås sk",
    "örgryte is":   "örgryte",
    "örgryte":      "örgryte",
}

def mappa_lag(lag):
    return LAG_MAP.get(norm(lag), norm(lag))

matchade  = 0
omatchade = []
kombinerad = []

for fs in fantasy:
    fm = None

    fantasy_enr  = efternamn(fs["namn"])
    fantasy_full = norm(fs["fullnamn"])
    fantasy_lag  = mappa_lag(fs["lag"])

    # 1. Exakt matchning på efternamn + lag
    fm = fm_efter.get((fantasy_enr, fantasy_lag))

    # 2. Fuzzy matchning på fullnamn mot alla FotMob-spelare i samma lag
    if not fm:
        basta_score = 0
        for fms in fotmob:
            if mappa_lag(fms["lag"]) != fantasy_lag:
                continue
            score = fuzz.ratio(fantasy_full, norm(fms["namn"]))
            if score > basta_score:
                basta_score = score
                if score > 70:
                    fm = fms

    # 3. Fuzzy matchning på smeknamn mot alla FotMob-spelare i samma lag
    if not fm:
        basta_score = 0
        for fms in fotmob:
            if mappa_lag(fms["lag"]) != fantasy_lag:
                continue
            score = fuzz.partial_ratio(norm(fs["namn"]), norm(fms["namn"]))
            if score > basta_score:
                basta_score = score
                if score > 85:
                    fm = fms

    if fm:
        kombinerad.append({**fs, "fotmob": fm})
        matchade += 1
    else:
        kombinerad.append({**fs, "fotmob": None})
        omatchade.append(f"{fs['namn']} ({fs['lag']})")

print(f"\nMatchade:  {matchade} spelare")
print(f"Omatchade: {len(omatchade)} spelare")

if omatchade:
    print("\nFörsta 20 utan FotMob-data:")
    for namn in omatchade[:20]:
        print(f"  {namn}")

with open("kombinerad.json", "w", encoding="utf-8") as f:
    json.dump(kombinerad, f, ensure_ascii=False, indent=2)

print("\nSparat till kombinerad.json")