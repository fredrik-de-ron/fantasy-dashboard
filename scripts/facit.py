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
os.makedirs("ai_historik", exist_ok=True)
arkiv_fil = f"ai_historik/gw{forra_gw}.json"
if not os.path.exists(arkiv_fil):
    print(f"Inga sparade insikter för GW{forra_gw} — hoppar över facit")
    sys.exit(0)

with open(arkiv_fil, encoding="utf-8") as f:
    gamla_insikter = json.load(f)

print(f"Hittade arkiverade insikter för GW{forra_gw}")

# Kolla om facit redan finns
facit_fil = f"ai_historik/facit_gw{forra_gw}.json"
if os.path.exists(facit_fil):
    print(f"Facit för GW{forra_gw} finns redan — hoppar över")
    sys.exit(0)

# Hämta verkligt utfall
print(f"Hämtar verkligt utfall för GW{forra_gw}...")
svar = httpx.get(f"https://fantasy.allsvenskan.se/api/event/{forra_gw}/live/")
live_data = svar.json()

with open("spelare_komplett.json", encoding="utf-8") as f:
    spelare_lista = json.load(f)
spelare_dict = {s["id"]: s for s in spelare_lista}
namn_till_poang = {s["namn"]: 0 for s in spelare_lista}

utfall = []
for element in live_data["elements"]:
    sid = element["id"]
    if sid not in spelare_dict:
        continue
    s = spelare_dict[sid]
    poang = element["stats"]["total_points"]
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
topp15 = utfall[:15]
genomsnitt = sum(u["poang"] for u in utfall) / len(utfall) if utfall else 0

print(f"Genomsnittspoäng GW{forra_gw}: {genomsnitt:.1f}")
print(f"Topp 5:")
for s in topp15[:5]:
    print(f"  {s['namn']} ({s['lag']}): {s['poang']}p")

# === BERÄKNA TRÄFFSÄKERHET ===
topp15_namn = [s["namn"] for s in topp15]
topp3_namn  = [s["namn"] for s in topp15[:3]]

# Kaptenstips — träffade vi topp 3?
kaptenstips_spelare = gamla_insikter.get("kaptenstips_spelare", [])
kapten_treff = sum(1 for namn in kaptenstips_spelare if namn in topp3_namn)
kapten_i_topp15 = [namn for namn in kaptenstips_spelare if namn in topp15_namn]

print(f"\nKaptenstips träffsäkerhet:")
print(f"  Rekommenderade: {kaptenstips_spelare}")
print(f"  I topp 3: {[n for n in kaptenstips_spelare if n in topp3_namn]}")
print(f"  I topp 15: {kapten_i_topp15}")

# Differentials — levererade de över genomsnittet?
differentials_spelare = gamla_insikter.get("differentials_spelare", [])
diff_treff = 0
diff_detaljer = []
for namn in differentials_spelare:
    poang = namn_till_poang.get(namn, 0)
    over_snitt = poang > genomsnitt
    if over_snitt:
        diff_treff += 1
    diff_detaljer.append(f"{namn}: {poang}p ({'✓' if over_snitt else '✗'} vs snitt {genomsnitt:.1f})")

print(f"\nDifferentials träffsäkerhet:")
for d in diff_detaljer:
    print(f"  {d}")

# Transferanalys — presterade KÖP bättre än SÄLJ?
transfer_kop  = gamla_insikter.get("transfer_kop", [])
transfer_salj = gamla_insikter.get("transfer_salj", [])
kop_poang  = [namn_till_poang.get(n, 0) for n in transfer_kop]
salj_poang = [namn_till_poang.get(n, 0) for n in transfer_salj]
kop_snitt  = sum(kop_poang) / len(kop_poang)   if kop_poang  else 0
salj_snitt = sum(salj_poang) / len(salj_poang) if salj_poang else 0
transfer_treff = kop_snitt > salj_snitt

print(f"\nTransferanalys träffsäkerhet:")
print(f"  KÖP-spelare: {list(zip(transfer_kop, kop_poang))} (snitt: {kop_snitt:.1f}p)")
print(f"  SÄLJ-spelare: {list(zip(transfer_salj, salj_poang))} (snitt: {salj_snitt:.1f}p)")
print(f"  KÖP > SÄLJ: {'✓' if transfer_treff else '✗'}")

# === UPPDATERA RULLANDE TRÄFFSÄKERHET ===
traffsakerhet_fil = "ai_historik/traffsakerhet.json"
if os.path.exists(traffsakerhet_fil):
    with open(traffsakerhet_fil, encoding="utf-8") as f:
        ts = json.load(f)
else:
    ts = {
        "antal_omgangar": 0,
        "kaptenstips":    {"treff": 0, "totalt": 0, "historia": []},
        "differentials":  {"treff": 0, "totalt": 0, "historia": []},
        "transferanalys": {"treff": 0, "totalt": 0, "historia": []},
    }

ts["antal_omgangar"] += 1
ts["kaptenstips"]["treff"]   += kapten_treff
ts["kaptenstips"]["totalt"]  += len(kaptenstips_spelare)
ts["kaptenstips"]["historia"].append({
    "gw": forra_gw, "treff": kapten_treff,
    "totalt": len(kaptenstips_spelare), "spelare": kaptenstips_spelare
})

ts["differentials"]["treff"]   += diff_treff
ts["differentials"]["totalt"]  += len(differentials_spelare)
ts["differentials"]["historia"].append({
    "gw": forra_gw, "treff": diff_treff,
    "totalt": len(differentials_spelare), "detaljer": diff_detaljer
})

ts["transferanalys"]["treff"]   += 1 if transfer_treff else 0
ts["transferanalys"]["totalt"]  += 1
ts["transferanalys"]["historia"].append({
    "gw": forra_gw, "treff": transfer_treff,
    "kop_snitt": round(kop_snitt, 1), "salj_snitt": round(salj_snitt, 1)
})

with open(traffsakerhet_fil, "w", encoding="utf-8") as f:
    json.dump(ts, f, ensure_ascii=False, indent=2)

print(f"\nRullande träffsäkerhet uppdaterad:")
print(f"  Kaptenstips: {ts['kaptenstips']['treff']}/{ts['kaptenstips']['totalt']} i topp 3")
print(f"  Differentials: {ts['differentials']['treff']}/{ts['differentials']['totalt']} över snitt")
print(f"  Transferanalys: {ts['transferanalys']['treff']}/{ts['transferanalys']['totalt']} KÖP > SÄLJ")

# === GENERERA FACIT MED CLAUDE ===
facit_prompt = f"""Du är en kvantitativ analytiker som granskar sina egna tidigare rekommendationer mot verkligt utfall.
Var ärlig, neutral och teknisk — detta är lärande, inte försvar av tidigare råd.

OMGÅNG SOM GRANSKAS: GW{forra_gw}
GENOMSNITTSPOÄNG DENNA OMGÅNG: {genomsnitt:.1f}p

TIDIGARE REKOMMENDATIONER:

KAPTENSTIPS (rekommenderade: {kaptenstips_spelare}):
{gamla_insikter.get('kaptenstips', 'Ej tillgängligt')}

DIFFERENTIALS (rekommenderade: {differentials_spelare}):
{gamla_insikter.get('differentials', 'Ej tillgängligt')}

TRANSFERANALYS:
KÖP-spelare: {list(zip(transfer_kop, kop_poang))}
SÄLJ-spelare: {list(zip(transfer_salj, salj_poang))}

VERKLIGT UTFALL — Topp 15 poängplockare GW{forra_gw}:
{chr(10).join(f"  {i+1}. {s['namn']} ({s['lag']}): {s['poang']}p ({s['mal']} mål, {s['assist']} ast)" for i, s in enumerate(topp15))}

BERÄKNAD TRÄFFSÄKERHET:
- Kaptenstips: {kapten_treff} av {len(kaptenstips_spelare)} rekommendationer i topp 3
- Differentials: {diff_treff} av {len(differentials_spelare)} levererade över genomsnittet ({genomsnitt:.1f}p)
- Transferanalys: KÖP-snitt {kop_snitt:.1f}p vs SÄLJ-snitt {salj_snitt:.1f}p ({'✓ KÖP vann' if transfer_treff else '✗ SÄLJ vann'})

Gör en strukturerad facit-analys på svenska:

## Kaptenstips — Träffade vi rätt?
Analysera varje rekommendation mot utfallet. Klassificera avvikelser:
- Datafel: informationen var fel/inaktuell
- Modellfel: informationen korrekt men vägdes fel
- Varians: rimlig rekommendation men dåligt utfall (otur)
- Okänd okänd: oförutsägbar händelse

## Differentials — Levererade de?
Analysera varje differential mot genomsnittet.

## Transferanalys — Var råden korrekta?
Presterade KÖP bättre än SÄLJ?

## Lärdomar (2-4 konkreta punkter)
Handlingsbara insikter för kommande omgångar.

## Träffsäkerhet denna omgång
Kort sammanfattning med betyg: Bra / Okej / Dålig"""

print("\nGenererar facit-analys...")
facit = fraga_claude(facit_prompt)
print("\n=== FACIT ===")
print(facit)

# Spara facit
facit_data = {
    "omgang":          forra_gw,
    "skapad":          datetime.now().isoformat(),
    "facit":           facit,
    "topp15":          topp15,
    "genomsnitt":      round(genomsnitt, 1),
    "traffsakerhet": {
        "kaptenstips":    {"treff": kapten_treff, "totalt": len(kaptenstips_spelare)},
        "differentials":  {"treff": diff_treff, "totalt": len(differentials_spelare)},
        "transferanalys": {"treff": 1 if transfer_treff else 0, "totalt": 1},
    }
}

with open(facit_fil, "w", encoding="utf-8") as f:
    json.dump(facit_data, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade facit till {facit_fil}")