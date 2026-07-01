import streamlit as st
import pdfplumber
import fitz
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch


st.set_page_config(page_title="Amazon Towel Production Helper", layout="wide")

st.title("Amazon Towel Production Helper")
st.write("Upload shipping label PDF and packing slip PDF. The app matches them by customer name and creates a production PDF.")


def extract_text_from_pdf(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_field(pattern, text, default=""):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return default


def parse_slip(text):
    order_id = extract_field(r"Order ID:\s*([0-9\-]+)", text)
    customer = extract_field(r"Ship To:\s*\n?([A-Za-z\s]+)", text)

    product_match = re.search(r"1\s+(Soleus.*?)(?:SKU:|ASIN:)", text, re.DOTALL | re.IGNORECASE)
    product = product_match.group(1).replace("\n", " ").strip() if product_match else ""

    font_style = extract_field(r"Font Style:\s*(.*)", text)
    thread_color = extract_field(r"Thread Color:\s*(.*)", text)
    gift = extract_field(r"Gift Note & Gift Bag:\s*(.*)", text)

    towel_lines = []
    for line in text.splitlines():
        if ":" in line:
            left, right = line.split(":", 1)
            if any(word in left.lower() for word in ["towel", "washcloth", "blanket", "robe"]):
                towel_lines.append((left.strip(), right.strip()))

    return {
        "order_id": order_id,
        "customer": customer,
        "product": product,
        "font_style": font_style,
        "thread_color": thread_color,
        "gift": gift,
        "items": towel_lines,
    }


def render_label_page_to_image(label_file):
    label_bytes = label_file.read()
    doc = fitz.open(stream=label_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    return img_bytes


def create_production_pdf(label_image_bytes, data):
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    label_img = BytesIO(label_image_bytes)

    # Label image
    c.drawImage(label_img, 0.6 * inch, 3.5 * inch, width=4.1 * inch, height=5.4 * inch, preserveAspectRatio=True)

    # Production card
    x = 4.9 * inch
    y = 8.5 * inch

    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, "PRODUCTION DETAILS")
    y -= 0.25 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Order ID:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.8 * inch, y, data["order_id"])
    y -= 0.22 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Customer:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.8 * inch, y, data["customer"])
    y -= 0.28 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Font Style:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.9 * inch, y, data["font_style"])
    y -= 0.22 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Thread Color:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 1.0 * inch, y, data["thread_color"])
    y -= 0.28 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Product:")
    y -= 0.18 * inch
    c.setFont("Helvetica", 8)

    product_text = data["product"][:180]
    for i in range(0, len(product_text), 45):
        c.drawString(x, y, product_text[i:i+45])
        y -= 0.17 * inch

    y -= 0.1 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "TOWEL TEXTS")
    y -= 0.22 * inch

    c.setFont("Helvetica", 9)
    for item, name in data["items"]:
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x, y, item + ":")
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 1.55 * inch, y, name)
        y -= 0.2 * inch

    y -= 0.1 * inch
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, "Gift Note & Gift Bag:")
    y -= 0.2 * inch
    c.setFont("Helvetica", 8.5)
    c.drawString(x, y, data["gift"] if data["gift"] else "-")

    c.showPage()
    c.save()

    output.seek(0)
    return output


label_pdf = st.file_uploader("Upload Shipping Label PDF", type=["pdf"])
slip_pdf = st.file_uploader("Upload Packing Slip PDF", type=["pdf"])

if label_pdf and slip_pdf:
    slip_text = extract_text_from_pdf(slip_pdf)
    data = parse_slip(slip_text)

    st.subheader("Detected Slip Details")
    st.json(data)

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
