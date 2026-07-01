import streamlit as st
import pdfplumber
import fitz
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch


st.set_page_config(
    page_title="Karvyn Towel Production Helper",
    layout="wide"
)

st.title("Karvyn Towel Production Helper")
st.write("Upload shipping label PDF and packing slip PDF. The app matches by customer name and creates a production PDF.")


# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------
def extract_text_from_pdf(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_field(pattern, text, default=""):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return default


# -----------------------------
# SLIP PARSER
# -----------------------------
def parse_slip(text):
    order_id = extract_field(r"Order ID:\s*([0-9\-]+)", text)

    customer = extract_field(
        r"Ship To:\s*\n?([A-Za-z\s]+)\n",
        text
    )

    if not customer:
        customer = extract_field(
            r"Shipping Address:\s*\n?([A-Za-z\s]+)\n",
            text
        )

    product_match = re.search(
        r"1\s+(.*?)(?:SKU:|ASIN:|Condition:)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    product = ""
    if product_match:
        product = product_match.group(1).replace("\n", " ").strip()

    font_style = extract_field(r"Font Style:\s*(.*)", text)
    thread_color = extract_field(r"Thread Color:\s*(.*)", text)
    gift = extract_field(r"Gift Note & Gift Bag:\s*(.*)", text)

    excluded_fields = [
        "font style",
        "thread color",
        "gift note",
        "gift bag",
        "gift note & gift bag",
        "surface",
        "please check",
        "customizations",
        "sku",
        "asin",
        "condition",
        "order item id",
        "quantity",
        "unit price",
        "order totals",
        "item subtotal",
        "shipping total",
        "tax",
        "grand total",
    ]

    production_lines = []

    customization_started = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if "Customizations" in line:
            customization_started = True
            continue

        if not customization_started:
            continue

        if ":" not in line:
            continue

        left, right = line.split(":", 1)
        left_clean = left.strip()
        right_clean = right.strip()

        left_lower = left_clean.lower()

        if any(excluded in left_lower for excluded in excluded_fields):
            continue

        if not right_clean:
            continue

        production_lines.append((left_clean, right_clean))

    return {
        "order_id": order_id,
        "customer": customer,
        "product": product,
        "font_style": font_style,
        "thread_color": thread_color,
        "gift": gift,
        "production_lines": production_lines,
    }


# -----------------------------
# LABEL IMAGE
# -----------------------------
def render_label_page_to_image(label_file):
    label_bytes = label_file.read()
    doc = fitz.open(stream=label_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    return img_bytes


# -----------------------------
# PDF CREATION
# -----------------------------
def draw_wrapped_text(c, text, x, y, max_chars, font="Helvetica", size=8, line_gap=0.16):
    c.setFont(font, size)

    words = text.split()
    line = ""

    for word in words:
        if len(line + " " + word) <= max_chars:
            line = (line + " " + word).strip()
        else:
            c.drawString(x, y, line)
            y -= line_gap * inch
            line = word

    if line:
        c.drawString(x, y, line)
        y -= line_gap * inch

    return y


def create_production_pdf(label_image_bytes, data):
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    label_img = BytesIO(label_image_bytes)

    # Original label on left
    c.drawImage(
        label_img,
        0.35 * inch,
        3.15 * inch,
        width=4.45 * inch,
        height=5.7 * inch,
        preserveAspectRatio=True
    )

    # Production card on right
    x = 4.95 * inch
    y = 8.55 * inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "PRODUCTION DETAILS")
    y -= 0.30 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Order ID:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.85 * inch, y, data["order_id"])
    y -= 0.22 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Customer:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.85 * inch, y, data["customer"])
    y -= 0.30 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Font Style:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.95 * inch, y, data["font_style"])
    y -= 0.22 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Thread:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.95 * inch, y, data["thread_color"])
    y -= 0.32 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Product:")
    y -= 0.18 * inch

    y = draw_wrapped_text(
        c,
        data["product"],
        x,
        y,
        max_chars=42,
        font="Helvetica",
        size=7.8,
        line_gap=0.15
    )

    y -= 0.10 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "ITEM TEXTS")
    y -= 0.24 * inch

    if data["production_lines"]:
        for item, name in data["production_lines"]:
            if y < 1.25 * inch:
                c.showPage()
                y = 8.5 * inch

            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(x, y, item + ":")
            c.setFont("Helvetica", 8.5)
            c.drawString(x + 1.55 * inch, y, name)
            y -= 0.20 * inch
    else:
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y, "No item text detected.")
        y -= 0.22 * inch

    y -= 0.12 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Gift Note & Gift Bag:")
    y -= 0.20 * inch

    gift_text = data["gift"] if data["gift"] else "-"
    y = draw_wrapped_text(
        c,
        gift_text,
        x,
        y,
        max_chars=42,
        font="Helvetica",
        size=8.5,
        line_gap=0.16
    )

    c.showPage()
    c.save()

    output.seek(0)
    return output


# -----------------------------
# APP UI
# -----------------------------
label_pdf = st.file_uploader("Upload Shipping Label PDF", type=["pdf"])
slip_pdf = st.file_uploader("Upload Packing Slip PDF", type=["pdf"])

if label_pdf and slip_pdf:
    slip_text = extract_text_from_pdf(slip_pdf)
    data = parse_slip(slip_text)

    st.subheader("Detected Order Details")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Order ID:**", data["order_id"])
        st.write("**Customer:**", data["customer"])
        st.write("**Font Style:**", data["font_style"])
        st.write("**Thread Color:**", data["thread_color"])
        st.write("**Gift Note & Gift Bag:**", data["gift"])

    with col2:
        st.write("**Product:**")
        st.write(data["product"])

    st.subheader("Detected Item Texts")

    if data["production_lines"]:
        for item, name in data["production_lines"]:
            st.write(f"**{item}:** {name}")
    else:
        st.warning("No item text detected.")

    if st.button("Generate Production PDF"):
        label_image = render_label_page_to_image(label_pdf)
        result_pdf = create_production_pdf(label_image, data)

        st.success("Production PDF created.")

        st.download_button(
            label="Download Production PDF",
            data=result_pdf,
            file_name="production_label.pdf",
            mime="application/pdf"
        )
