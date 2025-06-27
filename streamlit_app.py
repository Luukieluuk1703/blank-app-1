import streamlit as st
import pandas as pd
import json, os, hashlib, re, random

USERS_FILE = "users.json"
QUESTIONS_FILE = "Untitled spreadsheet.xlsx"

# ---- HELPERS ----
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(data: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

DAY_ORDER = {"maandag": 0, "dinsdag": 1, "woensdag": 2,
             "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}

def tijdscore(t: str) -> int:
    if not t:
        return 9999
    t = t.lower().strip()
    m = re.match(r"dag\s*(\d+)\s*uur\s*(\d+)", t)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    parts = t.split()
    if len(parts) >= 2:
        dag = DAY_ORDER.get(parts[0], 99)
        uur = int(re.findall(r"\d+", parts[1])[0]) if re.findall(r"\d+", parts[1]) else 99
        return dag * 100 + uur
    return 9999

def _clean(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", s or "").lower()

def is_correct(user_ans: str, real_ans: str) -> bool:
    return _clean(user_ans) == _clean(real_ans)

# ---- VRAGEN LADEN ----
def df_to_vragen(df: pd.DataFrame) -> list:
    vragen = []
    for _, r in df.iterrows():
        raw_type = str(r.get("meerkeuze of fill in the blanks.", "")).lower()
        fout_raw = str(r.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
        heeft_fout = bool(re.sub(r"[-\s]", "", fout_raw))

        vtype = "invul"
        if "meerkeuze" in raw_type and heeft_fout:
            vtype = "meerkeuze"

        vraag = {
            "vraag": str(r.get("vragen.", "")).strip(),
            "antwoord": str(r.get("goed antwoord", "")).strip(),
            "type": vtype,
            "tijd": str(r.get("dag+uur (voor volgorde)", "")).strip(),
            "vak": str(r.get("vak.", "")).strip()
        }

        if vtype == "meerkeuze":
            opties = [vraag["antwoord"]]
            for o in re.split(r"[;,]+", fout_raw):
                o = o.strip()
                if o:
                    opties.append(o)
            random.shuffle(opties)
            vraag["opties"] = opties

        vragen.append(vraag)

    return sorted(vragen, key=lambda v: tijdscore(v["tijd"]))

def load_questions() -> list:
    if not os.path.exists(QUESTIONS_FILE):
        st.error("❗ Spreadsheet niet gevonden.")
        return []
    return df_to_vragen(pd.read_excel(QUESTIONS_FILE))

# ---- INLOGGEN ----
def login(users: dict):
    st.header("📚 Schoolquiz | Inloggen")
    tab1, tab2 = st.tabs(["Inloggen", "Registreren"])

    with tab1:
        u = st.text_input("Gebruikersnaam", key="login_user")
        p = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Inloggen", key="login_btn"):
            if u in users and users[u]["pw"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    with tab2:
        nu = st.text_input("Nieuwe gebruikersnaam", key="reg_user")
        pw1 = st.text_input("Wachtwoord", type="password", key="reg_pw1")
        pw2 = st.text_input("Herhaal wachtwoord", type="password", key="reg_pw2")
        if st.button("Account aanmaken", key="reg_btn"):
            if nu in users:
                st.error("Gebruiker bestaat al.")
            elif pw1 != pw2:
                st.error("Wachtwoorden komen niet overeen.")
            else:
                users[nu] = {"pw": hash_pw(pw1)}
                save_users(users)
                st.success("Account aangemaakt! Log nu in.")

# ---- INIT QUIZ MET VERDELING ----
def init_quiz(vragen):
    quota = {
        "wiskunde": 2,
        "geschiedenis": 1,
        "nederlands": 2,
        "intermission": 2  # voor de pauzes
    }
    selectie = []
    rng = random.Random()

    for vak, n in quota.items():
        subset = [q for q in vragen if q["vak"].lower().strip() == vak]
        if len(subset) < n:
            st.error(f"Te weinig vragen voor {vak} (gevonden {len(subset)}, nodig {n}).")
            st.stop()
        selectie.extend(rng.sample(subset, n))

    # Voeg EIND-intermission toe (laatste vraag)
    eind_inter = [q for q in vragen if q["vak"].lower().strip() == "intermission" and q not in selectie]
    if eind_inter:
        eindvraag = rng.choice(eind_inter)
        selectie.append(eindvraag)

    selectie.sort(key=lambda q: tijdscore(q["tijd"]))
    st.session_state.vragenlijst = selectie
    st.session_state.idx = 0
    st.session_state.score = 0

# ---- QUIZ ----
def quiz(vragen):
    st.sidebar.write(f"👤 Ingelogd als **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    if "vragenlijst" not in st.session_state:
        st.title("🎬 Start je schoolquiz")
        st.write("De quiz bevat:")
        st.markdown("- 2 Wiskunde\n- 1 Geschiedenis\n- 2 Nederlands\n- 2 Intermissions\n- 1 Einde")
        if st.button("🚀 Start quiz"):
            init_quiz(vragen)
            st.rerun()
        return

    vragenlijst = st.session_state.vragenlijst
    idx = st.session_state.idx

    if idx >= len(vragenlijst):
        st.success(f"🎉 Je bent klaar! Eindscore: {st.session_state.score}/{len(vragenlijst)}")
        if st.button("🔁 Opnieuw beginnen"):
            del st.session_state.vragenlijst
            del st.session_state.idx
            del st.session_state.score
            st.rerun()
        return

    q = vragenlijst[idx]
    st.subheader(f"{q['tijd']} | {q['vak']}")
    st.write(q["vraag"])

    if q["type"] == "meerkeuze":
        ans = st.radio("Antwoord:", q["opties"], key=f"m{idx}")
        if st.button("Bevestig", key=f"bm{idx}"):
            if ans == q["antwoord"]:
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was: **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()
    else:
        inp = st.text_input("Antwoord:", key=f"i{idx}")
        if st.button("Bevestig", key=f"bi{idx}"):
            if is_correct(inp, q["antwoord"]):
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was: **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()

# ---- MAIN ----
def main():
    st.set_page_config("Schoolquiz", "📘")
    users = load_users()
    vragen = load_questions()

    if "user" not in st.session_state:
        login(users)
    else:
        quiz(vragen)

if __name__ == "__main__":
    main()
