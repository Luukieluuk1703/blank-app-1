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

# volgorde m-ma-… voor het oude formaat
DAY_ORDER = {"maandag": 0, "dinsdag": 1, "woensdag": 2,
             "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}

def tijdscore(txt: str) -> int:
    """ Geeft een numerieke score om op te sorteren:
        Dag 1 uur 1  -> 101
        Maandag 3e  ->  3  (dag=0, uur=3)  => 3 + 1 * 100 = 103
    """
    if not txt:                 # leeg veld → helemaal achteraan
        return 9_999

    t = txt.lower().strip()

    # --- Nieuw formaat: "Dag 1 uur 2"
    m = re.match(r"dag\s*(\d+)\s*uur\s*(\d+)", t)
    if m:
        dag_num  = int(m.group(1))
        uur_num  = int(m.group(2))
        return dag_num * 100 + uur_num

    # --- Oud formaat: "maandag 2e"
    parts = t.split()
    if len(parts) >= 2:
        dag_idx   = DAY_ORDER.get(parts[0], 99)
        uur_digits= re.findall(r"\d+", parts[1])
        uur_num   = int(uur_digits[0]) if uur_digits else 99
        return dag_idx * 100 + uur_num

    return 9_999   # onbekend formaat

def df_to_vragen(df: pd.DataFrame) -> list:
    vragen = []
    for _, r in df.iterrows():
        vraag = {
            "vraag"    : str(r.get("vragen.", "")).strip(),
            "antwoord" : str(r.get("goed antwoord", "")).strip(),
            "type"     : "invul"
                          if "fill" in str(r.get("meerkeuze of fill in the blanks.", "")).lower()
                          else "meerkeuze",
            "tijd"     : str(r.get("dag+uur (voor volgorde)", "")).strip(),
            "vak"      : str(r.get("vak.", "")).strip()
        }

        if vraag["type"] == "meerkeuze":
            opties = [vraag["antwoord"]]
            fout   = str(r.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
            if fout:
                for o in fout.replace(",", ";").split(";"):
                    o = o.strip()
                    if o:
                        opties.append(o)
            random.shuffle(opties)
            vraag["opties"] = opties

        vragen.append(vraag)

    return sorted(vragen, key=lambda v: tijdscore(v["tijd"]))

def load_questions() -> list:
    if not os.path.exists(QUESTIONS_XLSX):
        st.error("Spreadsheet niet gevonden in de repo.")
        return []
    df = pd.read_excel(QUESTIONS_XLSX)
    return df_to_vragen(df)

# ---------- LOGIN ----------
def login_screen(users: dict):
    st.header("📚 Schoolquiz | Inloggen")
    tab_login, tab_reg = st.tabs(["Inloggen", "Registreren"])

    # --- inloggen
    with tab_login:
        u = st.text_input("Gebruikersnaam")
        p = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen"):
            if u in users and users[u]["pw"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    # --- registreren
    with tab_reg:
        nu = st.text_input("Nieuwe gebruikersnaam")
        p1 = st.text_input("Wachtwoord", type="password")
        p2 = st.text_input("Herhaal wachtwoord", type="password")
        if st.button("Account aanmaken"):
            if nu in users:
                st.error("Gebruiker bestaat al.")
            elif p1 != p2:
                st.error("Wachtwoorden komen niet overeen.")
            else:
                users[nu] = {"pw": hash_pw(p1), "highscore": 0}
                save_users(users)
                st.success("Account aangemaakt — log nu in!")

# ---------- QUIZ ----------
def init_quiz(vragen):
    st.session_state.vragenlijst = vragen
    st.session_state.idx   = 0
    st.session_state.score = 0

def quiz_view(users, vragen):
    st.sidebar.write(f"👤 **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    if "vragenlijst" not in st.session_state:
        init_quiz(vragen)

    idx = st.session_state.idx
    if idx >= len(st.session_state.vragenlijst):
        st.success(f"Je bent klaar! Eindscore: {st.session_state.score}/{len(vragen)}")
        if st.session_state.score > users[st.session_state.user].get("highscore", 0):
            users[st.session_state.user]["highscore"] = st.session_state.score
            save_users(users)
            st.balloons()
            st.toast("Nieuw persoonlijk record!", icon="🏆")
        if st.button("🚀 Opnieuw spelen"):
            init_quiz(vragen)
            st.rerun()
        return

    q = st.session_state.vragenlijst[idx]
    st.subheader(f"{q['tijd']} | {q['vak']}")
    st.write(q["vraag"])

    if q["type"] == "meerkeuze":
        keuze = st.radio("Antwoord:", q["opties"], key=f"k{idx}")
        if st.button("Bevestig", key=f"b{idx}"):
            if keuze == q["antwoord"]:
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()
    else:
        inv = st.text_input("Antwoord:", key=f"i{idx}")
        if st.button("Bevestig", key=f"b{idx}"):
            if inv.strip().lower() == q["antwoord"].lower():
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()

# ---------- LEADERBOARD ----------
def leaderboard(users: dict):
    st.header("🏆 Leaderboard")
    data = sorted([(u, info.get("highscore", 0)) for u, info in users.items()],
                  key=lambda x: x[1], reverse=True)
    st.table(data[:10])

# ---------- MAIN ----------
def main():
    st.set_page_config("Schoolquiz", "📘")
    users    = load_users()
    vragen   = load_questions()

    if "user" not in st.session_state:
        login_screen(users)
    else:
        page = st.sidebar.radio("Menu", ["Quiz", "Leaderboard"])
        (leaderboard if page == "Leaderboard" else quiz_view)(users, vragen)

if __name__ == "__main__":
    main()
