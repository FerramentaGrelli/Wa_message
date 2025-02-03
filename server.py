from flask import Flask, request, jsonify
from twilio.rest import Client
import json
from dotenv import load_dotenv
import os
import datetime

# Caricamento delle variabili d'ambiente dal file .env
load_dotenv()

app = Flask(__name__)

# Caricamento delle credenziali Twilio dalle variabili d'ambiente
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

AUTO_REPLY_MESSAGE = ("Grazie per averci scritto!\n"
                      "Purtroppo questo numero non è abilitato alla ricezione di messaggi e non possiamo leggere quanto ci hai scritto\n"
                      "\n"
                      "Per ricevere assistenza, contattaci tramite uno dei seguenti canali:\n"
                      "\n"
                      "📧 assistenza@grelli.it\n"
                      "\n"
                      "📲 +39 3791988758\n"
                      "\n"
                      "📞 +39 0758040747\n"
                      "\n"
                      "Grazie mille,\n" 
                      "\n"
                      "*Ferramenta Grelli*")

twilio_client = Client(account_sid, auth_token)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"message": "Il server e' attivo e funzionante! n'te gasa?"}), 200

def extract_phone(phone):
    """Rimuove il prefisso internazionale +39, se presente."""
    if phone and phone.startswith('+39'):
        return phone[3:]
    return phone

supplier_delays = {
    "FER": 2,
    "CAP": 3,
    "DFL": 2,
    "LAF": 2,
    "KNI": 10,
    "KET": 10,
    "ARC": 8,
    "GRL": 1,
}

def calculate_shipping_date(skus, order_datetime):
    print(f"Calcolando data di spedizione per SKUs: {skus} e orario ordine: {order_datetime}")

    max_delay = 0
    laf_order = False

    # Se l’ordine arriva tra venerdì dopo le 17 e domenica a mezzanotte, consideriamolo come lunedì mattina
    if (order_datetime.weekday() == 4 and order_datetime.hour >= 17) or order_datetime.weekday() in [5, 6]:
        order_datetime = datetime.combine(order_datetime + timedelta(days=(7 - order_datetime.weekday())), time(8, 0))

    for sku in skus:
        prefix = sku[:3]
        if prefix in supplier_delays:
            delay = supplier_delays[prefix]

            # Aggiustamenti per orari specifici
            if prefix in ["FER", "CAP"] and order_datetime.hour >= 17:
                delay += 1
            if prefix == "DFL" and order_datetime.hour >= 10:
                delay += 1
            
            if prefix == "LAF":
                laf_order = True

            max_delay = max(max_delay, delay)

    # Se c’è LAF, applichiamo la logica specifica
    if laf_order:
        order_day = order_datetime.weekday()
        order_time = order_datetime.time()

        if order_day == 0 and order_time <= time(8, 30):  # Lunedì entro le 08:30 -> Mercoledì
            shipping_date = order_datetime.date() + timedelta(days=2)
        elif order_day <= 3 and order_time <= time(8, 30):  # Martedì-Giovedì entro 08:30 -> Lunedì successivo
            shipping_date = order_datetime.date() + timedelta(days=(7 - order_day))
        else:
            # Calcolo normale basato sul massimo ritardo
            shipping_date = order_datetime.date()
            days_added = 0
            while days_added < max_delay:
                shipping_date += timedelta(days=1)
                if shipping_date.weekday() < 5:
                    days_added += 1
    else:
        # Calcolo normale per gli altri fornitori
        shipping_date = order_datetime.date()
        days_added = 0
        while days_added < max_delay:
            shipping_date += timedelta(days=1)
            if shipping_date.weekday() < 5:
                days_added += 1

    print(f"Data di spedizione stimata: {shipping_date.strftime('%d/%m/%Y')}")
    return shipping_date.strftime("%d/%m/%Y")

def send_whatsapp_message(to, content_sid, content_variables):
    try:
        print(f"Invio messaggio a {to} con template {content_sid} e variabili {content_variables}")
        message = twilio_client.messages.create(
            from_=twilio_whatsapp_number,
            to=f'whatsapp:+39{to}',
            body=None,
            content_sid=content_sid,
            content_variables=json.dumps(content_variables)
        )
        print(f"Messaggio inviato con successo! SID: {message.sid}")
    except Exception as e:
        print(f"Errore nell'invio del messaggio: {e}")

@app.route('/webhook', methods=['POST'])
def shopify_webhook_order_created():
    data = request.get_json()
    print("Dati ricevuti dal webhook:")

    customer_phone = extract_phone(data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    customer_name = data.get('billing_address', {}).get('first_name') or data.get('customer', {}).get('default_address', {}).get('first_name')
    payment_method = data.get('payment_gateway_names', [None])[0]
    total_price = data.get('total_price')
    order_datetime = datetime.datetime.strptime(data.get('created_at'), "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
    
    skus = [item['sku'] for item in data.get('line_items', []) if 'sku' in item]
    print(f"SKUs estratti: {skus}")
    estimated_shipping_date = calculate_shipping_date(skus, order_datetime)
  
    if not customer_phone or not customer_name or not order_id:
        print("Errore: Dati mancanti nell'ordine.")
        return jsonify({"status": "error", "message": "Dati mancanti."}), 400

    if payment_method == "Bonifico Bancario":
        send_whatsapp_message(
            to=customer_phone,
            content_sid='HX9996adbb6d2f7ab2cf526af4afb47020',
            content_variables={
                '1': customer_name,
                '2': order_id,
                '3': total_price,
            }
        )
    else:
        send_whatsapp_message(
            to=customer_phone,
            content_sid='HX4dc1f54cfdf34308a9397c4462d3a35f',
            content_variables={
                '1': customer_name,
                '2': order_id,
                '3': estimated_shipping_date
            }
        )
    
    return jsonify({"status": "success"}), 200

# Endpoint per conferma pagamento
@app.route('/webhook_payment_confirmed', methods=['POST'])
def shopify_webhook_payment_confirmed():
    data = request.get_json()
    print("Dati pagamento confermato:", data)

    # Estrai informazioni dall'ordine
    customer_phone = extract_phone(data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    customer_name = data.get('billing_address', {}).get('first_name') or data.get('customer', {}).get('default_address', {}).get('first_name')

    if not customer_phone or not customer_name or not order_id:
        return jsonify({"status": "error", "message": "Dati mancanti."}), 400

    # Messaggio di conferma pagamento
    send_whatsapp_message(
        to=customer_phone,
        content_sid='HXcf8fe6d0d1ab5dfdc63e217875da3776',  # SID del template per conferma pagamento
        content_variables={
            '1': customer_name,  # Nome del cliente
            '2': order_id        # ID ordine
        }
    )

    return jsonify({"status": "success"}), 200

# Endpoint per ordini evasi
@app.route('/webhook_fulfilled', methods=['POST'])
def shopify_webhook_fulfilled():
    data = request.get_json()
    print("Dati ordine evaso:", data)

    # Estrai informazioni dall'ordine
    customer_phone = extract_phone(data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    customer_name = data.get('billing_address', {}).get('first_name') or data.get('customer', {}).get('default_address', {}).get('first_name')

    if not customer_phone or not customer_name or not order_id:
        return jsonify({"status": "error", "message": "Dati mancanti."}), 400

    # Messaggio di ordine evaso
    send_whatsapp_message(
        to=customer_phone,
        content_sid='HXa776638a63e3ddaaf1b31b4db6520793',  # SID del template per "not_partenza"
        content_variables={
            '1': customer_name,  # Nome del cliente
            '2': order_id        # ID ordine
        }
    )

    return jsonify({"status": "success"}), 200

# Endpoint per aggiornamento spedizione
@app.route('/webhook_shipping', methods=['POST'])
def shopify_webhook_shipping():
    data = request.get_json()
    print("Dati ordine spedito:", data)

    customer_phone = extract_phone(data.get('destination', {}).get('phone') or 
                                   data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    if '.' in order_id:
        order_id = order_id.split('.')[0]
    customer_name = data.get('destination', {}).get('first_name') or \
                    data.get('customer', {}).get('default_address', {}).get('first_name')
    tracking_company = data.get('tracking_company')
    tracking_number = data.get('tracking_number')
    tracking_urls = data.get('tracking_urls', [])
    tracking_url = tracking_urls[0] if tracking_urls else None

    if not (customer_phone and customer_name and order_id and tracking_company and tracking_number):
        return jsonify({"status": "error", "message": "Dati mancanti: telefono, nome, ID ordine o informazioni di tracking."}), 400

    variables = {
        '1': customer_name,
        '2': order_id,
        '3': tracking_company,
        '4': tracking_number
    }
    send_whatsapp_message(customer_phone, 'HX0dfb348184a895ca89f0d262071efde9', variables)
    return jsonify({"status": "success"}), 200

# 📩 Webhook per ricevere messaggi WhatsApp
@app.route('/whatsapp_webhook', methods=['POST'])
def whatsapp_webhook():
    # Twilio invia i dati in formato application/x-www-form-urlencoded
    sender_number = request.form.get('From', '').replace('whatsapp:', '')
    received_message = request.form.get('Body', '')

    print(f"📩 Messaggio ricevuto da {sender_number}: {received_message}")

    if sender_number:
        try:
            # Invia la risposta automatica
            message = twilio_client.messages.create(
                from_=twilio_whatsapp_number,
                to=f'whatsapp:{sender_number}',
                body=AUTO_REPLY_MESSAGE
            )
            print(f"✅ Risposta inviata a {sender_number}: {AUTO_REPLY_MESSAGE}")
        except Exception as e:
            print(f"❌ Errore nell'invio del messaggio: {e}")

    return jsonify({"status": "success"}), 200
    
# Avvio del server Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
