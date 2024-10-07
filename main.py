from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import requests
import re

# Crear instancia de FastAPI
app = FastAPI()

# Diccionario para almacenar nombres y ubicaciones de los usuarios
user_data = {}

# Modelo Pydantic para validar las solicitudes
class ChatRequest(BaseModel):
    user_id: str
    question: str = ""
    name: str = None
    location_choice: str = None
    city: str = None
    lat: float = None
    lon: float = None

# Función para normalizar texto y manejar errores en la escritura (quitar tildes, mayúsculas)
def normalize_text(text: str) -> str:
    return re.sub(r'[áàäâéèëêíìïîóòöôúùüûñ]', lambda match: {
        'á':'a', 'à':'a', 'ä':'a', 'â':'a',
        'é':'e', 'è':'e', 'ë':'e', 'ê':'e',
        'í':'i', 'ì':'i', 'ï':'i', 'î':'i',
        'ó':'o', 'ò':'o', 'ö':'o', 'ô':'o',
        'ú':'u', 'ù':'u', 'ü':'u', 'û':'u',
        'ñ':'n'
    }.get(match.group(), match.group()), text.lower())

# Función para obtener latitud y longitud de un lugar usando Nominatim API
def get_coordinates(location: str) -> dict:
    url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
    response = requests.get(url)
    data = response.json()

    if data:
        lat = data[0]['lat']
        lon = data[0]['lon']
        return {"lat": lat, "lon": lon}
    else:
        return None

# Función para obtener datos meteorológicos actuales de Meteomatics API con los nuevos parámetros
def get_meteomatics_data(lat: float, lon: float) -> dict:
    USERNAME = 'gonzalesastoray_andreaabigail'
    PASSWORD = '6DEsh48vL8'
    url = f"https://{USERNAME}:{PASSWORD}@api.meteomatics.com/now/t_2m:C,t_max_2m_24h:C,t_min_2m_24h:C,precip_1h:mm,precip_24h:mm,wind_speed_10m:ms,wind_dir_10m:d,wind_gusts_10m_1h:ms,wind_gusts_10m_24h:ms,msl_pressure:hPa,weather_symbol_1h:idx,weather_symbol_24h:idx,uv:idx,sunrise:sql,sunset:sql/{lat},{lon}/json"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail="Error al obtener los datos meteorológicos")

# Función para comenzar la conversación con una presentación
def start_conversation(user_id: str):
    if user_id not in user_data:
        user_data[user_id] = {"name": None, "location": None, "conversation": True}
        return {"reply": "Hola! Soy tu asistente meteorológico. ¿Cómo te llamas?"}
    else:
        name = user_data[user_id].get("name", "amigo")
        return {"reply": f"¡Hola de nuevo, {name}! ¿En qué te puedo ayudar hoy?"}

# Función para manejar preguntas y respuestas más naturales e informales
def generate_response(question: str, weather_data: dict) -> str:
    temp = weather_data['data'][0]['coordinates'][0]['dates'][0]['value']
    wind_speed = weather_data['data'][5]['coordinates'][0]['dates'][0]['value']
    precip = weather_data['data'][3]['coordinates'][0]['dates'][0]['value']

    normalized_question = normalize_text(question)

    if "temperatura" in normalized_question:
        return f"La temperatura actual es de {temp}°C. ¿Algo más que te interese saber?"
    elif "viento" in normalized_question:
        return f"El viento está a unos {wind_speed} m/s. ¡Agárrate el sombrero si sales!"
    elif "lluvia" in normalized_question or "precipitacion" in normalized_question:
        if precip > 0:
            return f"Está lloviendo, con {precip} mm acumulados. Mejor agarra el paraguas."
        else:
            return "Por ahora no ha llovido, ¡todo despejado!"
    elif "como esta el clima" in normalized_question:
        return f"La temperatura es de {temp}°C y no hay lluvias. ¿Te gustaría saber algo más?"
    else:
        return "Mmm, no estoy seguro de lo que preguntas. ¿Puedes repetirlo de otra forma?"

# Función para preguntar sobre la ubicación
def ask_for_location(user_id: str):
    if user_data[user_id]["location"] is None:
        return {"reply": f"¿Te gustaría usar tu ubicación actual o prefieres otra? Responde 'actual' o 'otra'."}
    else:
        return {"reply": "Parece que ya tenemos tu ubicación. ¿Te gustaría continuar?"}

# Función para procesar la elección de ubicación
def handle_location_choice(user_id: str, choice: str):
    normalized_choice = normalize_text(choice)
    if "otra" in normalized_choice:
        user_data[user_id]["location"] = "otra"
        return {"reply": "Por favor, dime el nombre de la ciudad o lugar que te gustaría usar."}
    elif "actual" in normalized_choice:
        user_data[user_id]["location"] = "ubicación actual"
        return {"reply": "¡Genial! Usaremos tu ubicación actual. ¿Qué te gustaría saber sobre el clima?"}
    else:
        return {"reply": "No entendí tu respuesta. ¿Prefieres usar 'ubicación actual' o 'otra'?"}

# Endpoint principal para el chatbot interactivo
@app.post("/chatbot")
async def chatbot(chat_request: ChatRequest):
    user_id = chat_request.user_id
    question = chat_request.question
    name = chat_request.name
    location_choice = chat_request.location_choice
    city = chat_request.city
    lat = chat_request.lat
    lon = chat_request.lon

    # Comenzar la conversación y preguntar el nombre
    if not user_data.get(user_id):
        return start_conversation(user_id)

    # Guardar el nombre del usuario
    if name and not user_data[user_id]["name"]:
        user_data[user_id]["name"] = name
        return ask_for_location(user_id)

    # Si el usuario elige entre ubicación actual u otra
    if location_choice and user_data[user_id]["location"] is None:
        return handle_location_choice(user_id, location_choice)

    # Si el usuario proporciona el nombre de una ciudad o lugar
    if city and user_data[user_id]["location"] == "otra":
        coordinates = get_coordinates(city)
        if coordinates:
            lat, lon = coordinates['lat'], coordinates['lon']
            user_data[user_id]["coordinates"] = coordinates
            return {"reply": f"Usaremos {city} como tu ubicación. ¿Qué te gustaría saber sobre el clima en {city}?"}
        else:
            return {"reply": f"No pude encontrar la ubicación {city}. ¿Puedes intentarlo de nuevo?"}

    # Obtener coordenadas si eligió una ubicación diferente
    if user_data[user_id]["location"] == "otra" and "coordinates" in user_data[user_id]:
        lat = user_data[user_id]["coordinates"]["lat"]
        lon = user_data[user_id]["coordinates"]["lon"]

    # Obtener datos de la ubicación actual (si no se eligió otra)
    if user_data[user_id]["location"] == "ubicación actual" and lat and lon:
        meteomatics_data = get_meteomatics_data(lat, lon)
        return {"reply": generate_response(question, meteomatics_data)}

    return {"reply": "No pude procesar tu solicitud. Intenta de nuevo."}
