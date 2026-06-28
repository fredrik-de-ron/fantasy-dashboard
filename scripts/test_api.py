import httpx
import json

print("Hämtar all spelardata...")
url = "https://fantasy.allsvenskan.se/api/bootstrap-static/"
svar = httpx.get(url)
data = svar.json()

spelare = data["elements"]
lag = data["teams"]
positioner = data["element_types"]

lag_dict = {l["id"]: l["name"] for l in lag}
pos_dict = {p["id"]: p["singular_name"] for p in positioner}

# Bygg en ren lista med bara det vi behöver
ren_lista = []
for s in spelare:
    ren_lista.append({
        "id": s["id"],
        "namn": s["web_name"],
        "fullnamn": s["first_name"] + " " + s["second_name"],
        "lag": lag_dict.get(s["team"], "?"),
        "lag_id": s["team"],
        "position": pos_dict.get(s["element_type"], "?"),
        "pris": s["now_cost"] / 10,
        "agarskap": s["selected_by_percent"],
        "form": s["form"],
        "poang_total": s["total_points"],
        "poang_per_match": s["points_per_game"],
        "minuter": s["minutes"],
        "mal": s["goals_scored"],
        "assist": s["assists"],
        "gula_kort": s["yellow_cards"],
        "roda_kort": s["red_cards"],
        "nollor": s["clean_sheets"],
        "radningar": s["saves"],
    })

# Spara till fil
with open("spelare.json", "w", encoding="utf-8") as f:
    json.dump(ren_lista, f, ensure_ascii=False, indent=2)

print(f"Sparade {len(ren_lista)} spelare till spelare.json")
print("")

# Visa topp 5 på ägarskap
sorterad = sorted(ren_lista, key=lambda x: float(x["agarskap"]), reverse=True)
print("Topp 5 mest ägda spelare just nu:")
print(f"{'Namn':<25} {'Lag':<20} {'Pris':<8} {'Ägarskap'}")
print("-" * 65)
for s in sorterad[:5]:
    print(f"{s['namn']:<25} {s['lag']:<20} {s['pris']:<8.1f} {s['agarskap']}%")