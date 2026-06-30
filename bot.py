def obtener_resultado_guacharito():
    try:
        response = requests.get(URL_GUACHARITO, headers=HEADERS, timeout=15)
        print(f"--- AUDITORÍA GUACHARITO (Status: {response.status_code}) ---")
        # Esto imprimirá los primeros 1000 caracteres de lo que ve el bot
        print(response.text[:1000]) 
        return None
    except Exception as e:
        print(f"❌ Error Auditoría Guacharito: {e}")
        return None

def obtener_resultado_segunda_loteria():
    try:
        response = requests.get(URL_SEGUNDA_LOTERIA, headers=HEADERS, timeout=15)
        print(f"--- AUDITORÍA GUÁCHARO (Status: {response.status_code}) ---")
        print(response.text[:1000])
        return None
    except Exception as e:
        print(f"❌ Error Auditoría Guácharo: {e}")
        return None
