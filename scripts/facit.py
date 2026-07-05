import httpx
import json
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

sys.path.insert(0, "scripts")
load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

def fraga_claude(prompt, max_tokens=2000):
    svar = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=120
    )
    data = svar.json()
    if "error" in data:
        raise Exception(data["error"])
    if "content" not in data:
        raise Exception(f"Oväntat svar: {data}")
    return "\n".join(
        block["text"] for block in data["content"]
        if block["type"] == "text"
    )

# Hämta omgångsinfo
bootstrap = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
forra_gw = aktuell_gw - 1

print(f"Facit-analys för omgång {forra_gw} (aktuell: {aktuell_gw})")

# Kolla om vi har sparade insikter för förra omgången
arkiv_fil = f"ai_historik/gw{forra_gw}.json"
if not os.path.exists(arkiv_fil):
    print(f"Inga sparade insikter för GW{forra_gw} — hoppar över facit")
    sys.exit(0)

with open(arkiv_fil, encoding="utf-8") as f:
    gamla_insikter = json.load(f)

print(f"Hittade arkiverade insikter för GW{forra_gw}")

# Hämta verkligt utfall för förra omgången
print(f"Hämtar verkligt utfall för GW{forra_gw}...")
svar = httpx.get(f"https://fantasy.allsvenskan.se/api/event/{forra_gw}/live/")
live_data = svar.json()

# Hämta spelarnamn
with open("spelare_komplett.json", encoding="utf-8") as f:
    spelare_lista = json.load(f)
spelare_dict = {s["id"]: s for s in spelare_lista}

# Bygg utfallsdata — topp 20 poängplockare
utfall = []
for element in live_data["elements"]:
    sid = element["id"]
    if sid not in spelare_dict:
        continue
    s = spelare_dict[sid]
    poang = element["stats"]["total_points"]
    minuter = element["stats"]["minutes"]
    if minuter > 0:
        utfall.append({
            "id":     sid,
            "namn":   s["namn"],
            "lag":    s["lag"],
            "poang":  poang,
            "minuter": minuter,
            "mal":    element["stats"]["goals_scored"],
            "assist": element["stats"]["assists"],
            "nollor": element["stats"]["clean_sheets"],
        })

utfall.sort(key=lambda x: x["poang"], reverse=True)
topp_poangplockare = utfall[:15]

print(f"Topp 5 poängplockare GW{forra_gw}:")
for s in topp_poangplockare[:5]:
    print(f"  {s['namn']} ({s['lag']}): {s['poang']}p")

# Generera facit med Claude
facit_prompt = f"""Du är en kvantitativ analytiker som granskar sina egna tidigare rekommendationer mot verkligt utfall.
Var ärlig, neutral och teknisk i tonen — detta är inte försvar av tidigare råd utan lärande.

OMGÅNG SOM GRANSKAS: GW{forra_gw}

TIDIGARE REKOMMENDATIONER (från vår analys innan GW{forra_gw}):

KAPTENSTIPS:
{gamla_insikter.get('kaptenstips', 'Ej tillgängligt')}

DIFFERENTIALS:
{gamla_insikter.get('differentials', 'Ej tillgängligt')}

TRANSFERANALYS:
{gamla_insikter.get('transferanalys', 'Ej tillgängligt')}

VERKLIGT UTFALL GW{forra_gw} — Topp 15 poängplockare:
{chr(10).join(f"  {i+1}. {s['namn']} ({s['lag']}): {s['poang']}p ({s['mal']} mål, {s['assist']} ast, {s['minuter']} min)" for i, s in enumerate(topp_poangplockare))}

Gör en strukturerad facit-analys:

## Kaptenstips — Träffade vi rätt?
- Hamnade någon av våra tre rekommenderade kaptener bland topp-poängplockarna?
- Om ja: vad fungerade i analysen?
- Om nej: klassificera avvikelsen (Datafel / Modellfel / Varians / Okänd okänd)

## Differentials — Levererade de?
- Hur gick det för de rekommenderade differentials-spelarna?
- Var det rätt att rekommendera dem?

## Transferanalys — Var råden korrekta?
- Hur presterade de rekommenderade KÖP-spelarna?
- Hur presterade de rekommenderade SÄLJ-spelarna? (Lägre poäng = rätt råd)

## Lärdomar (2-4 punkter)
Konkreta, handlingsbara lärdomar för kommande omgångar. Exempel:
- "Vi underskattade X faktor — vi viktar den högre framöver"
- "Kaptensrekommendationen missade pga Y — flagga liknande situationer tydligare"
- "Rekommendationen var korrekt process men dåligt utfall (varians)"

## Träffsäkerhet denna omgång
- Kaptenstips: [X av 3 bland topp-15 poängplockare]
- Differentials: [X av 3 levererade >genomsnittspoäng]
- Övergripande bedömning: [Bra/Okej/Dålig omgång för analysen]"""

print("\nGenererar facit-analys...")
facit = fraga_claude(facit_prompt, max_tokens=2000)
print("\n=== FACIT ===")
print(facit)

# Spara facit
facit_data = {
    "omgang":    forra_gw,
    "skapad":    datetime.now().isoformat(),
    "facit":     facit,
    "topp15":    topp_poangplockare,
}

os.makedirs("ai_historik", exist_ok=True)
with open(f"ai_historik/facit_gw{forra_gw}.json", "w", encoding="utf-8") as f:
    json.dump(facit_data, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade facit till ai_historik/facit_gw{forra_gw}.json")