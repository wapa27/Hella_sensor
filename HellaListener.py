from fastapi import FastAPI, Request, Response
from defusedxml.ElementTree import fromstring
import logging
import requests
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Define XML namespaces
NAMESPACES = {"sde2": "http://www.aglaia-gmbh.de/xml/2013/05/17/BaSS_SOAPd.xsd"}

# IP Addresses of sensors
SENSOR_IP_1 = "192.168.1.225"  # Front sensor
SENSOR_IP_2 = "192.168.1.226"  # Rear sensor

# Data store for the sensor counts
sensor_data = {
    SENSOR_IP_1: {'ins': 0, 'outs': 0, 'received': False},
    SENSOR_IP_2: {'ins': 0, 'outs': 0, 'received': False}
}

def log_error(error_reason, error_response):
    logger.error(f"Error response from APS: Reason: {error_reason}, Response: {error_response}")


def create_startup_response(referenced_notification_id, response_type="SOAP_SERVER_OK"):
    """Create a standard SOAP response message."""
    if not referenced_notification_id:
        logger.warning("Missing notification ID in response.")
        return None

    return f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:xsd="http://www.w3.org/2001/XMLSchema">
            <soap:Body>
                <answer_message 
                    referenced_notification_ID="{referenced_notification_id}"
                    server_response_type="{response_type}"
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




def create_count_channels_response(referenced_notification_id, response_type="SOAP_SERVER_OK"):
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

def send_count_to_modem(ins1, outs1, ins2, outs2):
    url = "http://127.0.0.1:5000/passCounts"
    json_data = {"message": f"ROUTE=UNKNOWN;D1INS={ins1};D1OUTS={outs1};D2INS={ins2};D2OUTS={outs2}"}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=json_data, headers=headers, timeout=5)
        response.raise_for_status()  # Raise exception for HTTP errors
        logger.info(f"Count data sent to modem successfully: {json_data}")
    except requests.RequestException as e:
        logger.error(f"Failed to send count data to modem: {e}")
        
        
async def wait_for_all_counts():
    """Wait for data from both sensors before sending it to the modem."""
    # Wait for both sensors to send data, with a timeout
    timeout = 5  # Timeout period in seconds

    for _ in range(timeout):
        if all(sensor['received'] for sensor in sensor_data.values()):
            break
        await asyncio.sleep(1)
    
    # If data from both sensors has been received, send to the modem
    ins1, outs1 = sensor_data[SENSOR_IP_1]['ins'], sensor_data[SENSOR_IP_1]['outs']
    ins2, outs2 = sensor_data[SENSOR_IP_2]['ins'], sensor_data[SENSOR_IP_2]['outs']
    
    send_count_to_modem(ins1, outs1, ins2, outs2)

    # Reset data to wait for the next batch
    sensor_data[SENSOR_IP_1] = {'ins': 0, 'outs': 0, 'received': False}
    sensor_data[SENSOR_IP_2] = {'ins': 0, 'outs': 0, 'received': False}

def process_message(xml_data, sender_ip):
    """Processes different types of incoming XML messages."""
    try:
        root_xml = fromstring(xml_data.encode())
        # Error messages
        error_message = root_xml.find(".//sde2:error_message", namespaces=NAMESPACES)
        if error_message is not None:
            log_error(error_message.attrib.get('error_reason', 'Unknown'),
                      error_message.attrib.get('error_text', 'Unknown'))
            return None

        # Alive notifications (no response needed)
        alive_notification = root_xml.find(".//sde2:alive_notification", namespaces=NAMESPACES)
        if alive_notification is not None:
            logger.info(f"Alive notification received from {sender_ip}")
            return None

        # Startup notification
        startup_notification = root_xml.find(".//sde2:startup_notification", namespaces=NAMESPACES)
        if startup_notification is not None:
            logger.info(f"Processing startup_notification from {sender_ip}")
            return create_startup_response(startup_notification.attrib.get("notification_ID"))

        ## Count channels notification
        count_channels_notification = root_xml.find(".//sde2:count_channels_notification", namespaces=NAMESPACES)
        if count_channels_notification is not None:
            logger.info(f"Processing count_channels_notification from {sender_ip}")

            try:
                ins, outs = 0, 0
                for child in root_xml.iter():
                    ins += int(child.attrib.get('count_in', 0))
                    outs += int(child.attrib.get('count_out', 0))

                # Store the data for this sensor
                if sender_ip == SENSOR_IP_1:
                    sensor_data[SENSOR_IP_1]['ins'] = ins
                    sensor_data[SENSOR_IP_1]['outs'] = outs
                    sensor_data[SENSOR_IP_1]['received'] = True
                elif sender_ip == SENSOR_IP_2:
                    sensor_data[SENSOR_IP_2]['ins'] = ins
                    sensor_data[SENSOR_IP_2]['outs'] = outs
                    sensor_data[SENSOR_IP_2]['received'] = True

                # Start waiting for data from both sensors
                asyncio.create_task(wait_for_all_counts())

                return create_count_channels_response(count_channels_notification.attrib.get('notification_ID'))

            except Exception as e:
                logger.error(f"Error parsing count data: {e}")
                return None
    except Exception as e:
        logger.error(f"Error processing XML response: {e}")
        return None

@app.post("/sensor")
async def handle_sensor(request: Request):
    """Handles incoming sensor messages."""
    try:
        xml_data = await request.body()
        xml_data = xml_data.decode("utf-8")
        print(xml_data)
        sender_ip = request.client.host  # Extract sender's IP

        response_xml = process_message(xml_data, sender_ip)
                            
        if response_xml:
            response_length = len(response_xml.encode('utf-8'))
            headers = {"Content-Type": "application/xml", "Content-Length": str(response_length) }
            return Response(content=response_xml, headers=headers, status_code=200)
        return Response(status_code=200) # May need to change at some point

    except Exception as e:
        logger.error(f"Error processing the message: {e}")
        return Response(content="Internal Server Error", status_code=500)


if __name__ == "__main__":
    # Specify the static IP address of the Raspberry Pi to listen on
    static_ip = "192.168.1.1"
    logger.info(f"Listening on IP: {static_ip}:8080")  # Log the IP address

