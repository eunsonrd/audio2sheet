
import streamlit as st
import whisper
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
from fpdf import FPDF
import os
import tempfile

# Page setup
st.set_page_config(page_title="Audio2Sheet", page_icon="🎵")
st.title("🎵 Audio2Sheet: Lyrics & Melody PDF")
st.write("Upload an MP3 → Edit lyrics → Download your PDF!")

# Load AI model
@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

model = load_whisper()

# ─────────── HELPER FUNCTIONS ───────────
def split_lines(text):
    import re
    lines = re.split(r'([.,;:!?])', text)
    result, current = [], ""
    for part in lines:
        if part in ".!,;:?":
            if current.strip():
                result.append((current + part).strip())
            current = ""
        else:
            current = part
    if current.strip():
        result.append(current.strip())
    return "\n".join(result)

def add_verses(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for i, line in enumerate(lines, 1):
        out.append(f"[Verse {i}]")
        out.append(line)
    return "\n".join(out)

def add_chorus(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for line in lines:
        out.append("[Chorus]")
        out.append(line)
    return "\n".join(out)

# Convert note events to simple note names list
def notes_to_text(note_events):
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    lines = []
    line = ""
    count = 0
    for note in note_events:
        _, _, pitch, conf, _ = note
        if conf > 0.4:
            name = note_names[pitch % 12]
            octave = (pitch // 12) - 1
            line += f"{name}{octave}  "
            count += 1
            if count >= 8:
                lines.append(line)
                line = ""
                count = 0
    if line:
        lines.append(line)
    return "\n".join(lines)

# ─────────── UPLOAD ───────────
audio_file = st.file_uploader("Upload your MP3", type=["mp3"])

if audio_file:
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    st.audio(tmp_path)

    # Step 1: Transcribe lyrics
    with st.spinner("🔄 Transcribing lyrics..."):
        result = model.transcribe(tmp_path)
        raw_lyrics = result["text"].strip()

    # Step 2: Lyrics editor with tools
    st.subheader("📝 Edit Your Lyrics")
    c1, c2, c3, c4 = st.columns(4)
    with c1: do_split = st.button("📏 Split Lines")
    with c2: do_verse = st.button("📖 Add Verses")
    with c3: do_chorus = st.button("🎤 Add Chorus")
    with c4: do_clean = st.button("🧹 Clean")

    if "lyrics" not in st.session_state:
        st.session_state.lyrics = raw_lyrics

    if do_split:
        st.session_state.lyrics = split_lines(st.session_state.lyrics)
    if do_verse:
        st.session_state.lyrics = add_verses(st.session_state.lyrics)
    if do_chorus:
        st.session_state.lyrics = add_chorus(st.session_state.lyrics)
    if do_clean:
        st.session_state.lyrics = "\n".join(
            [l.strip() for l in st.session_state.lyrics.splitlines() if l.strip()]
        )

    lyrics_out = st.text_area(
        "✏️ Edit freely below:",
        value=st.session_state.lyrics,
        height=200,
        key="lyrics"
    )

    # Step 3: Extract melody
    st.subheader("🎼 Melody Notes")
    with st.spinner("🎵 Detecting melody..."):
        _, _, note_events = predict(
            tmp_path,
            model_path=ICASSP_2022_MODEL_PATH
        )
        melody_text = notes_to_text(note_events[:48])
        st.text(melody_text)

    # Step 4: PDF generation
    st.subheader("📄 Create Your PDF")
    title = st.text_input("Song Title", value="My Song")

    if st.button("✨ Generate PDF", type="primary"):
        with st.spinner("Building PDF..."):
            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "B", 16)
                    self.cell(0, 12, title, ln=True, align="C")
                    self.ln(5)

            pdf = PDF()
            pdf.add_page()

            # Lyrics section
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Lyrics", ln=True)
            pdf.set_font("Arial", size=12)
            for line in lyrics_out.splitlines():
                if line.strip():
                    if line.startswith("[") and line.endswith("]"):
                        pdf.set_font("Arial", "B", 12)
                        pdf.ln(4)
                        pdf.cell(0, 7, line, ln=True)
                        pdf.set_font("Arial", size=12)
                    else:
                        pdf.multi_cell(0, 6, line)

            # Melody section
            pdf.ln(8)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Melody Notes", ln=True)
            pdf.set_font("Courier", size=11)
            for mline in melody_text.splitlines():
                pdf.cell(0, 6, mline, ln=True)

            # Save and offer download
            pdf_path = os.path.join(tempfile.gettempdir(), "output.pdf")
            pdf.output(pdf_path)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "📥 Download PDF",
                    f,
                    file_name=f"{title.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            os.unlink(pdf_path)
            st.success("✅ Done! Download your PDF above.")

    # Cleanup
    os.unlink(tmp_path)

st.divider()
st.info("💡 Tip: Edit your lyrics before generating the PDF — your changes are saved!")
