from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import httpx
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Conexión a la base de datos SQLite
conn = sqlite3.connect("configuraciones.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS configuraciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id TEXT,
        token TEXT
    )
''')
conn.commit()

@app.get("/configurar", response_class=HTMLResponse)
async def mostrar_formulario(request: Request):
    return templates.TemplateResponse("configurar.html", {"request": request})

@app.post("/configurar")
async def guardar_configuracion(
    request: Request,
    instance_id: str = Form(...),
    token: str = Form(...)
):
    conn = sqlite3.connect("configuraciones.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO configuraciones (instance_id, token) VALUES (?, ?)", (instance_id, token))
    conn.commit()
    conn.close()
    return templates.TemplateResponse("configurar.html", {
        "request": request,
        "mensaje": "Configuración guardada correctamente ✅"
    })

@app.post("/webhook")
async def recibir_pedido(pedido: dict):
    conn = sqlite3.connect("configuraciones.db")
    cursor = conn.cursor()
    cursor.execute("SELECT instance_id, token FROM configuraciones ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()

    if not result:
        print("No hay configuración guardada")
        return {"error": "No hay configuración"}

    instance_id, token = result
    telefono = pedido.get("shipping_address", {}).get("phone")
    nombre = pedido.get("shipping_address", {}).get("name")
    direccion = pedido.get("shipping_address", {}).get("address1")

    if not telefono:
        print("⚠️ Pedido sin número de teléfono.")
        return {"error": "Pedido sin número de teléfono"}

    productos = ""
    for item in pedido.get("line_items", []):
        productos += f"• {item.get('name')} x{item.get('quantity')}\n"

    mensaje = (
        f"🛍️ Hola {nombre}!\n\n"
        f"Gracias por tu pedido #{pedido.get('id')} en nuestra tienda ❤️\n\n"
        f"📦 Productos:\n{productos}\n"
        f"📍 Dirección de entrega:\n{direccion}\n\n"
        "Te avisaremos cuando tu pedido esté en camino. ¡Gracias por confiar en nosotros! 📬"
    )

    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    payload = {
        "token": token,
        "to": telefono,
        "body": mensaje
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=payload)
            print("✅ WhatsApp enviado a:", telefono)
            return {"status": "success", "whatsapp_response": response.json()}
        except Exception as e:
            print("❌ Error enviando WhatsApp:", str(e))
            return {"error": str(e)}
