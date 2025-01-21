from flask import Flask, request, jsonify
from twilio.rest import Client
import json
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

app = Flask(__name__)

# Usa le variabili d'ambiente
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
print(f"Account SID: {account_sid}")
print(f"Auth Token: {auth_token}")
print(f"Twilio WhatsApp Number: {twilio_whatsapp_number}")

twilio_client = Client(account_sid, auth_token)

def extract_phone(phone):
    """Rimuove il prefisso internazionale +39, se presente."""
    if phone and phone.startswith('+39'):
        return phone[3:]
    return phone

def send_whatsapp_message(to, content_sid, content_variables):
    """Invia un messaggio WhatsApp usando un template Twilio."""
    try:
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

# Endpoint per Ordini creati
@app.route('/webhook', methods=['POST'])
def shopify_webhook_order_created():
    data = request.get_json()
    print("Dati ordine creato:", data)

    # Estrai informazioni dall'ordine
    customer_phone = extract_phone(data.get('billing_address', {}).get('phone') or data.get('customer', {}).get('default_address', {}).get('phone'))
    order_id = data.get('name')
    customer_name = data.get('billing_address', {}).get('first_name') or data.get('customer', {}).get('default_address', {}).get('first_name')
    payment_method = data.get('payment_gateway_names', [None])[0]
    total_price = data.get('total_price')

    if not customer_phone or not customer_name or not order_id:
        return jsonify({"status": "error", "message": "Dati mancanti."}), 400

    # Messaggio diverso per Bonifico Bancario
    if payment_method == "Bonifico Bancario":
        send_whatsapp_message(
            to=customer_phone,
            content_sid='HX52842202fcd7eacbb58c0be40b718e21',  # SID del template per "prova"
            content_variables={
                '1': customer_name,  # Nome del cliente
                '2': order_id,       # ID ordine
                '3': total_price     # Prezzo totale
            }
        )
    else:
        send_whatsapp_message(
            to=customer_phone,
            content_sid='HXcf8fe6d0d1ab5dfdc63e217875da3776',  # SID del template per ordini normali
            content_variables={
                '1': customer_name,  # Nome del cliente
                '2': order_id        # ID ordine
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
        content_sid='HX392e854b4a15afa18abe75359568a7e7',  # SID del template per "not_partenza"
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
    app.run(port=5000, debug=True)
