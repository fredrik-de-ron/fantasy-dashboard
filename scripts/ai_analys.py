import httpx
import json
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, "scripts")
from straff_data import STRAFF_SKYTTARE

load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

def fraga_claude(prompt, max_tokens=3000):
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
        print(f"API-fel: {data['error']}")
        raise Exception(data["error"])
    if "content" not in data:
        print(f"Oväntat svar från API: {data}")
        raise Exception("Inget content i svaret")
    return "\n".join(
        block["text"] for block in data["content"]
        if block["type"] == "text"
    )

def extrahera_spelare(text, instruktion, max_tokens=200):
    prompt = f"""{instruktion}

TEXT ATT ANALYSERA:
{text}

Svara ENDAST med en JSON-lista med efternamn, t.ex: ["Heintz", "Botheim", "Lind"]
Inga förklaringar, ingen annan text — bara JSON-listan."""
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
        timeout=30
    )
    data = svar.json()
    text_svar = "\n".join(
        block["text"] for block in data["content"]
        if block["type"] == "text"
    )
    try:
        return json.loads(text_svar.strip())
    except:
        return []

def hitta_blanks():
    try:
        with open("fdr_data.json", encoding="utf-8") as f:
            fdr = json.load(f)
        alla_gw = set()
        for lag, matcher in fdr.items():
            for m in matcher:
                alla_gw.add(m["gw"])
        min_gw = min(alla_gw)
        max_gw = max(alla_gw)
        blanks = {}
        for lag, matcher in fdr.items():
            lag_gw = set(m["gw"] for m in matcher)
            lag_blanks = [gw for gw in range(min_gw, max_gw + 1) if gw not in lag_gw]
            if lag_blanks:
                blanks[lag] = lag_blanks
        return blanks
    except:
        return {}

BLANKS = hitta_blanks()

with open("dashboard_data.json", encoding="utf-8") as f:
    spelare = json.load(f)

with open("fdr_data.json", encoding="utf-8") as f:
    fdr = json.load(f)

bootstrap = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
nasta_gw = aktuell_gw + 1

print(f"Analyserar omgång {nasta_gw}...")
if BLANKS:
    print("Blankomgångar:")
    for lag, gw_lista in BLANKS.items():
        print(f"  {lag}: GW {gw_lista}")

# Arkivera föregående omgångs insikter
os.makedirs("ai_historik", exist_ok=True)
if os.path.exists("ai_insikter.json"):
    with open("ai_insikter.json", encoding="utf-8") as f:
        gamla = json.load(f)
    gamla_gw = gamla.get("omgang")
    if gamla_gw and gamla_gw != nasta_gw:
        arkiv_fil = f"ai_historik/gw{gamla_gw}.json"
        if not os.path.exists(arkiv_fil):
            with open(arkiv_fil, "w", encoding="utf-8") as f:
                json.dump(gamla, f, ensure_ascii=False, indent=2)
            print(f"Arkiverade GW{gamla_gw} insikter till {arkiv_fil}")

# Läs in senaste facit
lardomar = ""
if os.path.exists("ai_historik"):
    facit_filer = sorted([
        f for f in os.listdir("ai_historik")
        if f.startswith("facit_gw") and f.endswith(".json")
    ])
    if facit_filer:
        with open(f"ai_historik/{facit_filer[-1]}", encoding="utf-8") as f:
            senaste_facit = json.load(f)
        lardomar = senaste_facit.get("facit", "")
        print(f"Hittade facit från GW{senaste_facit['omgang']}")

lardomar_sektion = f"""LÄRDOMAR FRÅN FÖREGÅENDE OMGÅNG (ta hänsyn till dessa i din analys):
{lardomar}
""" if lardomar else ""

# Läs in rullande träffsäkerhet
traffsakerhet_text = ""
traffsakerhet_fil = "ai_historik/traffsakerhet.json"
if os.path.exists(traffsakerhet_fil):
    with open(traffsakerhet_fil, encoding="utf-8") as f:
        ts = json.load(f)
    kapten_treff = ts.get("kaptenstips", {})
    diff_treff   = ts.get("differentials", {})
    antal_gw     = ts.get("antal_omgangar", 0)
    if antal_gw > 0:
        traffsakerhet_text = f"""RULLANDE TRÄFFSÄKERHET (baserat på {antal_gw} omgångar):
- Kaptenstips: {kapten_treff.get('treff', 0)}/{kapten_treff.get('totalt', 0)} rekommendationer bland topp-3 poängplockare
- Differentials: {diff_treff.get('treff', 0)}/{diff_treff.get('totalt', 0)} levererade över genomsnittspoängen
Använd denna information för att kalibrera din konfidens.
"""

# Filtrera tillgängliga spelare
tillgangliga = [
    s for s in spelare
    if (s["status"] in ("a", "d") or (s["status"] == "n" and s["chans"] >= 75))
    and s["chans"] >= 75
    and s["minuter"] > 90
]

def antal_matcher(s):
    return len(s.get("historik", []))

def spelare_sammanfattning(s, max_fdr=3):
    fdr_lista = s.get("fdr", [])[:max_fdr]
    fdr_text = ", ".join(
        f"GW{m['gw']}:{m['fdr']}({'H' if m['hemma'] else 'B'})"
        for m in fdr_lista
    )
    fullnamn  = s.get("fullnamn") or s["namn"]
    efternamn = s["namn"]

    lag_info = STRAFF_SKYTTARE.get(s["lag"], {})
    fasta = []
    if efternamn in lag_info.get("straff", []):
        pos = lag_info["straff"].index(efternamn)
        fasta.append("Straffskyttare" if pos == 0 else "Reservstraffskyttare")
    if efternamn in lag_info.get("hornor", []):
        pos = lag_info["hornor"].index(efternamn)
        fasta.append("Hörnor (primär)" if pos == 0 else "Hörnor (reserv)")
    if efternamn in lag_info.get("frisparkar", []):
        pos = lag_info["frisparkar"].index(efternamn)
        if pos == 0:
            fasta.append("Frisparkar (primär)")
    fasta_text = f" | Fasta: {', '.join(fasta)}" if fasta else ""

    lag_blanks = BLANKS.get(s["lag"], [])
    blank_text = f" | ⚠ BLANK GW{lag_blanks}" if lag_blanks else ""

    n_matcher  = antal_matcher(s)
    sample_text = f" | Underlag: {n_matcher} matcher"

    return (
        f"{fullnamn} ({s['lag']}, {s['position']}, {s['pris']}M) | "
        f"Poäng/match:{s['ppg']} Form:{s['form3']} "
        f"xG:{s.get('xg') or '-'} xA:{s.get('xa') or '-'} "
        f"Äg:{s['agarskap']}%{fasta_text}{blank_text}{sample_text} FDR: {fdr_text}"
    )

blank_sammanfattning = "\n".join(
    f"  {lag}: spelar INTE GW {gw_lista}"
    for lag, gw_lista in BLANKS.items()
) if BLANKS else "  Inga blankomgångar hittade"

def agarskaps_trend(s):
    netto = s["trans_in"] - s["trans_ut"]
    if netto > 100:   return "↑ Stigande"
    elif netto < -100: return "↓ Sjunkande"
    else:              return "→ Stabil"

def kolla_stacking(spelare_lista):
    lag_count = {}
    for s in spelare_lista:
        lag_count[s["lag"]] = lag_count.get(s["lag"], 0) + 1
    return {lag: count for lag, count in lag_count.items() if count > 1}

# === KAPTENSTIPS ===
print("Genererar kaptenstips...")

anfallare_mf = [s for s in tillgangliga if s["position"] in ("Anfallare", "Mittfältare")]
anfallare_mf.sort(key=lambda x: float(x["ppg"]), reverse=True)
topp_kapten = anfallare_mf[:20]

kapten_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.

{lardomar_sektion}{traffsakerhet_text}
KONFIDENSNIVÅER:
- Stark rekommendation: bekräftad roll, stort dataunderlag (8+ matcher), samstämmiga signaler
- Rimlig rekommendation: god data men någon osäkerhetsfaktor
- Spekulativ/Bevaka: litet underlag, hög varians eller motstridiga signaler

KAPTENSKLASSIFICERING:
- Säkert kap: hög golv — säker start, säker payoff, låg varians
- Risk-kap: hög uppsida men osäker leverans
- Differential-kap: lågt ägarskap, kan ge stort övertag

BLANKOMGÅNGAR — 0 poäng dessa omgångar:
{blank_sammanfattning}
⚠ Rekommendera ALDRIG kapten från blankande lag den omgången!

Spelare att analysera (topp 20 på poäng/match):
{chr(10).join(spelare_sammanfattning(s) for s in topp_kapten)}

Ge dina topp 3 kaptensrekommendationer på svenska. För varje spelare:
1. Klassificera som Säkert kap / Risk-kap / Differential-kap
2. Ange konfidensnivå (Stark/Rimlig/Spekulativ)
3. Motivering (max 2 meningar) — inkludera fasta situationer om relevanta
4. ETT konkret motargument

Format:
1. [Namn] — [Klassificering] | Konfidens: [nivå]
   Motivering: [text]
   Motargument: [text]"""

kaptenstips = fraga_claude(kapten_prompt)
print("\n=== KAPTENSTIPS ===")
print(kaptenstips)

# === DIFFERENTIALS ===
print("\nGenererar differentials...")

differentials = [
    s for s in tillgangliga
    if float(s["agarskap"]) < 15
    and s.get("xg")
    and float(s.get("xg") or 0) > 1.5
]
differentials.sort(key=lambda x: float(x.get("xg") or 0), reverse=True)
diff_stacking = kolla_stacking(differentials[:10])

diff_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.

{lardomar_sektion}{traffsakerhet_text}
KONFIDENSNIVÅER:
- Stark: tydlig statistisk fördel, stort underlag, bra fixtures
- Rimlig: god potential men någon osäkerhetsfaktor
- Spekulativ/Bevaka: litet underlag eller hög varians

KORRELATIONSRISK:
{chr(10).join(f"  ⚠ {lag}: {count} differentials — korrelerade" for lag, count in diff_stacking.items()) if diff_stacking else "  Ingen uppenbar korrelationsrisk"}

BLANKOMGÅNGAR:
{blank_sammanfattning}

Kandidater:
{chr(10).join(spelare_sammanfattning(s) + f" | Trend: {agarskaps_trend(s)}" for s in differentials[:15])}

Ge dina topp 3 differentials på svenska. För varje spelare:
1. Konfidensnivå (Stark/Rimlig/Spekulativ)
2. Ägarskaps-trend och om spelaren bör köpas nu eller bevakas
3. Motivering (max 2 meningar)
4. ETT konkret motargument
5. Klassificering: Köp nu / Bevaka / Spekulativt kort

Format:
1. [Namn] ([Äg%], trend: [↑/↓/→]) | Konfidens: [nivå] | [Köp nu/Bevaka/Spekulativt]
   Motivering: [text]
   Motargument: [text]"""

diff_tips = fraga_claude(diff_prompt)
print("\n=== DIFFERENTIALS ===")
print(diff_tips)

# === PRISRÖRELSER ===
print("\nAnalyserar prisrörelser...")

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
            "namn":     s["namn"],
            "lag":      s["lag"],
            "position": s["position"],
            "pris":     s["pris"],
            "agarskap": s["agarskap"],
            "netto":    netto,
            "kvot":     round(kvot, 1),
            "prisand":  s["prisand"],
        })

stigande  = sorted([p for p in pris_kandidater if p["kvot"] > 3],  key=lambda x: -x["kvot"])[:8]
sjunkande = sorted([p for p in pris_kandidater if p["kvot"] < -4], key=lambda x:  x["kvot"])[:8]

pris_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.

{lardomar_sektion}
Totalt {TOTAL_MANAGERS} managers spelar.
Prisstegrings-tröskel: ~3-5% nettoinflöde av ägarskapsbasen
Prissänknings-tröskel: ~-4-5% nettoutflöde av ägarskapsbasen

TRÖSKELKÄNSLIGHET:
- 8%+: nästan säker prisrörelse
- 3-4%: känslig för daglig volym
- Ange alltid avstånd från tröskeln

FALSK SIGNAL-VARNING:
- Spike efter enskild match vs stabil trend 3+ dagar
- Flagga misstänkta spikes separat

BLANKOMGÅNGAR:
{blank_sammanfattning}

SPELARE SOM KAN STIGA I PRIS:
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) | Netto: +{p['netto']} ({p['kvot']}% av ägarbas)" for p in stigande)}

SPELARE SOM KAN SJUNKA I PRIS:
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) | Netto: {p['netto']} ({p['kvot']}% av ägarbas)" for p in sjunkande)}

## Köp INNAN prisstegring (max 3)
## Sälj INNAN prissänkning (max 3)
## Varningar"""

pris_tips = fraga_claude(pris_prompt)
print("\n=== PRISRÖRELSER ===")
print(pris_tips)

# === SPELARVARNINGAR ===
print("\nGenererar spelarvarningar...")

# Kandidater: dålig form, svåra fixtures, högt ägarskap eller blankomgång
varnings_kandidater = []
for s in tillgangliga:
    skäl = []
    if float(s["form3"]) < 3:
        skäl.append(f"Svag form ({s['form3']})")
    if s.get("fdr") and s["fdr"][0]["fdr"] >= 5:
        skäl.append(f"Svår fixture GW{s['fdr'][0]['gw']} (FDR {s['fdr'][0]['fdr']})")
    lag_blanks = BLANKS.get(s["lag"], [])
    if lag_blanks:
        skäl.append(f"Blank GW{lag_blanks}")
    if float(s["agarskap"]) > 15 and float(s["form3"]) < 4:
        skäl.append(f"Högt ägarskap ({s['agarskap']}%) trots svag form")
    if skäl:
        varnings_kandidater.append((s, skäl))

varnings_kandidater.sort(key=lambda x: (
    -float(x[0]["agarskap"]),
    float(x[0]["form3"])
))

varning_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.
Identifiera spelare som managers BÖR ÖVERVÄGA ATT SÄLJA eller vara försiktiga med.

{lardomar_sektion}
VIKTIGT: Detta är VARNINGAR — inte transferrekommendationer. Användaren gör sin egen transferanalys.
Fokus på spelare med högt ägarskap som riskerar att kosta poäng.

BLANKOMGÅNGAR:
{blank_sammanfattning}

VARNINGSKANDIDATER (sorterade efter ägarskap):
{chr(10).join(f"{s.get('fullnamn') or s['namn']} ({s['lag']}, {s['position']}, {s['pris']}M, äg:{s['agarskap']}%) | Form:{s['form3']} | Skäl: {', '.join(skal)}" for s, skal in varnings_kandidater[:12])}

Ge dina topp 5 spelarvarningar på svenska. För varje spelare:
1. Varningsnivå: 🔴 Sälj nu / 🟡 Bevaka / 🟠 Överväg att sälja
2. Konkrekt anledning (1 mening)
3. Vad som skulle ändra bedömningen (1 mening)

Format:
🔴/🟡/🟠 [Namn] ([Äg%]) — [Varningsnivå]
Anledning: [text]
Ändras om: [text]"""

varningar = fraga_claude(varning_prompt, max_tokens=2000)
print("\n=== SPELARVARNINGAR ===")
print(varningar)

# === EXTRAHERA STRUKTURERADE SPELARLISTOR ===
print("\nExtraherar strukturerade spelarlistor...")

kaptenstips_spelare = extrahera_spelare(
    kaptenstips,
    "Extrahera efternamnen på de tre rekommenderade kaptensalternativen."
)
differentials_spelare = extrahera_spelare(
    diff_tips,
    "Extrahera efternamnen på de tre rekommenderade differential-spelarna."
)
varningar_spelare = extrahera_spelare(
    varningar,
    "Extrahera efternamnen på de spelare som varnas för (max 5)."
)

print(f"  Kaptenstips: {kaptenstips_spelare}")
print(f"  Differentials: {differentials_spelare}")
print(f"  Varningar: {varningar_spelare}")

# Spara
insikter = {
    "omgang":                nasta_gw,
    "kaptenstips":           kaptenstips,
    "differentials":         diff_tips,
    "prisrorelser":          pris_tips,
    "varningar":             varningar,
    "lardomar":              lardomar,
    "kaptenstips_spelare":   kaptenstips_spelare,
    "differentials_spelare": differentials_spelare,
    "varningar_spelare":     varningar_spelare,
    "transfer_salj":         varningar_spelare,
    "transfer_kop":          [],
}

with open("ai_insikter.json", "w", encoding="utf-8") as f:
    json.dump(insikter, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade insikter till ai_insikter.json")