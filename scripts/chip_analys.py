import httpx
import json
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, "scripts")
from straff_data import STRAFF_SKYTTARE

load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

def fraga_claude(prompt, max_tokens=4000):
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

# Ladda data
with open("dashboard_data.json", encoding="utf-8") as f:
    spelare = json.load(f)

with open("fdr_data.json", encoding="utf-8") as f:
    fdr_data = json.load(f)

# Hämta omgångsinfo
bootstrap = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
nasta_gw = aktuell_gw + 1
aterstaende_gw = 30 - aktuell_gw

print(f"Chipanalys inför omgång {nasta_gw} ({aterstaende_gw} omgångar kvar)...")

# Beräkna lag-FDR för alla kommande omgångar
lag_fdr_full = {}
for lag, matcher in fdr_data.items():
    kommande = [m for m in matcher if m["gw"] >= nasta_gw]
    if kommande:
        snitt5 = sum(m["fdr"] for m in kommande[:5]) / min(len(kommande), 5)
        dgw_gw = list(set(m["gw"] for m in kommande if m.get("dgw")))
        lag_fdr_full[lag] = {
            "snitt5":  round(snitt5, 1),
            "matcher": kommande,
            "dgw":     sorted(dgw_gw),
        }

# Hitta alla DGW-omgångar
alla_dgw = {}
for lag, info in lag_fdr_full.items():
    for gw in info["dgw"]:
        if gw not in alla_dgw:
            alla_dgw[gw] = []
        alla_dgw[gw].append(lag)

# Hitta Blank-omgångar
alla_gw_i_schema = set()
for lag, info in lag_fdr_full.items():
    for m in info["matcher"]:
        alla_gw_i_schema.add(m["gw"])

blanks = {}
for gw in sorted(alla_gw_i_schema):
    lag_utan_match = []
    for lag in lag_fdr_full.keys():
        gw_matcher = [m for m in lag_fdr_full[lag]["matcher"] if m["gw"] == gw]
        if not gw_matcher:
            lag_utan_match.append(lag)
    if lag_utan_match:
        blanks[gw] = lag_utan_match

# Tillgängliga spelare — inkludera landslagsuttagna med hög spelchans
tillgangliga = [
    s for s in spelare
    if (s["status"] in ("a", "d") or (s["status"] == "n" and s["chans"] >= 75))
    and s["chans"] >= 75
]

print(f"  Tillgängliga spelare: {len(tillgangliga)}")

# Bästa försvarare för Parkera Bussen
forsvarare = [s for s in tillgangliga if s["position"] == "Försvarare"]
forsvarare.sort(key=lambda x: (
    lag_fdr_full.get(x["lag"], {}).get("snitt5", 5),
    -float(x["nollor"])
))

# DGW-försvarare explicit
dgw_forsvarare = [
    s for s in tillgangliga
    if s["position"] == "Försvarare"
    and lag_fdr_full.get(s["lag"], {}).get("dgw")
]
dgw_forsvarare.sort(key=lambda x: float(x["ppg"]), reverse=True)

# Bästa anfallare/mittfältare för Dynamisk Duo
anfallare_mf = [s for s in tillgangliga if s["position"] in ("Anfallare", "Mittfältare")]
anfallare_mf.sort(key=lambda x: float(x["ppg"]), reverse=True)
topp_duo = anfallare_mf[:15]

def fdr_rad(lag, max_gw=6):
    matcher = lag_fdr_full.get(lag, {}).get("matcher", [])[:max_gw]
    return ", ".join(
        f"GW{m['gw']}:{m['fdr']}({'H' if m['hemma'] else 'B'}{'★' if m.get('dgw') else ''})"
        for m in matcher
    )

def dgw_detaljer(lag, gw):
    matcher = [m for m in fdr_data.get(lag, []) if m["gw"] == gw and m.get("dgw")]
    if not matcher:
        return f"{lag}: ingen data"
    snitt = sum(m["fdr"] for m in matcher) / len(matcher)
    match_text = " + ".join(
        f"vs {m['mot']} ({'H' if m['hemma'] else 'B'}) FDR:{m['fdr']}"
        for m in matcher
    )
    return f"{lag}: {match_text} (snitt FDR: {round(snitt, 1)})"

# Bygg DGW-översikt med detaljerad matchinfo
dgw_text = ""
for gw, lag_lista in sorted(alla_dgw.items()):
    dgw_text += f"\n  ★ DGW Omgång {gw}:\n"
    for lag in lag_lista:
        dgw_text += f"    {dgw_detaljer(lag, gw)}\n"
    dgw_text += f"    → Idealiskt för Parkera Bussen, Dynamisk Duo ELLER Lånelaget (välj ETT)\n"
if not dgw_text:
    dgw_text = "  Inga DGW hittade i schemat"

# Bygg Blank-översikt
blank_text = "\n".join(
    f"  ⚠ Blank Omgång {gw}: {', '.join(lag_lista)} spelar INTE"
    for gw, lag_lista in sorted(blanks.items())
    if len(lag_lista) >= 3
) if blanks else "  Inga stora Blank-omgångar hittade"

# Lag med lättast fixtures kommande 6 omgångar
lag_oversikt = "\n".join(
    f"  {lag}: snitt FDR {info['snitt5']} | {fdr_rad(lag)}"
    for lag, info in sorted(lag_fdr_full.items(), key=lambda x: x[1]["snitt5"])[:8]
)

# Försvarare för Parkera Bussen
pb_text = "  --- FÖRSVARARE FRÅN DGW-LAG (prioritera för Parkera Bussen) ---\n"
pb_text += "\n".join(
    f"  {s.get('fullnamn') or s['namn']} ({s['lag']}, {s['pris']}M) | "
    f"Nollor:{s['nollor']} PPM:{s['ppg']} | {fdr_rad(s['lag'], 4)} ★DGW"
    for s in dgw_forsvarare[:10]
)
pb_text += "\n\n  --- ÖVRIGA FÖRSVARARE MED BRA FIXTURES ---\n"
pb_text += "\n".join(
    f"  {s.get('fullnamn') or s['namn']} ({s['lag']}, {s['pris']}M) | "
    f"Nollor:{s['nollor']} PPM:{s['ppg']} | {fdr_rad(s['lag'], 4)}"
    for s in forsvarare[:8]
    if not lag_fdr_full.get(s["lag"], {}).get("dgw")
)

# Duo-kandidater
duo_text = "\n".join(
    f"  {s.get('fullnamn') or s['namn']} ({s['lag']}, {s['pris']}M) | "
    f"PPM:{s['ppg']} Form:{s['form3']} xG:{s.get('xg') or '-'} | {fdr_rad(s['lag'], 4)}"
    + (" ★DGW" if lag_fdr_full.get(s["lag"], {}).get("dgw") else "")
    for s in topp_duo
)

chip_prompt = f"""Du är expert på Allsvenskan Fantasy och chipstrategi. Analysera när och hur chipsen bör användas för resten av säsongen.

AKTUELL OMGÅNG: {aktuell_gw}
NÄSTA OMGÅNG: {nasta_gw}
ÅTERSTÅENDE OMGÅNGAR I SÄSONGEN: {aterstaende_gw} (säsongen slutar GW30)

CHIPSEN I ALLSVENSKAN FANTASY — REGLER:
⚠️ KRITISKT: BARA ETT CHIP KAN ANVÄNDAS PER OMGÅNG — inga undantag!
Parkera Bussen, Lånelaget och Dynamisk Duo kan INTE kombineras med varandra.
Inget av dessa kan heller kombineras med Frikort samma omgång.
Varje chip kan bara användas EN gång per säsong.

1. FRIKORT / WILDCARD (2 st — ett för GW2-15, ett för GW16-30)
   - Byt hela laget fritt utan transferkostnad
   - KAN EJ kombineras med Parkera Bussen, Lånelaget eller Dynamisk Duo samma omgång
   - Bäst inför en period med bra fixtures eller när laget är skadat

2. PARKERA BUSSEN (1 gång per säsong)
   - Alla försvarares poäng FÖRDUBBLAS
   - Ingen kapten eller vicekapten denna omgång
   - Optimalt med 5 försvarare i formationen (t.ex. 3-5-2)
   - KRITISKT: MAX 3 SPELARE FRÅN SAMMA LAG — du kan inte ha 5 backar från ett DGW-lag!
   - Välj 5 backar från MINST 2 OLIKA DGW-lag
   - KAN EJ kombineras med Lånelaget eller Dynamisk Duo samma omgång
   - KRAFTFULLAST VID DGW: 5 backar × 2 matcher × dubbla poäng = upp till 4x normaleffekt

3. LÅNELAGET (1 gång per säsong, GW2-30)
   - Obegränsade transfers denna omgång
   - Max 3-spelarsregeln per lag försvinner
   - Laget återställs automatiskt vid nästa deadline
   - KAN EJ avbrytas när det aktiverats
   - KAN EJ kombineras med Parkera Bussen eller Dynamisk Duo samma omgång
   - ANVÄNDNINGSFALL 1 — DGW: Ladda upp maximalt med spelare från DGW-lag
   - ANVÄNDNINGSFALL 2 — Blank-omgång: Byt tillfälligt till spelare som spelar

4. DYNAMISK DUO (1 gång per säsong)
   - Kapten får 3x poäng, vicekapten får 2x poäng
   - KAN EJ kombineras med Parkera Bussen eller Lånelaget samma omgång
   - KRAFTFULLAST VID DGW: Kapten spelar 2 matcher × 3x = enorm effekt
   - Bäst när dina två bästa spelare båda har DGW med lätta motståndare

DOUBLE GAMEWEEKS I HELA SCHEMAT:
OBS: Vid DGW är ALLA spelare från DGW-lagen värda att överväga oavsett form,
eftersom två matcher potentiellt ger dubbla poäng. Även spelare med form 3-5 PPM
kan ge 8-12 poäng i en DGW. Inkludera ALLTID spelare från ALLA DGW-lag i analysen.
{dgw_text}

BLANK GAMEWEEKS (lag som INTE spelar):
{blank_text}

LAG MED LÄTTAST FIXTURES KOMMANDE 6 OMGÅNGAR:
{lag_oversikt}

BÄSTA FÖRSVARARE FÖR PARKERA BUSSEN (★ = har DGW):
{pb_text}

KANDIDATER FÖR DYNAMISK DUO (★ = har DGW):
{duo_text}

Ge en detaljerad chipstrategi på svenska för resten av säsongen.
Tänk på att BARA ETT CHIP kan spelas per omgång.

## Frikort (Wildcard)
- Bör Frikort 1 spelas snart (löper ut GW15)?
- När bör Frikort 2 sparas till?

## Parkera Bussen
- Vilket DGW är optimalt för Parkera Bussen?
- Föreslå 5 backar från MINST 2 olika lag (max 3 från samma)
- Beräkna potentiell poängeffekt: 5 backar × 2 matcher × 2x poäng
- Inkludera backar från ALLA DGW-lag, även Mjällby AIF

## Lånelaget
- Finns det en DGW som är idealisk för Lånelaget?
- Finns det Blank-omgångar där Lånelaget kan rädda laget?
- Vilka lag bör man ladda upp med och varför?

## Dynamisk Duo
- Finns det en DGW för toppspelarna?
- Vilka två spelare maximerar effekten?
- Beräkna: kapten PPM × 3 × 2 matcher

## Prioriteringsordning
Sammanfatta chipstrategin i en tydlig tabell.
Påminn om att bara ETT chip kan spelas per omgång.
Rekommendera alltid att spara chips till DGW."""

print("Genererar chipanalys...")
chip_tips = fraga_claude(chip_prompt, max_tokens=4000)
print("\n=== CHIPANALYS ===")
print(chip_tips)

# Spara
with open("chip_insikter.json", "w", encoding="utf-8") as f:
    json.dump({
        "omgang":     nasta_gw,
        "chipanalys": chip_tips
    }, f, ensure_ascii=False, indent=2)

print("\nKlart! Sparade chip_insikter.json")