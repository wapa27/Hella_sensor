To run, create a virtual environment:
``
    python3 -m venv hella-fast ``

Activate the environment:
``
    source hella-fast/bin/activate ``

Install dependencies:
`` 
    pip install fastapi uvicorn defusedxml requests ``

Note that the sensor must be connected via ethernet to the RPI to run the program.

Run the app: 
`` uvicorn HellaListener:app --host 192.168.1.1 --port 8080 ``

You may need to manually set the RPI IP:
`` 
    sudo ip addr add 192.168.1.1/24 dev eth0
    sudo ip link set eth0 up
``

The configuration interface can be found at the sensor URL - in my case 192.168.1.225
