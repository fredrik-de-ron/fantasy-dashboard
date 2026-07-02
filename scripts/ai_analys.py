import httpx
import json
import os
from dotenv import load_dotenv

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
        timeout=60
    )
    return svar.json()["content"][0]["text"]

# Ladda data
with open("dashboard_data.json", encoding="utf-8") as f:
    spelare = json.load(f)

with open("fdr_data.json", encoding="utf-8") as f:
    fdr = json.load(f)

# Hitta aktuell och nästa omgång
import httpx as hx
bootstrap = hx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
nasta_gw = aktuell_gw + 1

print(f"Analyserar omgång {nasta_gw}...")

# Filtrera bort otillgängliga spelare
tillgangliga = [s for s in spelare if s["status"] in ("a", "d") and s["chans"] >= 50 and s["minuter"] > 90]

# Bygg kompakt spelarsammanfattning för AI:n
def spelare_sammanfattning(s, max_fdr=3):
    fdr_lista = s.get("fdr", [])[:max_fdr]
    fdr_text = ", ".join(f"GW{m['gw']}:{m['fdr']}({'H' if m['hemma'] else 'B'})" for m in fdr_lista)
    return (
        f"{s['namn']} ({s['lag']}, {s['position']}, {s['pris']}M) | "
        f"Poäng/match:{s['ppg']} Form:{s['form3']} "
        f"xG:{s.get('xg') or '-'} xA:{s.get('xa') or '-'} "
        f"Äg:{s['agarskap']}% FDR: {fdr_text}"
    )

# Topp anfallare och mittfältare för kaptensanalys
anfallare_mf = [s for s in tillgangliga if s["position"] in ("Anfallare", "Mittfältare")]
anfallare_mf.sort(key=lambda x: float(x["ppg"]), reverse=True)
topp_kapten = anfallare_mf[:20]

# === KAPTENSTIPS ===
print("Genererar kaptenstips...")

kapten_prompt = f"""Du är expert på Allsvenskan Fantasy och analyserar inför omgång {nasta_gw}.

VIKTIGA REGLER FÖR KAPTENSVAL:
- Kaptenen ger dubbla poäng så välj den med högst förväntad poäng
- Prioritera: straffskyttare, hemmamatcher, låg FDR, hög form och xG
- En spelare med FDR 1-2 är mycket bättre än en med FDR 5-7
- Bonuspotential (attacking_bonus) är viktigt i Allsvenskan

Spelare att analysera (topp 20 på poäng/match):
{chr(10).join(spelare_sammanfattning(s) for s in topp_kapten)}

Ge dina topp 3 kaptensval med kortfattad motivering på svenska (max 2 meningar per spelare).
Format:
1. [Namn] - [Motivering]
2. [Namn] - [Motivering]  
3. [Namn] - [Motivering]"""

kaptenstips = fraga_claude(kapten_prompt)
print("\n=== KAPTENSTIPS ===")
print(kaptenstips)

# === DIFFERENTIALS ===
print("\nGenererar differentials...")

# Hitta spelare med lågt ägarskap men stark statistik
differentials = [s for s in tillgangliga if float(s["agarskap"]) < 15 and s.get("xg") and float(s.get("xg") or 0) > 1.5]
differentials.sort(key=lambda x: float(x.get("xg") or 0), reverse=True)

diff_prompt = f"""Du är expert på Allsvenskan Fantasy. Hitta de bästa differentials inför omgång {nasta_gw}.

En differential är en spelare som:
- Ägs av FÄRRE än 15% av lagen
- Har stark underliggande statistik (xG, xA)
- Har bra kommande matcher (låg FDR)
- Kan ge ett stort övertag mot motståndarna

Kandidater:
{chr(10).join(spelare_sammanfattning(s) for s in differentials[:15])}

Ge dina topp 3 differentials med motivering på svenska (max 2 meningar).
Format:
1. [Namn] ([Ägarskap]%) - [Motivering]
2. [Namn] ([Ägarskap]%) - [Motivering]
3. [Namn] ([Ägarskap]%) - [Motivering]"""

diff_tips = fraga_claude(diff_prompt)
print("\n=== DIFFERENTIALS ===")
print(diff_tips)

# === PRISRÖRELSER ===
print("\nAnalyserar prisrörelser...")

# Beräkna nettotransfers och prisrörelsepotential
TOTAL_MANAGERS = 57383
pris_kandidater = []
for s in spelare:
    if s["status"] not in ("a", "d"):
        continue
    netto = s["trans_in"] - s["trans_ut"]
    agare = float(s["agarskap"]) / 100 * TOTAL_MANAGERS
    if agare > 0:
        kvot = netto / agare * 100
        pris_kandidater.append({
            "namn": s["namn"],
            "lag": s["lag"],
            "position": s["position"],
            "pris": s["pris"],
            "agarskap": s["agarskap"],
            "netto": netto,
            "kvot": round(kvot, 1),
            "prisand": s["prisand"],
        })

stigande = sorted([p for p in pris_kandidater if p["kvot"] > 3], key=lambda x: -x["kvot"])[:8]
sjunkande = sorted([p for p in pris_kandidater if p["kvot"] < -4], key=lambda x: x["kvot"])[:8]

pris_prompt = f"""Du är expert på Allsvenskan Fantasy och prisrörelser.

Totalt {TOTAL_MANAGERS} managers spelar.
En spelare stiger i pris när nettoinflödet är ca 3-5% av ägarskapsbasen.
En spelare sjunker när nettoutflödet är ca -4-5% av ägarskapsbasen.

SPELARE SOM KAN STIGA I PRIS (hög nettoinköpskvot):
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) - Netto: +{p['netto']} ({p['kvot']}% av ägarbas)" for p in stigande)}

SPELARE SOM KAN SJUNKA I PRIS (hög nettoförsäljningskvot):
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) - Netto: {p['netto']} ({p['kvot']}% av ägarbas)" for p in sjunkande)}

Ge en kort analys på svenska:
1. Köp INNAN prisstegring: lista max 3 spelare
2. Sälj INNAN prissänkning: lista max 3 spelare
Motivera varje val i en mening."""

pris_tips = fraga_claude(pris_prompt)
print("\n=== PRISRÖRELSER ===")
print(pris_tips)

# Spara alla insikter
insikter = {
    "omgang": nasta_gw,
    "kaptenstips": kaptenstips,
    "differentials": diff_tips,
    "prisrorelser": pris_tips,
}

with open("ai_insikter.json", "w", encoding="utf-8") as f:
    json.dump(insikter, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade insikter till ai_insikter.json")