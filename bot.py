if __name__ == "__main__":
    srv = threading.Thread(target=servidor, name="HTTP")
    srv.daemon = False
    srv.start()
    # Prueba de envío al arrancar
    if bot:
        try:
            bot.send_message(CANAL_ID, "🔔 *Prueba de conexión* - Bot iniciado correctamente", parse_mode="Markdown")
            print("[TEST] Mensaje de prueba enviado")
        except Exception as e:
            print(f"[TEST] Error al enviar prueba: {e}")
    bucle()
