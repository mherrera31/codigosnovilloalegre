# qr_utils.py
import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
from fpdf import FPDF # Asegúrate de que tu librería FPDF funcione (fpdf2)

def create_qr_card(data_to_encode: str, output_path: str, description: str, expiration: str):
    """Genera una imagen de tarjeta con el QR, optimizada para tamaño de presentación."""
    
    # Asegúrate de que la carpeta de salida exista
    if not os.path.exists('generated_qrs'):
        os.makedirs('generated_qrs')
        
    # Dimensiones con una relación de aspecto de tarjeta de presentación (aprox 1.75)
    card_width, card_height = 875, 500 
    bg_color, text_color = (255, 255, 255), (0, 0, 0)
    accent_color = (191, 2, 2) # Rojo Novillo Alegre

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    card_img = Image.new('RGB', (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card_img)

    draw.rectangle([0, 0, card_width, 80], fill=accent_color)
    try:
        # Intenta usar fuentes TrueType (debe existir arialbd.ttf o una alternativa)
        title_font = ImageFont.truetype("arialbd.ttf", size=32)
        main_font = ImageFont.truetype("arial.ttf", size=30)
    except IOError:
        # Usa la fuente por defecto si no se encuentra
        title_font = main_font = ImageFont.load_default()
        
    draw.text((30, 25), "TARJETA DE REGALO NOVILLO ALEGRE", fill=(255,255,255), font=title_font)
        
    # Pegar QR
    qr_size = 256 # Tamaño base del QR generado
    qr_scaled = qr_img.resize((card_height - 100, card_height - 100)) # Ajustar el tamaño del QR para la tarjeta
    card_img.paste(qr_scaled, (card_width - qr_scaled.width - 50, 100)) # Posicionamiento
    
    draw.text((50, 150), description, fill=text_color, font=main_font)
    draw.text((50, 220), f"Válido hasta: {expiration}", fill=(100, 100, 100), font=main_font)

    card_img.save(output_path)
    return output_path

def generate_pdf_from_images(image_paths, output_filename):
    """Crea un PDF a partir de una lista de imágenes, cada una en una página tamaño tarjeta."""
    # Dimensiones en mm para una tarjeta de presentación estándar (CR80)
    CARD_WIDTH_MM = 85.6
    CARD_HEIGHT_MM = 53.98
    
    # FPDF debe inicializarse con las dimensiones de la tarjeta
    pdf = FPDF(orientation='L', unit='mm', format=(CARD_WIDTH_MM, CARD_HEIGHT_MM))
    
    for image_path in image_paths:
        pdf.add_page()
        # La imagen se ajusta al tamaño de la página (tarjeta)
        pdf.image(image_path, x=0, y=0, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM) 
        
    pdf.output(output_filename)
    return output_filename
