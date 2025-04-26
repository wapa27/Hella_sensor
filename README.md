To run the program, you will need to install fastAPI. It is recommended that you use a virtual environment for this.

`` uvicorn HellaListener:app --host 192.168.1.1 --port 8080 ``

You may need to manually set the RPI IP:
`` 
    sudo ip addr add 192.168.1.1/24 dev eth0
    sudo ip link set eth0 up
``

The configuration interface can be found at the sensor URL - in my case 192.168.1.225
