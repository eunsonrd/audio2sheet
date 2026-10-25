
import streamlit as st
from fpdf import FPDF
import os
import tempfile

# Page setup
st.set_page_config(page_title="Lyrics & Sheet Music PDF", page_icon="🎵")
st.title("🎵 Lyrics + Blank Staves PDF")
st.write("Type or paste your lyrics → Get a clean PDF with blank staves above each line!")

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

# ─────────── MAIN APP ───────────
st.subheader("📝 Enter Your Lyrics")
st.info("💡 Each line below will get its own blank music staff in the PDF.")

c1, c2, c3, c4 = st.columns(4)
with c1: do_split = st.button("📏 Split Lines")
with c2: do_verse = st.button("📖 Add Verses")
with c3: do_chorus = st.button("🎤 Add Chorus")
with c4: do_clean = st.button("🧹 Clean")

if "lyrics" not in st.session_state:
    st.session_state.lyrics = ""

if do_split and st.session_state.lyrics:
    st.session_state.lyrics = split_lines(st.session_state.lyrics)
if do_verse and st.session_state.lyrics:
    st.session_state.lyrics = add_verses(st.session_state.lyrics)
if do_chorus and st.session_state.lyrics:
    st.session_state.lyrics = add_chorus(st.session_state.lyrics)
if do_clean:
    st.session_state.lyrics = "\n".join(
        [l.strip() for l in st.session_state.lyrics.splitlines() if l.strip()]
    )

lyrics_out = st.text_area(
    "✏️ Type or paste your lyrics here:",
    value=st.session_state.lyrics,
    height=250,
    key="lyrics"
)

st.subheader("📄 PDF Options")
title = st.text_input("Song Title", value="My Song")
clef_choice = st.radio("Clef to display:", ["Treble Clef", "Bass Clef", "Both"], horizontal=True)

# ─────────── PDF GENERATION ───────────
def draw_staff(pdf, clef="treble"):
    """Draw one blank staff with clef"""
    line_y = pdf.get_y()
   
    # Staff lines — 5 horizontal lines
    for i in range(5):
        y_line = line_y + (i * 2.5)
        pdf.line(15, y_line, 195, y_line)
   
    # Clef symbol (text representation — clear which one it is)
    pdf.set_font("Arial", "B", 14)
    if clef == "treble":
        pdf.text(10, line_y + 9, "𝄢")  # Bass clef symbol
    elif clef == "bass":
        pdf.text(10, line_y + 9, "𝄞")  # Treble clef symbol
    else:  # both
        pdf.text(8, line_y + 9, "𝄞   𝄢")
   
    # Bar line at end
    pdf.line(193, line_y, 193, line_y + 10)
   
    # Move cursor down past the staff
    pdf.set_y(line_y + 14)

def draw_double_staff(pdf):
    """Draw grand staff: treble + bass"""
    line_y = pdf.get_y()
   
    # Treble staff — 5 lines
    for i in range(5):
        y_line = line_y + (i * 2.5)
        pdf.line(15, y_line, 195, y_line)
    pdf.set_font("Arial", "B", 14)
    pdf.text(10, line_y + 9, "𝄞")
   
    # Space between staves
    mid_gap = line_y + 14
   
    # Bass staff — 5 lines
    for i in range(5):
        y_line = mid_gap + (i * 2.5)
        pdf.line(15, y_line, 195, y_line)
    pdf.text(10, mid_gap + 9, "𝄢")
   
    # Bar lines
    pdf.line(193, line_y, 193, mid_gap + 10)
    pdf.line(15, line_y, 15, mid_gap + 10)
   
    pdf.set_y(mid_gap + 14)

if st.button("✨ Generate PDF", type="primary") and lyrics_out.strip():
    with st.spinner("Creating your PDF..."):
       
        class SheetPDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 18)
                self.cell(0, 12, title, ln=True, align="C")
                self.ln(3)
                self.set_font("Arial", "I", 10)
                self.set_text_color(10, 100, 100)
                self.cell(0, 6, "Write your notes on the staves below", ln=True, align="C")
                self.set_text_color(0, 0, 0)
                self.ln(5)
       
        pdf = SheetPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
       
        # Choose drawing function
        if clef_choice == "Treble Clef":
            draw = lambda pdf: draw_staff(pdf, "treble")
        elif clef_choice == "Bass Clef":
            draw = lambda pdf: draw_staff(pdf, "bass")
        else:
            draw = draw_double_staff
       
        # Process each line
        for line in lyrics_out.splitlines():
            line = line.strip()
            if not line:
                pdf.ln(4)
                continue
           
            # Section header (Verse/Chorus)
            if line.startswith("[") and line.endswith("]"):
                pdf.ln(4)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, line, ln=True)
                pdf.set_font("Arial", size=12)
                continue
           
            # Blank staff
            draw(pdf)
           
            # Lyrics centered below staff
            pdf.set_x(15)
            pdf.cell(0, 7, line, ln=True, align="C")
            pdf.ln(3)
       
        # Save and download
        output_path = os.path.join(tempfile.gettempdir(), "blank_staves.pdf")
        pdf.output(output_path)
       
        with open(output_path, "rb") as f:
            st.download_button(
                "📥 Download Your PDF",
                f,
                file_name=f"{title.replace(' ', '_')}_sheet.pdf",
                mime="application/pdf"
            )
       
        os.unlink(output_path)
        st.success("✅ Done! Your PDF is ready — enjoy writing your music! 🎵")

elif not lyrics_out.strip():
    st.info("👆 Type some lyrics above, then click Generate PDF!")

st.divider()
st.info("💡 Tip: One line of lyrics = one staff. Use the buttons to add [Verse] and [Chorus] headers!")


