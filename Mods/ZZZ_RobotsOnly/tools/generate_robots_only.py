import xml.etree.ElementTree as ET
import re, random, sys

BASE = "/home/mcarpenter/.local/share/Steam/steamapps/common/7 Days To Die"
OUT = f"{BASE}/Mods/ZZZ_RobotsOnly"

# ---------- 1. replay vanilla + DZ merges (same logic as simulation) ----------
def entries_from_elem(elem):
    out = []
    for child in elem:
        if child.tag == "e" and child.get("n"): out.append(child.get("n"))
        elif child.tag == "entity" and child.get("name"): out.append(child.get("name"))
    if elem.text:
        for m in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(,|\r?$)", elem.text.replace('\r',''), re.M):
            out.append(m.group(1))
    return out

van = ET.parse(f"{BASE}/Data/Config/entitygroups.xml").getroot()
groups, order = {}, []
for g in van.findall("entitygroup"):
    groups[g.get("name")] = entries_from_elem(g); order.append(g.get("name"))

# --- A_ZombieHordesPurge runs BEFORE District Zero ---
PURGE_PREFIXES = ("FwanderingHordeStage",)
for n in [n for n in order if n.startswith(PURGE_PREFIXES)]:
    del groups[n]; order.remove(n)

dz = ET.parse(f"{BASE}/Mods/District Zero/Config/entitygroups.xml").getroot()
def gname(xp):
    m = re.search(r"@name='([^']+)'", xp); return m.group(1) if m else None

for node in dz:
    xp = node.get("xpath","")
    if node.tag == "remove":
        if "@name=" in xp and "starts-with" not in xp:
            n = gname(xp)
            if n in groups: del groups[n]; order.remove(n)
        elif "starts-with(@name," in xp:
            pref = re.search(r"starts-with\(@name,'([^']+)'\)", xp).group(1)
            for n in [n for n in order if n.startswith(pref)]:
                del groups[n]; order.remove(n)
        elif "starts-with(@n," in xp:
            pref = re.search(r"starts-with\(@n,'([^']+)'\)", xp).group(1)
            for n in order:
                groups[n] = [e for e in groups[n] if not e.startswith(pref)]
    elif node.tag == "append" and xp.strip() == "/entitygroups":
        for g in node.findall("entitygroup"):
            n = g.get("name"); ents = entries_from_elem(g)
            if n not in groups: order.append(n)
            groups.setdefault(n, []).extend(ents)
    elif node.tag == "append" and "starts-with(@name," in xp:
        pref = re.search(r"starts-with\(@name,'([^']+)'\)", xp).group(1)
        ents = [c.get("n") or c.get("name") for c in node if c.get("n") or c.get("name")]
        for n in [n for n in order if n.startswith(pref)]:
            groups[n].extend(ents)
    elif node.tag in ("append","set"):
        n = gname(xp)
        if n is None: continue
        ents = entries_from_elem(node)
        if node.tag == "append":
            groups.setdefault(n, []).extend(ents)
            if n not in order: order.append(n)
        else:
            groups[n] = ents

# ---------- 2. find groups emptied by the zombie strip ----------
zr = re.compile(r"^zombie")
emptied = {}
for n in order:
    removed = [e for e in groups[n] if zr.match(e)]
    kept    = [e for e in groups[n] if not zr.match(e)]
    if removed and not kept:
        emptied[n] = len(removed)

# ---------- 3. replacement roster ----------
# All names verified present in DZ's own entitygroups.xml (i.e. guaranteed valid)
bases = ["robotAndroidBolt","robotAndroidClank","robotAndroidEva","robotAndroidRalph",
         "robotAndroidAxl","robotAndroidOrion","robotAndroidChronos","robotAndroidRex",
         "robotCyborgSpark","robotCyborgNova","robotAndroidPrime","robotAndroidAndromeda",
         "robotCyborgTitan"]  # index = rough tier 0..12
MODS = {"": "", "Feral": "Overcharged", "Charged": "Shocker",
        "Radiated": "Radiated", "Infernal": "Inferno"}
SPECIALS = {"robotDroneNano","robotDronePoliceNano","robotDroneSecurity","robotDronePolice",
            "robotSpiderBot","robotSpiderBotNano","robotDroidBomber","robotDroidCombat",
            "robotDroidSoldier","robotCombatDog"}

valid = set()
txt_dz = open(f"{BASE}/Mods/District Zero/Config/entitygroups.xml").read()
txt_van = open(f"{BASE}/Data/Config/entitygroups.xml").read()
valid |= set(re.findall(r'(?:n|name)="(robot[A-Za-z]+)"', txt_dz))
valid |= set(re.findall(r'^\s*(robot[A-Za-z]+)\s*,', txt_dz, re.M))

def gs_tier(n):
    m = re.search(r"GS(\d+)", n)
    if not m: return None
    gs = int(m.group(1))
    T = [(20,0),(50,1),(100,2),(200,3),(350,4),(600,5),(900,6),(1300,7),(2600,8)]
    for lim,t in T:
        if gs <= lim: return t
    return 9

def pick(rng, lo, hi, k):
    return [rng.choice(bases[lo:hi+1]) for _ in range(k)]

def make(name, removed_count):
    rng = random.Random(name)  # deterministic per group
    low = name.lower()
    # --- special themes ---
    if "scout" in low or "screamer" in low:
        pool = ["robotDroneNano","robotDronePoliceNano"]
        suf = next((s for s in MODS if s and name.endswith(s)), "")
        return sorted({p for p in pool}) if not suf else [pool[0]]
    if "spider" in low: return ["robotSpiderBot"]
    if "crawler" in low or any("Crawler" in e for e in [name]): return ["robotSpiderBotNano"]
    if "demolition" in low: return ["robotDroidBomber"]
    if "wight" in low: return ["robotCyborgNova"]
    if "frostclaw" in low: return ["robotCyborgSpark"]
    if "boss" in low: return ["robotCyborgTitanOvercharged","robotAndroidPrimeInferno"]
    if "specialinfected" in low:
        return ["robotCyborgNova","robotSpiderBot","robotDroidBomber","robotCyborgTitan"]

    suf = next((s for s in ("Infernal","Radiated","Charged","Feral") if name.endswith(s)), "")

    # --- gamestage-scaled tables ---
    t = gs_tier(name)
    if t is not None:
        lo, hi = max(0,t-1), min(12,t+1)
        k = max(3, min(removed_count, 10))
        out = []
        for b in pick(rng, lo, hi, k):
            m = MODS[suf] if (suf and rng.random() < 0.45) else ""
            out.append(b+m if m and b+m in valid else b)
        return list(dict.fromkeys(out)) or [bases[t]]

    # --- single-entity gamestage pools & un-scaled POI groups ---
    if removed_count <= 1 and name[0].islower():
        band = {"": (0,4), "Feral": (1,6), "Charged": (2,6),
                "Radiated": (2,6), "Infernal": (3,8)}[suf]
        b = rng.choice(bases[band[0]:band[1]])
        m = MODS[suf]
        return [b+m if m and b+m in valid else b]

    lo, hi = (1,5) if suf=="" else (2,8)
    k = max(3, min(removed_count, 8))
    out = []
    for b in pick(rng, lo, hi, k):
        m = MODS[suf] if (suf and rng.random() < 0.4) else ""
        out.append(b+m if m and b+m in valid else b)
    return list(dict.fromkeys(out))

# ---------- 4. emit mod ----------
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
 '<!-- ZZZ_RobotsOnly: strips ALL humanoid zombies from entity spawn groups',
 '     and backfills emptied groups with District Zero robots.',
 '     Load order: last (folder name prefix ZZZ). Animals are untouched. -->',
 '<config>',
 '',
 '  <!-- global strip of every zombie entry, whatever format the group uses',
 '       (single-node mixed groups keep their robot entries this way) -->',
 '  <remove xpath="//entitygroup/e[starts-with(@n,\'zombie\')]"/>',
 '  <remove xpath="//entitygroup/entity[starts-with(@name,\'zombie\')]"/>',
 '',
 '  <!-- refill groups whose entire content was zombies -->']
bad = []
for n in sorted(emptied):
    # prefer real merged content minus zombies; fall back to generated
    ents = [e for e in dict.fromkeys(groups[n]) if not zr.match(e)]
    if not ents:
        ents = make(n, emptied.get(n, 4))
    for e in ents:
        if e not in valid:
            bad.append((n,e))
    lines.append(f"  <set xpath=\"//entitygroup[@name='{n}']\">")
    for e in ents:
        lines.append(f"\t\t{e}, 1")
    lines.append("  </set>")
lines += ["", "</config>"]

if bad:
    print("INVALID NAMES:", bad); sys.exit(1)

# ---------- 5. missing sleeper groups referenced by POI prefabs ----------
# MPLogue (and other) prefabs reference legacy A16-era group names that no
# longer exist in V1.0/DZ entitygroups. Define them as robot groups.
MISSING_GROUPS = {
    "GroupGenericZombie":    ["robotAndroidBolt","robotAndroidClank","robotAndroidEva","robotAndroidRalph","robotAndroidAxl"],
    "S_-Group_Generic_Zombie":["robotAndroidClank","robotAndroidEva"],
    "GroupAbandonedHouse":   ["robotAndroidEva","robotAndroidRalph","robotAndroidClank"],
    "GroupGhostTown":        ["robotAndroidRalph","robotAndroidAxl","robotCyborgSpark"],
    "GroupBikerBar":         ["robotAndroidAxl","robotAndroidOrion","robotAndroidChronos"],
    "GroupZomSoldier":       ["robotAndroidOrion","robotAndroidChronos","robotAndroidRex","robotDroidSoldier"],
    "GroupZomBadass":        ["robotAndroidChronos","robotAndroidRex","robotCyborgNova","robotAndroidPrime"],
    "GroupZomBadassOnly":    ["robotAndroidPrime","robotAndroidAndromeda","robotCyborgTitan"],
    "ZomFatCops":            ["robotDroidCombat","robotDroidSoldier"],
    "ZomBurnt":              ["robotCyborgSpark","robotAndroidRex"],
    "ZomBusinessman":        ["robotAndroidAxl","robotAndroidOrion"],
    "ZomHazMatOnly":         ["robotAndroidChronos","robotCyborgNova"],
    "ZomJanitorOnly":        ["robotAndroidClank","robotAndroidEva"],
    "ZomLumberJack":         ["robotAndroidRalph","robotAndroidAxl"],
    "ZomSnow":               ["robotMechLightBiped","robotAndroidOrion"],
    "ZomSpiderOnly":         ["robotSpiderBot","robotSpiderBotNano"],
    "ZomUtilityWorker":      ["robotAndroidEva","robotAndroidOrion","robotDroidCombat"],
    "GroupHospital":         ["robotCyborgNova","robotAndroidAndromeda","robotAndroidPrime"],
    "GroupNightClub":        ["robotDroneNano","robotAndroidAxl","robotAndroidAndromeda"],
    "GroupLabWorker":        ["robotCyborgSpark","robotAndroidClank","robotAndroidChronos"],
    "GroupSpecialInfected":  ["robotSpiderBot","robotDroidBomber","robotCyborgTitan","robotCyborgNova"],
    "GroupTestChamberDecoy": ["robotSpiderBotNano","robotDronePoliceNano"],
}

extra = ["",
 '  <!-- legacy A16-era sleeper groups referenced by POI prefabs but missing'
 '\n       from V1.0/DZ entitygroups -->',
 '  <append xpath="/entitygroups">']
for n, ents in MISSING_GROUPS.items():
    for e in ents:
        if e not in valid:
            print("INVALID NAME in MISSING_GROUPS:", e); sys.exit(1)
    extra.append(f'\t<entitygroup name="{n}">')
    extra += [f"\t\t{e}, 1" for e in ents]
    extra.append("\t</entitygroup>")
extra += ["  </append>"]

lines = lines[:-1] + extra + ["</config>"]

import os
os.makedirs(f"{OUT}/Config", exist_ok=True)
open(f"{OUT}/Config/entitygroups.xml","w").write("\n".join(lines)+"\n")
open(f"{OUT}/ModInfo.xml","w").write("""<?xml version="1.0" encoding="UTF-8"?>
<xml>
\t<Name value="ZZZ_RobotsOnly" />
\t<DisplayName value="Robots Only (District Zero addon)" />
\t<Version value="1.0.0" />
\t<Description value="Removes all humanoid zombies from spawning; District Zero robots only. Loads last." />
\t<Author value="local" />
</xml>
""")
print(f"wrote {len(emptied)} set-blocks; {len(lines)} lines total")
