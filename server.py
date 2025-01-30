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
    "DFL": 3,
    "LAF": 3,
}

def calculate_shipping_date(skus, order_datetime):
    print(f"Calcolando data di spedizione per SKUs: {skus} e orario ordine: {order_datetime}")
    max_delay = 0
    for sku in skus:
        prefix = sku[:3]
        if prefix in supplier_delays:
            delay = supplier_delays[prefix]
            
            if prefix in ["FER", "CAP"] and order_datetime.hour >= 17:
                delay += 1
            if prefix == "DFL" and order_datetime.hour >= 10:
                delay += 1
            
            max_delay = max(max_delay, delay)
    
    shipping_date = order_datetime.date()
    days_added = 0
    while days_added < max_delay:
        shipping_date += datetime.timedelta(days=1)
        if shipping_date.weekday() < 5:  # Esclude sabato (5) e domenica (6)
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
    print("Dati ricevuti dal webhook:", json.dumps(data, indent=2))

    customer_phone = data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone')
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
            content_sid='HX52842202fcd7eacbb58c0be40b718e21',
            content_variables={
                '1': customer_name,
                '2': order_id,
                '3': total_price,
            }
        )
    else:
        send_whatsapp_message(
            to=customer_phone,
            content_sid='HX2a67b36c226811c9d9153b0512a16778',
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
        content_sid='HX76a884b0a9b5426891612e2ad17b2e09',  # SID del template per "not_partenza"
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
    send_whatsapp_message(customer_phone, 'HXb121236c140447b2c01c7625d2503558', variables)
    return jsonify({"status": "success"}), 200

# Endpoint per Ordini rimborsati
@app.route('/webhook_refund', methods=['POST'])
def shopify_webhook_refund():
    data = request.get_json()
    print("Dati ordine rimborsato:", data)

    # Estrai informazioni dall'ordine
    customer_phone = extract_phone(data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    customer_name = data.get('billing_address', {}).get('first_name') or data.get('customer', {}).get('default_address', {}).get('first_name')

    # Estrai il metodo di pagamento
    payment_method = data.get('transactions', [{}])[0].get('gateway', 'Non specificato')
    
    # Estrai il totale del rimborso dalla sezione delle transazioni
    total_refund = data.get('transactions', [{}])[0].get('amount', '0.00')
    # Debug: Stampa i dati estratti
    print("Telefono cliente:", customer_phone)
    print("ID ordine:", order_id)
    print("Nome cliente:", customer_name)
    print("Metodo di pagamento:", payment_method)
    print("Totale rimborso:", total_refund)
    
    if not customer_phone or not customer_name or not order_id:
        return jsonify({"status": "error", "message": "Dati mancanti."}), 400

    send_whatsapp_message(
        to=customer_phone,
        content_sid='HX3eaece9adcab7f17a7f9341813528219',  # SID del template per "prova"
        content_variables={
            '1': customer_name,  # Nome del cliente
            '2': order_id,       # ID ordine
            '3': total_refund     # Rimborso totale
        }
    )
    
    return jsonify({"status": "success"}), 200

# Avvio del server Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
