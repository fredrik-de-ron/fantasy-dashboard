import httpx
import json
import os
import time

def safe(v):
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except:
        return None

with open("kombinerad.json", encoding="utf-8") as f:
    kombinerad = json.load(f)

with open("fdr_data.json", encoding="utf-8") as f:
    fdr_data = json.load(f)

LAG_MAP = {
    "malmö ff":          "Malmö FF",
    "ik sirius":         "IK Sirius",
    "hammarby":          "Hammarby",
    "hammarby if":       "Hammarby",
    "djurgården":        "Djurgården",
    "ifk göteborg":      "IFK Göteborg",
    "if elfsborg":       "IF Elfsborg",
    "bk häcken":         "BK Häcken",
    "aik":               "AIK",
    "kalmar ff":         "Kalmar FF",
    "mjällby aif":       "Mjällby AIF",
    "mjällby":           "Mjällby AIF",
    "gais":              "GAIS",
    "halmstads bk":      "Halmstads BK",
    "degerfors if":      "Degerfors IF",
    "bp":                "BP",
    "if brommapojkarna": "BP",
    "västerås sk":       "Västerås SK",
    "örgryte is":        "Örgryte IS",
    "örgryte":           "Örgryte IS",
}

def hitta_fdr(lag_namn):
    normerat = lag_namn.lower().strip()
    fdr_namn = LAG_MAP.get(normerat, lag_namn)
    return fdr_data.get(fdr_namn, [])

print(f"Hämtar prishistorik för {len(kombinerad)} spelare...")

dashboard_spelare = []

for i, s in enumerate(kombinerad):
    fm = s.get("fotmob") or {}

    prishistorik = []
    try:
        url = f"https://fantasy.allsvenskan.se/api/element-summary/{s['id']}/"
        svar = httpx.get(url, timeout=10)
        if svar.status_code == 200:
            history = svar.json().get("history", [])
            for gw in history:
                prishistorik.append({
                    "gw":   gw["round"],
                    "pris": round(gw["value"] / 10, 1)
                })
    except:
        pass

    omgangar = s.get("omgangar", [])
    senaste3 = omgangar[-3:] if len(omgangar) >= 3 else omgangar
    form3 = round(sum(g["poang"] for g in senaste3) / len(senaste3), 1) if senaste3 else 0

    dashboard_spelare.append({
        "id":          s["id"],
        "namn":        s["namn"],
        "fullnamn":    s["fullnamn"],
        "lag":         s["lag"],
        "position":    s["position"],
        "status":       s["status"],
        "status_text":  s["status_text"],
        "nyheter":      s["nyheter"],
        "chans":        s["chans_spela_nästa"] or 100,
        "pris":        s["pris"],
        "prisand":     s["prisändring_omgång"],
        "agarskap":    s["agarskap"],
        "trans_in":    s["transfers_in_omgång"],
        "trans_ut":    s["transfers_out_omgång"],
        "poang":       s["poang_total"],
        "ppg":         s["poang_per_match"],
        "ep_nasta":    s["ep_nästa"],
        "form":        s["form"],
        "form3":       form3,
        "minuter":     s["minuter"],
        "mal":         s["mal"],
        "assist":      s["assist"],
        "nollor":      s["nollor"],
        "radningar":   s["radningar"],
        "xg":          safe(fm.get("expected_goals")),
        "xg_p90":      safe(fm.get("expected_goals_p90")),
        "xa":          safe(fm.get("expected_assists")),
        "xa_p90":      safe(fm.get("expected_assists_p90")),
        "skott":       safe(fm.get("shots")),
        "chanser":     safe(fm.get("chances_created")),
        "betyg":       safe(fm.get("rating")),
        "historik":    [
            {"gw": g["omgang"], "p": g["poang"], "min": g["minuter"]}
            for g in omgangar
        ],
        "prishistorik": prishistorik,
        "fdr":         hitta_fdr(s["lag"])
    })

    if (i + 1) % 50 == 0:
        print(f"  {i + 1}/{len(kombinerad)} klara...")

    time.sleep(0.1)

dashboard_spelare.sort(key=lambda x: x["poang"], reverse=True)

with open("dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(dashboard_spelare, f, ensure_ascii=False, separators=(",", ":"))

storlek = os.path.getsize("dashboard_data.json") / 1024
print(f"\nKlar! {len(dashboard_spelare)} spelare sparade")
print(f"Filstorlek: {storlek:.0f} KB")