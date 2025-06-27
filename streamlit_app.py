import streamlit as st
import pandas as pd
import json, os, hashlib, re, random

USERS_FILE        = "users.json"
QUESTIONS_XLSX    = "Untitled spreadsheet.xlsx"

# ---------- HULPFUNCTIES ----------
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

DAY_ORDER = {"maandag": 0, "dinsdag": 1, "woensdag": 2,
             "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}

def tijdscore(txt: str) -> int:
    """Maakt sorteerbare score uit 'Dag 1 uur 2' of 'Maandag 2e'."""
    if not txt:
        return 9_999
    t = txt.lower().strip()
    m = re.match(r"dag\s*(\d+)\s*uur\s*(\d+)", t)
    if m:  # nieuw formaat
        return int(m.group(1)) * 100 + int(m.group(2))
    parts = t.split()           # oud formaat
    if len(parts) >= 2:
        dag = DAY_ORDER.get(parts[0], 99)
        uren = re.findall(r"\d+", parts[1])
        uur = int(uren[0]) if uren else 99
        return dag * 100 + uur
    return 9_999

def df_to_vragen(df: pd.DataFrame) -> list:
    vragen = []
    for _, r in df.iterrows():
        v = {
            "vraag"    : str(r.get("vragen.", "")).strip(),
            "antwoord" : str(r.get("goed antwoord", "")).strip(),
            "type"     : "invul"
                          if "fill" in str(r.get("meerkeuze of fill in the blanks.", "")).lower()
                          else "meerkeuze",
            "tijd"     : str(r.get("dag+uur (voor volgorde)", "")).strip(),
            "vak"      : str(r.get("vak.", "")).strip()
        }
        if v["type"] == "meerkeuze":
            opties = [v["antwoord"]]
            fout   = str(r.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
            if fout:
                # split op komma's, puntkomma’s of meerdere scheidingstekens
                for o in re.split(r"[;,]+", fout):
                    o = o.strip()
                    if o:
                        opties.append(o)
            random.shuffle(opties)
            v["opties"] = opties
        vragen.append(v)
    return sorted(vragen, key=lambda x: tijdscore(x["tijd"]))

def load_questions() -> list:
    if not os.path.exists(QUESTIONS_XLSX):
        st.error("Spreadsheet niet gevonden.")
        return []
    return df_to_vragen(pd.read_excel(QUESTIONS_XLSX))

# ---------- ANTWOORD-CHECK ----------
def clean_txt(s: str) -> str:
    """Verwijder alle niet-alfanumerieke tekens en maak lower-case."""
    return re.sub(r"[^a-zA-Z0-9]", "", s or "").lower()

def correct(invul: str, juist: str) -> bool:
    return clean_txt(invul) == clean_txt(juist)

# ---------- LOGIN ----------
def login(users: dict):
    st.header("📚 Schoolquiz | Inloggen")
    login_tab, reg_tab = st.tabs(["Inloggen", "Registreren"])

    with login_tab:
        u = st.text_input("Gebruikersnaam", key="login_user")
        p = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Inloggen", key="login_btn"):
            if u in users and users[u]["pw"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    with reg_tab:
        nu = st.text_input("Nieuwe gebruikersnaam", key="reg_user")
        p1 = st.text_input("Wachtwoord", type="password", key="reg_pw1")
        p2 = st.text_input("Herhaal wachtwoord", type="password", key="reg_pw2")
        if st.button("Account aanmaken", key="reg_btn"):
            if nu in users:
                st.error("Gebruiker bestaat al.")
            elif p1 != p2:
                st.error("Wachtwoorden komen niet overeen.")
            else:
                users[nu] = {"pw": hash_pw(p1), "highscore": 0}
                save_users(users)
                st.success("Account aangemaakt — log nu in!")

# ---------- QUIZ ----------# Vervangt init_quiz()
def init_quiz(vragen):
    geselecteerd = []
    vak_filter = {
        "math": 2,
        "history": 1,
        "nederlands": 2
    }

    for vak, aantal in vak_filter.items():
        subset = [v for v in vragen if v["vak"].lower().strip() == vak]
        random.shuffle(subset)
        geselecteerd.extend(subset[:aantal])

    random.shuffle(geselecteerd)  # eventueel nog herschudden
    st.session_state.vragenlijst = geselecteerd
    st.session_state.score = 0
    st.session_state.idx = 0


def quiz(users, vragen):
    st.sidebar.write(f"👤 **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    if "vragenlijst" not in st.session_state:
        init_quiz(vragen)

    i = st.session_state.idx
    if i >= len(st.session_state.vragenlijst):
        st.success(f"Eindscore : {st.session_state.score}/{len(vragen)}")
        if st.session_state.score > users[st.session_state.user].get("highscore", 0):
            users[st.session_state.user]["highscore"] = st.session_state.score
            save_users(users)
            st.balloons()
            st.toast("Nieuw persoonlijk record!", icon="🏆")
        if st.button("🔄 Opnieuw spelen"):
            init_quiz(vragen)
            st.rerun()
        return

    q = st.session_state.vragenlijst[i]
    st.subheader(f"{q['tijd']} | {q['vak']}")
    st.write(q["vraag"])

    if q["type"] == "meerkeuze":
        ans = st.radio("Antwoord:", q["opties"], key=f"m{i}")
        if st.button("Bevestig", key=f"bm{i}"):
            if ans == q["antwoord"]:
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()
    else:  # invul
        inv = st.text_input("Antwoord:", key=f"i{i}")
        if st.button("Bevestig", key=f"bi{i}"):
            if correct(inv, q["antwoord"]):
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()

# ---------- LEADERBOARD ----------
def leaderboard(users):
    st.header("🏆 Leaderboard")
    data = sorted([(u, v.get("highscore", 0)) for u, v in users.items()],
                  key=lambda x: x[1], reverse=True)
    st.table(data[:10])

# ---------- MAIN ----------
def main():
    st.set_page_config("Schoolquiz", "📘")
    users  = load_users()
    vragen = load_questions()

    if "user" not in st.session_state:
        login(users)
    else:
        page = st.sidebar.radio("Menu", ["Quiz", "Leaderboard"])
        (leaderboard if page == "Leaderboard" else quiz)(users, vragen)

if __name__ == "__main__":
    main()
