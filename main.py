import os, io, re
from urllib.parse import urlparse
from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.svg import SvgImage
from telegram import from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ✅ Token bot của anh (đổi nếu anh revoke token)
TOKEN = "8214290283:AAFym1JqZNqiV6NM_YcqhW4K9726OATOOVw"
LOGO_PATH = "logo.png"   # file logo đặt cùng thư mục

URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)
HELP_TEXT = ("Gửi link Google Maps (https://maps.app.goo.gl/... hoặc https://www.google.com/maps/...).\n"
             "Em sẽ trả QR PNG (có logo VietinBank) + SVG vector (không logo) để in.")

def is_google_maps_url(u: str) -> bool:
    try:
        p = urlparse(u.strip())
        if p.scheme not in ("http","https"): return False
        host = p.netloc.lower()
        return (host.endswith("google.com") or host == "maps.app.goo.gl" or host.endswith("goo.gl")) and \
               (("maps" in p.path.lower()) or host == "maps.app.goo.gl" or "/maps" in u.lower())
    except Exception:
        return False

def extract_first_maps_url(text: str) -> str|None:
    for m in URL_RE.finditer(text or ""):
        url = m.group(1)
        if is_google_maps_url(url): return url
    return None

def qr_core_image(data: str) -> Image.Image:
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(data.strip()); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w,h = img.size
    if max(w,h) < 640: img = img.resize((w*2, h*2), Image.NEAREST)
    return img

def overlay_center_logo(qr_img: Image.Image, logo_path: str, rel_size: float = 0.22) -> Image.Image:
    img = qr_img.copy(); W,H = img.size; side = int(min(W,H)*rel_size)
    if not (logo_path and os.path.exists(logo_path)): return img
    logo = Image.open(logo_path).convert("RGBA"); logo.thumbnail((side,side), Image.LANCZOS)
    pad = max(6, side//12); bg_w, bg_h = logo.width+pad*2, logo.height+pad*2
    # nền trắng bo góc
    mask = Image.new("L",(bg_w,bg_h),0); draw = ImageDraw.Draw(mask)
    radius = max(8, bg_w//6); draw.rounded_rectangle([(0,0),(bg_w-1,bg_h-1)], radius=radius, fill=255)
    rounded = Image.new("RGBA",(bg_w,bg_h),(255,255,255,255)); rounded.putalpha(mask)
    rounded.alpha_composite(logo,(pad,pad))
    img = img.convert("RGBA"); pos = ((W-bg_w)//2, (H-bg_h)//2); img.alpha_composite(rounded,pos)
    return img.convert("RGB")

def make_qr_png_with_logo(data: str, logo_path: str) -> bytes:
    core = qr_core_image(data); img = overlay_center_logo(core, logo_path)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0); return buf.read()

def make_qr_svg(data: str) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(data.strip()); qr.make(fit=True)
    img = qr.make_image(image_factory=SvgImage)
    buf = io.BytesIO(); img.save(buf); buf.seek(0); return buf.read()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Hướng dẫn", callback_data="help")]])
    await update.message.reply_text("Chào anh Kiệt 👋 Dán link Google Maps, em trả QR có logo VietinBank!", reply_markup=kb, disable_web_page_preview=True)

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); await q.edit_message_text(HELP_TEXT, disable_web_page_preview=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    url = extract_first_maps_url(text.split(maxsplit=1)[1] if text.lower().startswith("/qr") and len(text.split(maxsplit=1))>1 else text)
    if not url:
        await update.message.reply_text("Em chưa thấy link Google Maps hợp lệ.\n"+HELP_TEXT, disable_web_page_preview=True); return
    try:
        png = make_qr_png_with_logo(url, LOGO_PATH); svg = make_qr_svg(url)
        await update.message.reply_photo(photo=png, caption=f"QR Google Maps (có logo) cho:\n{url}", read_timeout=60)
        await update.message.reply_document(
    document=InputFile(svg_bytes, filename="qr.svg"),
    caption="SVG vector (không logo) để in.",
    read_timeout=60)
    except Exception as e:
        await update.message.reply_text(f"Lỗi tạo QR: {e}")

def main():
    if not TOKEN: raise RuntimeError("Thiếu TOKEN.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="^help$"))
    from telegram.ext import filters as f
    app.add_handler(MessageHandler(f.Regex(r"^/qr(\s|$)") & ~f.COMMAND, handle_text))
    app.add_handler(MessageHandler(f.TEXT & ~f.COMMAND, handle_text))
    app.add_handler(MessageHandler(f.COMMAND, start))
    print("QR Map Bot (logo) is running…"); app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__": main()

