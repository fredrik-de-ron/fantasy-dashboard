import httpx
import json

print("Hämtar grunddata...")
url1 = "https://fantasy.allsvenskan.se/api/bootstrap-static/"
data1 = httpx.get(url1).json()

lag_dict = {l["id"]: l["name"] for l in data1["teams"]}
pos_dict = {p["id"]: p["singular_name"] for p in data1["element_types"]}

# Statuskoder -> läsbar text
STATUS_TEXT = {
    "a": "Tillgänglig",
    "i": "Skadad",
    "u": "Lämnat klubben",
    "n": "Ej tillgänglig",
    "s": "Avstängd",
    "d": "Osäker",
}

spelare_dict = {}
for s in data1["elements"]:
    spelare_dict[s["id"]] = {
        "id":                      s["id"],
        "namn":                    s["web_name"],
        "fullnamn":                s["first_name"] + " " + s["second_name"],
        "lag":                     lag_dict.get(s["team"], "?"),
        "lag_id":                  s["team"],
        "position":                pos_dict.get(s["element_type"], "?"),
        # Status
        "status":                  s["status"],
        "status_text":             STATUS_TEXT.get(s["status"], s["status"]),
        "nyheter":                 s["news"],
        "chans_spela_nästa":       s["chance_of_playing_next_round"],
        "chans_spela_denna":       s["chance_of_playing_this_round"],
        # Pris
        "pris":                    s["now_cost"] / 10,
        "prisändring_omgång":      s["cost_change_event"] / 10,
        "prisändring_säsong":      s["cost_change_start"] / 10,
        "prisändring_procent":     s["price_change_percent"],
        # Ägarskap och transfers
        "agarskap":                float(s["selected_by_percent"]),
        "transfers_in_totalt":     s["transfers_in"],
        "transfers_out_totalt":    s["transfers_out"],
        "transfers_in_omgång":     s["transfers_in_event"],
        "transfers_out_omgång":    s["transfers_out_event"],
        # Form och värde
        "form":                    float(s["form"]),
        "varde_form":              float(s["value_form"]),
        "varde_säsong":            float(s["value_season"]),
        "ep_denna":                float(s["ep_this"]),
        "ep_nästa":                float(s["ep_next"]),
        # Säsongsstatistik
        "poang_total":             s["total_points"],
        "poang_per_match":         float(s["points_per_game"]),
        "poang_omgång":            s["event_points"],
        "dreamteam_count":         s["dreamteam_count"],
        "minuter":                 s["minutes"],
        "mal":                     s["goals_scored"],
        "assist":                  s["assists"],
        "gula_kort":               s["yellow_cards"],
        "roda_kort":               s["red_cards"],
        "nollor":                  s["clean_sheets"],
        "inslappta_mal":           s["goals_conceded"],
        "radningar":               s["saves"],
        "straffradningar":         s["penalties_saved"],
        "missade_straff":          s["penalties_missed"],
        "sjalvmal":                s["own_goals"],
        "avgörande_mal":           s["winning_goals"],
        "nyckelpassningar":        s["key_passes"],
        "defensiva_aktioner":      s["clearances_blocks_interceptions"],
        "offensiv_bonus":          s["attacking_bonus"],
        "defensiv_bonus":          s["defending_bonus"],
        "omgangar": []
    }

print(f"  {len(spelare_dict)} spelare inladdade")

# Visa statusöversikt
status_count = {}
for s in spelare_dict.values():
    st = s["status_text"]
    status_count[st] = status_count.get(st, 0) + 1
print("  Statusöversikt:", status_count)

print("Hämtar omgångsstatistik...")
aktuell_omgang = next(e["id"] for e in data1["events"] if e.get("is_current"))
print(f"  Aktuell omgång: {aktuell_omgang}")

for gw in range(1, aktuell_omgang + 1):
    url2 = f"https://fantasy.allsvenskan.se/api/event/{gw}/live/"
    svar = httpx.get(url2)
    if svar.status_code != 200:
        print(f"  Omgång {gw}: kunde inte hämtas")
        continue
    gw_data = svar.json()
    antal = 0
    for element in gw_data["elements"]:
        sid = element["id"]
        if sid in spelare_dict and element["stats"]["minutes"] > 0:
            st = element["stats"]
            spelare_dict[sid]["omgangar"].append({
                "omgang":              gw,
                "poang":               st["total_points"],
                "minuter":             st["minutes"],
                "mal":                 st["goals_scored"],
                "assist":              st["assists"],
                "gula_kort":           st["yellow_cards"],
                "roda_kort":           st["red_cards"],
                "nollor":              st["clean_sheets"],
                "inslappta_mal":       st["goals_conceded"],
                "radningar":           st["saves"],
                "straffradningar":     st["penalties_saved"],
                "missade_straff":      st["penalties_missed"],
                "sjalvmal":            st["own_goals"],
                "avgörande_mal":       st["winning_goals"],
                "nyckelpassningar":    st["key_passes"],
                "defensiva_aktioner":  st["clearances_blocks_interceptions"],
                "offensiv_bonus":      st["attacking_bonus"],
                "defensiv_bonus":      st["defending_bonus"],
            })
            antal += 1
    print(f"  Omgång {gw}: {antal} spelare spelade")

slutlista = list(spelare_dict.values())
with open("spelare_komplett.json", "w", encoding="utf-8") as f:
    json.dump(slutlista, f, ensure_ascii=False, indent=2)

print(f"\nKlart! {len(slutlista)} spelare sparade")

# Visa spelare som INTE är tillgängliga
print("\nSpelare som inte är tillgängliga nästa omgång:")
print(f"{'Namn':<22} {'Status':<16} {'Chans %':<10} {'Nyheter'}")
print("-" * 75)
ej_tillg = [s for s in slutlista if s["status"] != "a"]
for s in sorted(ej_tillg, key=lambda x: x["status"]):
    chans = s["chans_spela_nästa"] or 0
    nyheter = (s["nyheter"] or "")[:40]
    print(f"{s['namn']:<22} {s['status_text']:<16} {chans:<10} {nyheter}")