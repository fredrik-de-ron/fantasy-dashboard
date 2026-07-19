import httpx
import json

def berakna_trender(spelare_lista, fixtures, lag_dict, lag_styrka):
    """
    Beräknar hemma/borta-splits, bonusmönster och form-trender per spelare.
    Returnerar en dict med trender för spelare med tillräckligt underlag.
    """
    MIN_MATCHER = 5

    # Bygg fixture-lookup: gw -> {lag_id: {hemma, mot_lag, mot_styrka}}
    fixture_lookup = {}
    for f in fixtures:
        if not f.get("finished"):
            continue
        gw = f["event"]
        if gw not in fixture_lookup:
            fixture_lookup[gw] = {}
        fixture_lookup[gw][f["team_h"]] = {
            "hemma": True,
            "mot_lag": lag_dict.get(f["team_a"], "?"),
            "mal_for": f["team_h_score"],
            "mal_mot": f["team_a_score"],
        }
        fixture_lookup[gw][f["team_a"]] = {
            "hemma": False,
            "mot_lag": lag_dict.get(f["team_h"], "?"),
            "mal_for": f["team_a_score"],
            "mal_mot": f["team_h_score"],
        }

    # Bygg lag_id-lookup
    lag_id_dict = {v: k for k, v in lag_dict.items()}

    trender = {}

    for s in spelare_lista:
        omgangar = s.get("omgangar", [])
        if len(omgangar) < MIN_MATCHER:
            continue

        lag_id = s.get("lag_id")
        if not lag_id:
            continue

        hemma_matcher  = []
        borta_matcher  = []
        bonus_matcher  = []
        poang_per_gw   = []

        for o in omgangar:
            gw = o["omgang"]
            if gw not in fixture_lookup or lag_id not in fixture_lookup[gw]:
                continue
            fix  = fixture_lookup[gw][lag_id]
            data = {
                "gw":              gw,
                "poang":           o["poang"],
                "minuter":         o["minuter"],
                "mal":             o["mal"],
                "assist":          o["assist"],
                "offensiv_bonus":  o["offensiv_bonus"],
                "defensiv_bonus":  o["defensiv_bonus"],
                "nyckelpassningar": o["nyckelpassningar"],
                "hemma":           fix["hemma"],
                "mot_lag":         fix["mot_lag"],
            }
            poang_per_gw.append(data)
            if fix["hemma"]:
                hemma_matcher.append(data)
            else:
                borta_matcher.append(data)
            if o["offensiv_bonus"] > 0 or o["defensiv_bonus"] > 0:
                bonus_matcher.append(data)

        if len(poang_per_gw) < MIN_MATCHER:
            continue

        # Hemma/borta-split
        hemma_snitt = sum(m["poang"] for m in hemma_matcher) / len(hemma_matcher) if hemma_matcher else 0
        borta_snitt = sum(m["poang"] for m in borta_matcher) / len(borta_matcher) if borta_matcher else 0
        hemma_borta_diff = round(hemma_snitt - borta_snitt, 1)

        # Bonusfrekvens
        bonus_freq = round(len(bonus_matcher) / len(poang_per_gw) * 100, 0)

        # Form-trend (senaste 3 vs tidigare)
        senaste3   = poang_per_gw[-3:]
        tidigare   = poang_per_gw[:-3]
        senaste3_snitt  = sum(m["poang"] for m in senaste3) / len(senaste3)
        tidigare_snitt  = sum(m["poang"] for m in tidigare) / len(tidigare) if tidigare else senaste3_snitt
        form_trend = round(senaste3_snitt - tidigare_snitt, 1)

        # Flagga intressanta mönster
        flaggor = []
        n = len(poang_per_gw)

        if abs(hemma_borta_diff) >= 2.5 and len(hemma_matcher) >= 3 and len(borta_matcher) >= 3:
            riktning = "hemma" if hemma_borta_diff > 0 else "borta"
            flaggor.append({
                "typ":    "hemma_borta",
                "text":   f"Producerar {abs(hemma_borta_diff):.1f}p mer {riktning} (snitt: hemma {hemma_snitt:.1f}p, borta {borta_snitt:.1f}p)",
                "styrka": "stark" if abs(hemma_borta_diff) >= 4 else "måttlig",
                "underlag": n,
            })

        if bonus_freq >= 60:
            flaggor.append({
                "typ":    "bonus",
                "text":   f"Tar bonuspoäng i {int(bonus_freq)}% av matcherna — systematisk bonusprofil",
                "styrka": "stark" if bonus_freq >= 75 else "måttlig",
                "underlag": n,
            })

        if form_trend >= 3.0:
            flaggor.append({
                "typ":    "form_uppgång",
                "text":   f"Formuppgång: snitt {senaste3_snitt:.1f}p senaste 3 matcher vs {tidigare_snitt:.1f}p tidigare",
                "styrka": "stark" if form_trend >= 5 else "måttlig",
                "underlag": n,
            })
        elif form_trend <= -3.0:
            flaggor.append({
                "typ":    "form_nedgång",
                "text":   f"Formnedgång: snitt {senaste3_snitt:.1f}p senaste 3 matcher vs {tidigare_snitt:.1f}p tidigare",
                "styrka": "stark" if form_trend <= -5 else "måttlig",
                "underlag": n,
            })

        if flaggor:
            trender[s["namn"]] = {
                "flaggor":        flaggor,
                "hemma_snitt":    round(hemma_snitt, 1),
                "borta_snitt":    round(borta_snitt, 1),
                "bonus_freq":     bonus_freq,
                "form_trend":     form_trend,
                "antal_matcher":  n,
                "lag":            s["lag"],
                "position":       s["position"],
                "pris":           s["pris"],
                "agarskap":       s["agarskap"],
            }

    return trender


if __name__ == "__main__":
    print("Beräknar trender...")

    svar = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/")
    bootstrap = svar.json()
    lag_dict = {l["id"]: l["name"] for l in bootstrap["teams"]}

    svar2 = httpx.get("https://fantasy.allsvenskan.se/api/fixtures/")
    fixtures = svar2.json()

    with open("spelare_komplett.json", encoding="utf-8") as f:
        spelare = json.load(f)

    # Enkel styrkemodell
    lag_styrka = {l["name"]: 4.0 for l in bootstrap["teams"]}

    trender = berakna_trender(spelare, fixtures, lag_dict, lag_styrka)

    print(f"\nHittade trender för {len(trender)} spelare:\n")
    for namn, data in sorted(trender.items(), key=lambda x: -len(x[1]["flaggor"])):
        print(f"{namn} ({data['lag']}, {data['position']}, {data['pris']}M):")
        for f in data["flaggor"]:
            print(f"  [{f['styrka'].upper()}] {f['text']} (underlag: {f['underlag']} matcher)")
        print()

    with open("trend_data.json", "w", encoding="utf-8") as f:
        json.dump(trender, f, ensure_ascii=False, indent=2)
    print(f"Sparade trend_data.json")