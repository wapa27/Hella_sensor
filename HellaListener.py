from flask import Flask, request, Response
from defusedxml.lxml import fromstring
import logging
import requests
import socket  # Import socket module

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

def log_error(error_reason, error_response):
    logger.error(f"Error response from APS: Reason: {error_reason}, Response: {error_response}")

def create_startup_response(referenced_notification_id):
    if not referenced_notification_id:
        logger.warning("Missing notification ID in startup response.")
        return None

    logger.info(f"Startup Notification ID: {referenced_notification_id}")
    return f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:xsd="http://www.w3.org/2001/XMLSchema">
            <soap:Body>
                <answer_message 
                    referenced_notification_ID="{referenced_notification_id}"
                    server_response_type="SOAP_SERVER_OK"
                    xmlns="http://www.aglaia-gmbh.de/xml/2013/05/17/BaSS_SOAPd.xsd">
                    <task_subscribe_count_channels
                        task_type="TASK_COUNT_CHANNELS"
                        serverTask_ID="116"
                        store_task="false"
                        activity_state="true"
                        store_on_transmission_error="false">
                        <trigger>
                            <event_trigger>
                                <counting_finished_event />
                            </event_trigger>
                        </trigger>
                    </task_subscribe_count_channels>
                </answer_message>
            </soap:Body>
        </soap:Envelope>"""

def create_count_channels_response(referenced_notification_id):
    if not referenced_notification_id:
        logger.warning("Missing notification ID in count channels response.")
        return None

    logger.info(f"Count Channels Response ID: {referenced_notification_id}")
    return f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:xsd="http://www.w3.org/2001/XMLSchema">
            <soap:Body>
                <answer_message 
                    referenced_notification_ID="{referenced_notification_id}"
                    server_response_type="SOAP_SERVER_OK"
                    xmlns="http://www.aglaia-gmbh.de/xml/2013/05/17/BaSS_SOAPd.xsd">
                </answer_message>
            </soap:Body>
        </soap:Envelope>"""

def send_count_to_modem(ins, outs):
    url = "http://127.0.0.1:5000/passCounts"
    json_data = {"message": f"ROUTE=UNKNOWN;D1INS={ins};D1OUTS={outs}"}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=json_data, headers=headers, timeout=5)
        response.raise_for_status()  # Raise exception for HTTP errors
        logger.info(f"Count data sent to modem successfully: {json_data}")
    except requests.RequestException as e:
        logger.error(f"Failed to send count data to modem: {e}")

def get_response(root_xml, xml_data):
    namespaces = {"sde2": "http://www.aglaia-gmbh.de/xml/2013/05/17/BaSS_SOAPd.xsd"}

    try:
        # Error message check
        error_message = root_xml.find(".//sde2:error_message", namespaces=namespaces)
        if error_message is not None:
            log_error(error_message.attrib.get('error_reason', 'Unknown'),
                      error_message.attrib.get('error_text', 'Unknown'))
            return None

        # Alive notification check
        if root_xml.find(".//sde2:alive_notification", namespaces=namespaces) is not None:
            logger.info("Alive notification received.")
            return None

        # Startup notification
        startup_notification = root_xml.find(".//sde2:startup_notification", namespaces=namespaces)
        if startup_notification is not None:
            return create_startup_response(startup_notification.attrib.get('notification_ID'))

        # Count channels notification
        count_channels_notification = root_xml.find(".//sde2:count_channels_notification", namespaces=namespaces)
        if count_channels_notification is not None:
            logger.info("Processing count_channels_notification")

            try:
                root = fromstring(xml_data.encode())  # Convert string to bytes
                ins, outs = 0, 0
                for child in root.iter():
                    ins += int(child.attrib.get('count_in', 0))
                    outs += int(child.attrib.get('count_out', 0))
                
                response_xml = create_count_channels_response(count_channels_notification.attrib.get('notification_ID'))
                send_count_to_modem(ins, outs)
                return response_xml
            except Exception as e:
                logger.error(f"Error parsing count data: {e}")
                return None
    except Exception as e:
        logger.error(f"Error processing XML response: {e}")
        return None

@app.route('/sensor', methods=['POST'])
def handle_sensor():
    try:
        xml_data = request.data.decode('utf-8')
        logger.info(request.remote_addr)
        # Secure XML parsing
        tree = fromstring(xml_data.encode())  # Convert string to bytes
        
        soap_response = get_response(tree, xml_data)
#        print(soap_response)
        if soap_response:
            return Response(soap_response, mimetype='text/xml', status=200)
        return Response("No valid response generated", status=204)
    except Exception as e:
        logger.error(f"Error processing the message: {e}")
        return Response("Internal Server Error", status=500)

if __name__ == "__main__":
    # Specify the static IP address of the Raspberry Pi to listen on
    static_ip = "192.168.1.1"
    logger.info(f"Listening on IP: {static_ip}:8080")  # Log the IP address
    app.run(host=static_ip, port=8080, threaded=True)

