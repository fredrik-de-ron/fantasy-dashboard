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

bootstrap = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
forra_gw = aktuell_gw - 1

print(f"Facit-analys för omgång {forra_gw} (aktuell: {aktuell_gw})")

os.makedirs("ai_historik", exist_ok=True)
arkiv_fil = f"ai_historik/gw{forra_gw}.json"
if not os.path.exists(arkiv_fil):
    print(f"Inga sparade insikter för GW{forra_gw} — hoppar över facit")
    sys.exit(0)

with open(arkiv_fil, encoding="utf-8") as f:
    gamla_insikter = json.load(f)

facit_fil = f"ai_historik/facit_gw{forra_gw}.json"
if os.path.exists(facit_fil):
    print(f"Facit för GW{forra_gw} finns redan — hoppar över")
    sys.exit(0)

print(f"Hämtar verkligt utfall för GW{forra_gw}...")
svar = httpx.get(f"https://fantasy.allsvenskan.se/api/event/{forra_gw}/live/")
live_data = svar.json()

with open("spelare_komplett.json", encoding="utf-8") as f:
    spelare_lista = json.load(f)
spelare_dict = {s["id"]: s for s in spelare_lista}

# Bygg komplett utfallsdata för ALLA spelare
namn_till_poang = {}
utfall = []
for element in live_data["elements"]:
    sid = element["id"]
    if sid not in spelare_dict:
        continue
    s = spelare_dict[sid]
    poang   = element["stats"]["total_points"]
    minuter = element["stats"]["minutes"]
    namn_till_poang[s["namn"]] = poang
    if minuter > 0:
        utfall.append({
            "id":      sid,
            "namn":    s["namn"],
            "lag":     s["lag"],
            "poang":   poang,
            "minuter": minuter,
            "mal":     element["stats"]["goals_scored"],
            "assist":  element["stats"]["assists"],
            "nollor":  element["stats"]["clean_sheets"],
        })

utfall.sort(key=lambda x: x["poang"], reverse=True)
topp15    = utfall[:15]
genomsnitt = sum(u["poang"] for u in utfall) / len(utfall) if utfall else 0

print(f"Genomsnittspoäng GW{forra_gw}: {genomsnitt:.1f}")
print(f"Topp 5:")
for s in topp15[:5]:
    print(f"  {s['namn']} ({s['lag']}): {s['poang']}p")

topp15_namn = [s["namn"] for s in topp15]
topp3_namn  = [s["namn"] for s in topp15[:3]]

# Kaptenstips
kaptenstips_spelare = gamla_insikter.get("kaptenstips_spelare", [])
kapten_treff     = sum(1 for n in kaptenstips_spelare if n in topp3_namn)
kapten_i_topp15  = [n for n in kaptenstips_spelare if n in topp15_namn]
kapten_poang     = {n: namn_till_poang.get(n, "okänd") for n in kaptenstips_spelare}

print(f"\nKaptenstips: {kaptenstips_spelare}")
print(f"  Poäng: {kapten_poang}")
print(f"  I topp 3: {[n for n in kaptenstips_spelare if n in topp3_namn]}")

# Differentials
differentials_spelare = gamla_insikter.get("differentials_spelare", [])
diff_treff   = 0
diff_detaljer = []
for namn in differentials_spelare:
    poang      = namn_till_poang.get(namn, 0)
    over_snitt = poang > genomsnitt
    if over_snitt:
        diff_treff += 1
    diff_detaljer.append(f"{namn}: {poang}p ({'✓' if over_snitt else '✗'} vs snitt {genomsnitt:.1f})")

print(f"\nDifferentials: {diff_detaljer}")

# Varningar — presterade varnade spelare dåligt? (validering)
varningar_spelare = gamla_insikter.get("varningar_spelare", [])
varning_poang = {n: namn_till_poang.get(n, "okänd") for n in varningar_spelare}
varning_under_snitt = sum(1 for n in varningar_spelare if namn_till_poang.get(n, 999) < genomsnitt)

print(f"\nVarningar: {varning_poang}")
print(f"  Under snitt: {varning_under_snitt}/{len(varningar_spelare)}")

# Uppdatera rullande träffsäkerhet
traffsakerhet_fil = "ai_historik/traffsakerhet.json"
if os.path.exists(traffsakerhet_fil):
    with open(traffsakerhet_fil, encoding="utf-8") as f:
        ts = json.load(f)
else:
    ts = {
        "antal_omgangar": 0,
        "kaptenstips":    {"treff": 0, "totalt": 0, "historia": []},
        "differentials":  {"treff": 0, "totalt": 0, "historia": []},
        "varningar":      {"treff": 0, "totalt": 0, "historia": []},
    }

ts["antal_omgangar"] += 1
ts["kaptenstips"]["treff"]  += kapten_treff
ts["kaptenstips"]["totalt"] += len(kaptenstips_spelare)
ts["kaptenstips"]["historia"].append({
    "gw": forra_gw, "treff": kapten_treff,
    "totalt": len(kaptenstips_spelare), "poang": kapten_poang
})

ts["differentials"]["treff"]  += diff_treff
ts["differentials"]["totalt"] += len(differentials_spelare)
ts["differentials"]["historia"].append({
    "gw": forra_gw, "treff": diff_treff,
    "totalt": len(differentials_spelare), "detaljer": diff_detaljer
})

if "varningar" not in ts:
    ts["varningar"] = {"treff": 0, "totalt": 0, "historia": []}
ts["varningar"]["treff"]  += varning_under_snitt
ts["varningar"]["totalt"] += len(varningar_spelare)
ts["varningar"]["historia"].append({
    "gw": forra_gw, "treff": varning_under_snitt,
    "totalt": len(varningar_spelare), "poang": varning_poang
})

with open(traffsakerhet_fil, "w", encoding="utf-8") as f:
    json.dump(ts, f, ensure_ascii=False, indent=2)

print(f"\nRullande träffsäkerhet:")
print(f"  Kaptenstips: {ts['kaptenstips']['treff']}/{ts['kaptenstips']['totalt']} i topp 3")
print(f"  Differentials: {ts['differentials']['treff']}/{ts['differentials']['totalt']} över snitt")
print(f"  Varningar: {ts['varningar']['treff']}/{ts['varningar']['totalt']} under snitt")

# Generera facit
# Bygg komplett spelarpoäng-lista för Claude
alla_relevanta = sorted(utfall, key=lambda x: x["poang"], reverse=True)
spelare_poang_text = "\n".join(
    f"  {s['namn']} ({s['lag']}): {s['poang']}p ({s['mal']} mål, {s['assist']} ast, {s['minuter']} min)"
    for s in alla_relevanta[:30]
)

facit_prompt = f"""Du är en kvantitativ analytiker som granskar sina egna rekommendationer mot verkligt utfall.
Var ärlig, neutral och teknisk — detta är lärande, inte försvar av tidigare råd.

OMGÅNG: GW{forra_gw}
GENOMSNITTSPOÄNG: {genomsnitt:.1f}p

TIDIGARE REKOMMENDATIONER:

KAPTENSTIPS (rekommenderade: {kaptenstips_spelare}):
{gamla_insikter.get('kaptenstips', 'Ej tillgängligt')}

DIFFERENTIALS (rekommenderade: {differentials_spelare}):
{gamla_insikter.get('differentials', 'Ej tillgängligt')}

SPELARVARNINGAR (varnade för: {varningar_spelare}):
{gamla_insikter.get('varningar', 'Ej tillgängligt')}

VERKLIGA POÄNG FÖR REKOMMENDERADE SPELARE:
Kaptenstips: {kapten_poang}
Differentials: {dict(zip(differentials_spelare, [namn_till_poang.get(n, 0) for n in differentials_spelare]))}
Varningar: {varning_poang}

TOPP 30 POÄNGPLOCKARE GW{forra_gw}:
{spelare_poang_text}

BERÄKNAD TRÄFFSÄKERHET:
- Kaptenstips: {kapten_treff}/{len(kaptenstips_spelare)} i topp 3
- Differentials: {diff_treff}/{len(differentials_spelare)} över snitt ({genomsnitt:.1f}p)
- Varningar: {varning_under_snitt}/{len(varningar_spelare)} under snitt (varning bekräftad)

Gör en strukturerad facit-analys på svenska:

## Kaptenstips — Träffade vi rätt?
Analysera varje rekommendation med faktiska poäng. Klassificera avvikelser:
Datafel / Modellfel / Varians / Okänd okänd

## Differentials — Levererade de?
Analysera varje differential mot genomsnittet med faktiska poäng.

## Spelarvarningar — Bekräftades varningarna?
Presterade varnade spelare under genomsnittet?

## Lärdomar (2-4 konkreta punkter)
Handlingsbara insikter för kommande omgångar.

## Träffsäkerhet denna omgång
Betyg: Bra / Okej / Dålig"""

print("\nGenererar facit-analys...")
facit = fraga_claude(facit_prompt)
print("\n=== FACIT ===")
print(facit)

facit_data = {
    "omgang":    forra_gw,
    "skapad":    datetime.now().isoformat(),
    "facit":     facit,
    "topp15":    topp15,
    "genomsnitt": round(genomsnitt, 1),
    "traffsakerhet": {
        "kaptenstips":   {"treff": kapten_treff,        "totalt": len(kaptenstips_spelare)},
        "differentials": {"treff": diff_treff,          "totalt": len(differentials_spelare)},
        "varningar":     {"treff": varning_under_snitt, "totalt": len(varningar_spelare)},
    }
}

with open(facit_fil, "w", encoding="utf-8") as f:
    json.dump(facit_data, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade facit till {facit_fil}")