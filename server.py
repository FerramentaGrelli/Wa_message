from flask import Flask, request, jsonify
from twilio.rest import Client
import json
from dotenv import load_dotenv
import os

# Caricamento delle variabili d'ambiente dal file .env
load_dotenv()

app = Flask(__name__)

# Caricamento delle credenziali Twilio dalle variabili d'ambiente
account_sid = os.getenv('TWILIO_ACCOUNT_SID', 'AC279ed44b7238e36d395af0a371b96be3')
auth_token = os.getenv('TWILIO_AUTH_TOKEN', 'd1fd562ce73505b5b8cc054d26f9fb2a')
twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+393896896372')

twilio_client = Client(account_sid, auth_token)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"message": "Il server è attivo e funzionante!"}), 200

def send_whatsapp_message(to, template_sid, variables):
    """
    Funzione per inviare un messaggio WhatsApp tramite Twilio
    """
    try:
        # Log per tracciare i dettagli del messaggio in uscita
        print(f"Tentativo di invio messaggio a {to} usando il template {template_sid} con variabili: {variables}")

        # Creazione del messaggio
        message = twilio_client.messages.create(
            from_=twilio_whatsapp_number,
            to=to,
            body=None,  # Lasciato vuoto perché stiamo usando un template
            content_sid=template_sid,
            content_variables=json.dumps(variables)
        )
        # Log in caso di successo
        print(f"Messaggio inviato con successo! SID: {message.sid}")
        return {"status": "success", "sid": message.sid}
    except Exception as e:
        # Log in caso di errore
        print(f"Errore durante l'invio del messaggio: {e}")
        return {"status": "error", "error": str(e)}

@app.route('/webhook', methods=['POST'])
def shopify_webhook_order_created():
    """
    Endpoint per gestire i webhook di ordini creati da Shopify
    """
    data = request.get_json()
    print("Ricevuto payload per ordine creato:", data)

    customer_phone = (
        data.get('billing_address', {}).get('phone') or
        data.get('customer', {}).get('default_address', {}).get('phone')
    )
    order_id = data.get('name')
    customer_name = (
        data.get('billing_address', {}).get('first_name') or
        data.get('customer', {}).get('default_address', {}).get('first_name')
    )

    # Log per verificare i dati estratti
    print(f"Dati estratti - Nome cliente: {customer_name}, Telefono: {customer_phone}, ID ordine: {order_id}")

    if customer_phone and customer_name:
        variables = {'1': customer_name, '2': order_id}
        response = send_whatsapp_message(
            to=f'whatsapp:{customer_phone}',
            template_sid='HXb5eb1051e4ae9085bf6c663bd62ecedd',
            variables=variables
        )
        return jsonify(response), 200
    else:
        # Log in caso di dati mancanti
        print("Errore: Dati insufficienti per inviare il messaggio.")
        return jsonify({"status": "error", "error": "Dati insufficienti per inviare il messaggio."}), 400

@app.route('/webhook_fulfilled', methods=['POST'])
def shopify_webhook_fulfilled():
    """
    Endpoint per gestire i webhook di ordini evasi da Shopify
    """
    data = request.get_json()
    print("Ricevuto payload per ordine evaso:", data)

    customer_phone = (
        data.get('billing_address', {}).get('phone') or
        data.get('customer', {}).get('default_address', {}).get('phone')
    )
    order_id = data.get('name')
    customer_name = (
        data.get('billing_address', {}).get('first_name') or
        data.get('customer', {}).get('default_address', {}).get('first_name')
    )

    # Log per verificare i dati estratti
    print(f"Dati estratti - Nome cliente: {customer_name}, Telefono: {customer_phone}, ID ordine: {order_id}")

    if customer_phone and customer_name:
        variables = {'1': customer_name, '2': order_id}
        response = send_whatsapp_message(
            to=f'whatsapp:{customer_phone}',
            template_sid='HXc814c3fc47ebc90c0ec2c067ff94cf93',
            variables=variables
        )
        return jsonify(response), 200
    else:
        # Log in caso di dati mancanti
        print("Errore: Dati insufficienti per inviare il messaggio.")
        return jsonify({"status": "error", "error": "Dati insufficienti per inviare il messaggio."}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
