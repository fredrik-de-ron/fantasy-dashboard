import httpx
import json
from collections import defaultdict

print("Hämtar matchdata...")
svar = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/")
bootstrap = svar.json()

svar2 = httpx.get("https://fantasy.allsvenskan.se/api/fixtures/")
fixtures = svar2.json()

lag_dict = {l["id"]: l["name"] for l in bootstrap["teams"]}
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
print(f"Aktuell omgång: {aktuell_gw}")

# Aggregera resultat per lag per omgång
lag_form = {}
for f in fixtures:
    if not f.get("finished"):
        continue
    gw       = f["event"]
    hem_id   = f["team_h"]
    bort_id  = f["team_a"]
    hem_mal  = f["team_h_score"]
    bort_mal = f["team_a_score"]
    for lag_id, mal, inslappta, hemma in [
        (hem_id,  hem_mal,  bort_mal, True),
        (bort_id, bort_mal, hem_mal,  False),
    ]:
        if lag_id not in lag_form:
            lag_form[lag_id] = []
        lag_form[lag_id].append({
            "gw":        gw,
            "mal":       mal,
            "inslappta": inslappta,
            "hemma":     hemma,
            "vinst":     mal > inslappta,
            "oavgjort":  mal == inslappta,
            "forlust":   mal < inslappta,
        })

def styrkeindex(matcher):
    if not matcher:
        return 4.0
    senaste = sorted(matcher, key=lambda x: x["gw"])[-5:]
    poang           = sum(3 if m["vinst"] else 1 if m["oavgjort"] else 0 for m in senaste)
    mal_snitt       = sum(m["mal"] for m in senaste) / len(senaste)
    inslappta_snitt = sum(m["inslappta"] for m in senaste) / len(senaste)
    index = (poang / 15) * 4 + (mal_snitt / 3) * 1.5 - (inslappta_snitt / 3) * 1.5
    return max(1.0, min(7.0, round(index + 2, 1)))

lag_styrka = {}
for lag_id, matcher in lag_form.items():
    namn = lag_dict.get(lag_id, f"Lag {lag_id}")
    lag_styrka[namn] = styrkeindex(matcher)

print("\nLag-styrkeindex:")
for namn, styrka in sorted(lag_styrka.items(), key=lambda x: -x[1]):
    print(f"  {namn:<22} {styrka:.1f}")

# Hämta kommande 6 omgångar
kommande = [
    f for f in fixtures
    if not f.get("finished")
    and f.get("event")
   and f.get("event")
]

# Gruppera per lag per omgång — stöd för DGW (flera matcher samma omgång)
fdr_per_lag = defaultdict(lambda: defaultdict(list))

for f in kommande:
    gw        = f["event"]
    hem_id    = f["team_h"]
    bort_id   = f["team_a"]
    hem_namn  = lag_dict.get(hem_id, "?")
    bort_namn = lag_dict.get(bort_id, "?")
    mot_styrka_hem  = lag_styrka.get(bort_namn, 4.0)
    mot_styrka_bort = lag_styrka.get(hem_namn, 4.0)
    fdr_hem  = max(1, min(7, round(mot_styrka_hem  - 0.5, 1)))
    fdr_bort = max(1, min(7, round(mot_styrka_bort + 0.5, 1)))

    for namn, fdr, hemma, mot in [
        (hem_namn,  fdr_hem,  True,  bort_namn),
        (bort_namn, fdr_bort, False, hem_namn),
    ]:
        fdr_per_lag[namn][gw].append({
            "mot":   mot,
            "hemma": hemma,
            "fdr":   fdr,
        })

# Bygg slutformat — en lista per lag med omgångar
# DGW markeras med dgw=True och innehåller flera matcher
resultat = {}
for lag_namn, gw_dict in fdr_per_lag.items():
    resultat[lag_namn] = []
    for gw in sorted(gw_dict.keys()):
        matcher = gw_dict[gw]
        dgw = len(matcher) > 1
        if dgw:
            # Double Gameweek — snitt-FDR plus flagga
            snitt_fdr = round(sum(m["fdr"] for m in matcher) / len(matcher), 1)
            resultat[lag_namn].append({
                "gw":      gw,
                "dgw":     True,
                "matcher": matcher,
                "fdr":     snitt_fdr,
                "mot":     " + ".join(f"{m['mot']} ({'H' if m['hemma'] else 'B'})" for m in matcher),
                "hemma":   matcher[0]["hemma"],
            })
        else:
            m = matcher[0]
            resultat[lag_namn].append({
                "gw":    gw,
                "dgw":   False,
                "fdr":   m["fdr"],
                "mot":   m["mot"],
                "hemma": m["hemma"],
            })

with open("fdr_data.json", "w", encoding="utf-8") as f:
    json.dump(resultat, f, ensure_ascii=False, indent=2)

print(f"\nSparade FDR för {len(resultat)} lag")

# Visa DGW:s i fönstret
print("\nDouble Gameweeks i kommande omgångar:")
hittade_dgw = False
for lag_namn, matcher in resultat.items():
    for m in matcher:
        if m.get("dgw"):
            print(f"  Omgång {m['gw']}: {lag_namn} — {m['mot']}")
            hittade_dgw = True
if not hittade_dgw:
    print("  Inga DGW i kommande 6 omgångar")

nasta_gw = aktuell_gw + 1
nasta = [(n, m) for n, ml in resultat.items() for m in ml if m["gw"] == nasta_gw]
nasta.sort(key=lambda x: x[1]["fdr"])
print(f"\nFixtures omgång {nasta_gw}:")
print(f"{'Lag':<22} {'Mot':<25} {'H/B':<7} {'FDR':<6} {'DGW'}")
print("-" * 65)
for namn, m in nasta:
    hb  = "Hemma" if m["hemma"] else "Borta"
    dgw = "★ DGW" if m.get("dgw") else ""
    print(f"{namn:<22} {m['mot']:<25} {hb:<7} {m['fdr']:<6} {dgw}")