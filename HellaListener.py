from flask import Flask, request, Response
from lxml import etree
import Hella_Message
import xml.etree.ElementTree as ET

app = Flask(__name__)

def log_error(error_reason, error_response):
    print("Error response from APS:")
    print("Error reason: " + error_reason)
    print("Error response: " + error_response)

def create_startup_response(referenced_notification_id):
    print("ID: " + referenced_notification_id)
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
    print("ID: " + referenced_notification_id)
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
    print ('Sending to modem: ')
    print ('Ins: ' + str(ins))
    print ('Outs: ' + str(outs))
    print ('____________________________')

def get_response(root_xml, xml_data):
    namespaces = {"sde2": "http://www.aglaia-gmbh.de/xml/2013/05/17/BaSS_SOAPd.xsd"}

    # Look for error message
    error_message = root_xml.find(".//sde2:error_message", namespaces=namespaces)
    if error_message is not None:
        print('Error notification')
        log_error(error_message.attrib.get('error_reason'), error_message.attrib.get('error_text'))
        return None

    # Look for alive notification
    alive_notification = root_xml.find(".//sde2:alive_notification", namespaces=namespaces)
    if alive_notification is not None: 
        print('Alive notification')
        return None    
    
    # Look for startup notification
    startup_notification = root_xml.find(".//sde2:startup_notification", namespaces=namespaces)
    if startup_notification is not None:
        print('Startup Notification')
        return create_startup_response(startup_notification.attrib.get('notification_ID'))
    
    # Look for count notification
    count_channels_notification = root_xml.find(".//sde2:count_channels_notification", namespaces=namespaces)
    if count_channels_notification is not None:
        print('count_channels Response')
        root = ET.fromstring(xml_data)
        ins = 0
        outs = 0
        # For debugging purposes
        for child in root.iter():
            if child.attrib and child.attrib.get('count_in'):
                ins += int(child.attrib.get('count_in')) 
                outs += int(child.attrib.get('count_out'))
        resopnse = create_count_channels_response(count_channels_notification.attrib.get('notification_ID'))
        send_count_to_modem(ins, outs)
        return resopnse
    

@app.route('/sensor', methods=['POST'])
def handle_sensor():
    try:
        xml_data = request.data.decode('utf-8')
        
        '''
        root = ET.fromstring(xml_data)
        # For debugging purposes
        for child in root.iter():
            if child.attrib:  # Check if the element has attributes
                print(f"Element: {child.tag}")
                for key, value in child.attrib.items():
                    print(f"  {key}: {value}")
        '''

        raw_data = request.data
        tree = etree.fromstring(raw_data)
        soap_response = get_response(tree, xml_data)
        return Response(soap_response, mimetype='text/xml', status=200)
    except Exception as e:
        print("Error processing the message:", e)
        return Response(f"Error processing the message: {e}", status=500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
