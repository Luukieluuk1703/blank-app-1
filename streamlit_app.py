import streamlit as st
import pandas as pd
import json, os, hashlib, re, random

USERS_FILE     = "users.json"
QUESTIONS_FILE = "Untitled spreadsheet.xlsx"

# ---------- BASIS-HELPERS ----------
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

# ---------- TIJDSCORE VOOR SORTEREN ----------
DAY_ORDER = {"maandag": 0, "dinsdag": 1, "woensdag": 2,
             "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}

def tijdscore(t: str) -> int:
    """Maak een numerieke sorteersleutel uit 'Maandag 2e' of 'Dag 1 uur 2'."""
    if not t:
        return 9_999
    t = t.lower().strip()

    # nieuw formaat: Dag 1 uur 2
    m = re.match(r"dag\s*(\d+)\s*uur\s*(\d+)", t)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))

    # oud formaat: Maandag 2e / 3e
    parts = t.split()
    if len(parts) >= 2:
        dag = DAY_ORDER.get(parts[0], 99)
        uur = int(re.findall(r"\d+", parts[1])[0]) if re.findall(r"\d+", parts[1]) else 99
        return dag * 100 + uur

    return 9_999

# ---------- EXCEL → VRAGEN-LIST ----------
def df_to_vragen(df: pd.DataFrame) -> list:
    vragen = []
    for _, r in df.iterrows():
        raw_type   = str(r.get("meerkeuze of fill in the blanks.", "")).lower()
        fout_raw   = str(r.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
        heeft_fout = bool(re.sub(r"[-\s]", "", fout_raw))

        vtype = "invul"  # standaard
        if "meerkeuze" in raw_type and heeft_fout:
            vtype = "meerkeuze"

        vraag = {
            "vraag"   : str(r.get("vragen.", "")).strip(),
            "antwoord": str(r.get("goed antwoord", "")).strip(),
            "type"    : vtype,
            "tijd"    : str(r.get("dag+uur (voor volgorde)", "")).strip(),
            "vak"     : str(r.get("vak.", "")).strip()
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
        st.error("❗ Spreadsheet niet gevonden in de repo.")
        return []
    return df_to_vragen(pd.read_excel(QUESTIONS_FILE))

# ---------- ANTWOORD-CHECK ----------
def _clean(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", s or "").lower()

def is_correct(user_ans: str, real_ans: str) -> bool:
    return _clean(user_ans) == _clean(real_ans)

# ---------- LOGIN / REGISTRATIE ----------
def login(users: dict):
    st.header("📚 Schoolquiz | Inloggen")
    tab_in, tab_reg = st.tabs(["Inloggen", "Registreren"])

    with tab_in:
        u = st.text_input("Gebruikersnaam", key="login_user")
        p = st.text_input("Wachtwoord", type="password", key="login_pwd")
        if st.button("Inloggen", key="login_btn"):
            if u in users and users[u]["pw"] == hash_pw(p):
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    with tab_reg:
        nu = st.text_input("Nieuwe gebruikersnaam", key="reg_user")
        pw1 = st.text_input("Wachtwoord", type="password", key="reg_pw1")
        pw2 = st.text_input("Herhaal wachtwoord", type="password", key="reg_pw2")
        if st.button("Account aanmaken", key="reg_btn"):
            if nu in users:
                st.error("Gebruiker bestaat al.")
            elif pw1 != pw2:
                st.error("Wachtwoorden komen niet overeen.")
            else:
                users[nu] = {"pw": hash_pw(pw1), "highscore": 0}
                save_users(users)
                st.success("Account aangemaakt — log nu in!")

# ---------- QUIZ LOGICA ----
def init_quiz(vragen):
    """
    Kies precies 5 vragen in rooster­volgorde:
    2 Wiskunde – 1 Geschiedenis – 2 Nederlands.
    Geen random shuffle meer: we lopen gesorteerd door de lijst.
    """
    quota   = {"math": 2, "history": 1, "nederlands": 2}
    selectie = []

    # 'vragen' staat al gesorteerd op tijdscore (zie df_to_vragen)
    for q in vragen:
        vak = q["vak"].lower().strip()
        if vak in quota and quota[vak] > 0:
            selectie.append(q)
            quota[vak] -= 1
        if sum(quota.values()) == 0:
            break

    # Controle: genoeg vragen gevonden?
    if sum(quota.values()) > 0:
        ontbrekend = ", ".join([f"{v}: {n}" for v, n in quota.items() if n > 0])
        st.error(f"Niet genoeg vragen in spreadsheet voor: {ontbrekend}")
        st.stop()

    st.session_state.vragenlijst = selectie       # rooster-volgorde
    st.session_state.idx         = 0
    st.session_state.score       = 0


def quiz(users, vragen):
    st.sidebar.write(f"👤 **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    if "vragenlijst" not in st.session_state:
        init_quiz(vragen)

    i = st.session_state.idx
    if i >= len(st.session_state.vragenlijst):
        totaal = len(st.session_state.vragenlijst)
        st.success(f"Klaar! Je score: {st.session_state.score}/{totaal}")
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
    st.subheader(f"{q['tijd']} | {q['vak']}")
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
        inp = st.text_input("Antwoord:", key=f"i{i}")
        if st.button("Bevestig", key=f"bi{i}"):
            if is_correct(inp, q["antwoord"]):
                st.success("✅ Correct")
                st.session_state.score += 1
            else:
                st.error(f"❌ Fout — correct was **{q['antwoord']}**")
            st.session_state.idx += 1
            st.rerun()

# ---------- LEADERBOARD ----------
def leaderboard(users):
    st.header("🏆 Leaderboard")
    data = sorted([(u, info.get("highscore", 0)) for u, info in users.items()],
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
        if page == "Leaderboard":
            leaderboard(users)
        else:
            quiz(users, vragen)

if __name__ == "__main__":
    main()
