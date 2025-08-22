import socket
import json

def receive_hand_data(host='127.0.0.1', port=5050, output_file='receivedData.json'):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

    try:
        buffer = ""
        while True:
            chunk = client.recv(4096).decode('utf-8')
            if not chunk:
                break
            buffer += chunk

            while '\n' in buffer:
                packet, buffer = buffer.split('\n', 1)
                try:
                    data = json.loads(packet)
                    print("[Client] Received data:", data)

                    with open(output_file, 'w') as f:
                        json.dump(data, f, indent=4)

                    print(f"[Client] Overwritten {output_file} with latest data.")
                except json.JSONDecodeError as e:
                    print(f"[Client] JSON decode error: {e}")

    except Exception as e:
        print(f"[Client] Error: {e}")


receive_hand_data()

#add "if connection breaks" -> client.close() 
