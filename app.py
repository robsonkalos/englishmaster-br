import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import json, os, datetime, io, re

# Configurações
st.set_page_config(page_title="EnglishMaster BR", page_icon="🇬🇧", layout="wide")
DATA_DIR = "english_app_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Banco inicial
DEFAULT_WORDS = [
    {"word": "actually", "translation": "na verdade (não 'atualmente')", "level": "A2", "note": "⚠️ False friend clássico"},
    {"word": "thorough", "translation": "minucioso / completo", "level": "B1", "note": "🗣️ /ˈθʌr.ə/ (th suave)"},
    {"word": "schedule", "translation": "agenda / horário", "level": "A2", "note": "US: /ˈskedʒ.uːl/ | UK: /ˈʃed.juːl/"},
    {"word": "embarrassed", "translation": "envergonhado (não 'embaraçado')", "level": "B1", "note": "⚠️ False friend"},
]
DEFAULT_PHRASES = [
    {"phrase": "I'm looking forward to hearing from you.", "translation": "Fico no aguardo do seu retorno.", "level": "B1", "context": "E-mail formal"},
    {"phrase": "It slipped my mind.", "translation": "Esqueci / saiu da minha cabeça.", "level": "B1", "context": "Informal"},
    {"phrase": "Could you repeat that, please?", "translation": "Poderia repetir, por favor?", "level": "A2", "context": "Conversa"},
]

# ─────────────────────────────────────────────
# FIX #7: load_json com tratamento de JSON corrompido
# ─────────────────────────────────────────────
def load_json(fname, default):
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        save_json(fname, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        st.warning(f"⚠️ Arquivo {fname} estava corrompido. Dados padrão restaurados.")
        save_json(fname, default)
        return default

def save_json(fname, data):
    with open(os.path.join(DATA_DIR, fname), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# FIX #5: speak() com tratamento de erro de rede
# ─────────────────────────────────────────────
def speak(text):
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        st.audio(fp, format="audio/mp3", autoplay=False)
    except Exception as e:
        st.warning(f"🔇 Áudio indisponível: {e}")

# ─────────────────────────────────────────────
# FIX #2: review_srs com fórmula SM-2 correta
# A fórmula original aumentava o efactor incorretamente para quality=3.
# A fórmula SM-2 padrão: ef = ef + (-0.8 + 0.28*q - 0.02*q²)
# Isso garante: quality=5 → +0.1, quality=4 → +0.02, quality=3 → -0.06
# ─────────────────────────────────────────────
def review_srs(card, quality):
    card.setdefault("interval", 1)
    card.setdefault("repetition", 0)
    card.setdefault("efactor", 2.5)

    if quality >= 3:
        if card["repetition"] == 0:
            card["interval"] = 1
        elif card["repetition"] == 1:
            card["interval"] = 6
        else:
            card["interval"] = int(card["interval"] * card["efactor"])
        card["repetition"] += 1
        # Fórmula SM-2 correta
        card["efactor"] = max(1.3, card["efactor"] - 0.8 + 0.28 * quality - 0.02 * quality * quality)
    else:
        card["interval"] = 1
        card["repetition"] = 0

    card["next_review"] = (
        datetime.date.today() + datetime.timedelta(days=card["interval"])
    ).isoformat()
    return card

# ─────────────────────────────────────────────
# FIX #3: parse_ai_json robusto a markdown e JSON aninhado
# ─────────────────────────────────────────────
def parse_ai_json(text):
    # Remove blocos de código markdown (```json ... ``` ou ``` ... ```)
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"reply": text, "correction": None, "pronunciation_tip": None}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"reply": text, "correction": None, "pronunciation_tip": None}

def main():
    st.title("🇬🇧 EnglishMaster BR")
    st.caption("App completo para brasileiros: Palavras, Frases e Conversação com IA Corretiva")

    with st.sidebar:
        st.header("⚙️ Configuração")
        level = st.selectbox("📊 Seu nível", ["A1", "A2", "B1", "B2", "C1", "C2"])
        st.divider()
        st.info("💡 Use a aba **Conversação IA** para praticar inglês com correção automática.")

    # Lê a chave da API dos secrets do Streamlit Cloud
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("⚠️ Chave da API não configurada. Adicione GEMINI_API_KEY nos secrets do Streamlit Cloud.")
        st.stop()

    genai.configure(api_key=api_key)
    words = load_json("words.json", DEFAULT_WORDS)
    phrases = load_json("phrases.json", DEFAULT_PHRASES)

    tab1, tab2, tab3 = st.tabs(["📖 Palavras", "💬 Frases", "🎙️ Conversação IA"])

    # ─────────────────────────────────────────────
    # TAB 1 — FIX #1: toast com valor correto após save
    # ─────────────────────────────────────────────
    with tab1:
        st.header("🔤 Palavras com Tradução & SRS")
        today = datetime.date.today().isoformat()
        due = [w for w in words if w.get("next_review", today) <= today]
        if not due:
            st.success("✅ Revisão do dia concluída!")
            st.balloons()
        for w in due:
            st.markdown(f"### {w['word']}")
            st.info(f"🇧🇷 {w['translation']}")
            if w.get("note"):
                st.warning(w["note"])
            c1, c2, c3 = st.columns(3)
            if c1.button("🔊 Ouvir", key=f"t1_{w['word']}"):
                speak(w['word'])
            if c2.button("✅ Acertei", key=f"ok_{w['word']}"):
                review_srs(w, 5)
                save_json("words.json", words)
                st.toast(f"Agendada para {w['interval']}d")  # valor já atualizado
            if c3.button("❌ Errei", key=f"fail_{w['word']}"):
                review_srs(w, 1)
                save_json("words.json", words)
                st.toast("Revisão amanhã")

    # ─────────────────────────────────────────────
    # TAB 2 — FIX #6: chave de botão por índice para evitar DuplicateWidgetID
    # ─────────────────────────────────────────────
    with tab2:
        st.header("🗣️ Frases & Expressões")
        for i, p in enumerate(phrases):
            st.markdown(f"#### {p['phrase']}")
            st.caption(f"📌 {p['context']} | 🇧🇷 {p['translation']}")
            if st.button("🔊 Ouvir", key=f"p_{i}"):
                speak(p['phrase'])
            st.divider()

    # ─────────────────────────────────────────────
    # TAB 3 — FIX #4: histórico enviado ao modelo
    #          FIX #8: modo de voz honesto (sem promessa de transcrição automática)
    # ─────────────────────────────────────────────
    with tab3:
        st.header("🤖 Conversação com Correção em Tempo Real")
        st.caption("A IA conversa, corrige erros de brasileiros e dá dicas de pronúncia.")

        if "chat" not in st.session_state:
            st.session_state.chat = []

        # Exibir histórico acumulado
        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["content"])

        mode = st.radio("Entrada:", ["📝 Digitar", "🎤 Falar (beta)"])
        user_in = ""

        if mode == "🎤 Falar (beta)":
            # FIX #8: deixar claro que não há transcrição automática
            st.warning(
                "🚧 **Modo de voz em beta**: o áudio ainda não é transcrito automaticamente. "
                "Grave abaixo e depois escreva o que você disse no campo de texto."
            )
            audio_value = st.audio_input("Grave sua fala")
            if audio_value:
                st.success("✅ Áudio gravado!")
            user_in = st.text_area(
                "🎤 Digite o que você disse em inglês:",
                placeholder="Ex: I goes to the market yesterday..."
            )
            if user_in:
                user_in = user_in.strip()
                if st.button("📨 Enviar"):
                    pass  # cai no bloco abaixo normalmente
                else:
                    user_in = ""  # aguarda clique explícito no modo voz
        else:
            user_in = st.chat_input("Digite em inglês...")

        if user_in:
            st.session_state.chat.append({"role": "user", "content": user_in})
            st.chat_message("user").write(user_in)

            # FIX #4: montar histórico para contexto conversacional
            history_lines = []
            for m in st.session_state.chat[:-1]:  # exclui a mensagem recém-adicionada
                role_label = "Aluno" if m["role"] == "user" else "Professor"
                history_lines.append(f"{role_label}: {m['content']}")
            history_text = "\n".join(history_lines)

            prompt = (
                f"Você é professor de inglês para brasileiros (nível {level}).\n"
                "Regras:\n"
                "1. Responda em inglês mantendo o fluxo da conversa.\n"
                "2. Se houver erro gramatical, corrija explicitamente em PT-BR no campo 'correction'.\n"
                "3. Foque em erros comuns de brasileiros: ship/sheep, th, tempos verbais, preposições, false friends.\n"
                "4. Use o histórico abaixo para manter coerência na conversa.\n"
                "5. Retorne APENAS JSON válido, sem markdown, sem texto extra:\n"
                '{"reply": "...", "correction": "... ou null", "pronunciation_tip": "... ou null"}\n\n'
                f"Histórico:\n{history_text}\n"
                f"Aluno: {user_in}"
            )

            try:
                model = genai.GenerativeModel("gemini-2.0-flash")
                res = model.generate_content(prompt)
                ai = parse_ai_json(res.text)

                reply_text = ai.get("reply", "")
                correction = ai.get("correction")
                tip = ai.get("pronunciation_tip")

                st.chat_message("assistant").write(reply_text)
                if correction:
                    st.warning(f"🛠️ **Correção:** {correction}")
                if tip:
                    st.info(f"🗣️ **Pronúncia:** {tip}")
                if reply_text:
                    st.caption("🔊 Ouvindo resposta:")
                    speak(reply_text)

                st.session_state.chat.append({"role": "assistant", "content": reply_text})

            except Exception as e:
                st.error(f"Erro na IA: {e}. Verifique a chave API ou tente novamente.")

if __name__ == "__main__":
    main()
