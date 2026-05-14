from fpdf import FPDF
from datetime import datetime


def generate_ticket_pdf(pedido: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_fill_color(30, 41, 59)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_y(8)
    pdf.cell(0, 12, "Cafeteria Universitaria", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, "Ticket de Pedido", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(241, 245, 249)
    pdf.cell(0, 8, f"  Pedido #: {pedido['id'][:8].upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(40, 7, "Cliente:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, pedido.get("cliente_nombre", ""), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=11)
    pdf.cell(40, 7, "Correo:", new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 7, pedido.get("cliente_email", ""), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=11)
    pdf.cell(40, 7, "Fecha:", new_x="RIGHT", new_y="TOP")
    created = pedido.get("created_at", "")
    try:
        dt = datetime.fromisoformat(created)
        fecha = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        fecha = created
    pdf.cell(0, 7, fecha, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(110, 8, "  Producto", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 8, "Precio", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=11)
    fill = False
    for item in pedido.get("items", []):
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(110, 7, f"  {item['producto_nombre']}", fill=True, new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, f"  ${float(item['precio']):.2f}", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        fill = not fill

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_fill_color(220, 252, 231)
    pdf.cell(110, 9, "", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 9, f"  Total:  ${float(pedido.get('total', 0)):.2f}", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, "Gracias por su compra.", align="C", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
