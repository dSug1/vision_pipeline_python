import socket
import json


from extract_hands_landmaks_in_array import extract_landmark_array as Create_hands_coordinates_array

def receive_keypoints_data(host='127.0.0.1', port=5050):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((host, port))
        print("[Client] Connected to server.")

        buffer = ""
        while True:
            chunk = client.recv(4096).decode('utf-8')
            if not chunk:
                print("[Client] Connection closed by server.")
                break
            buffer += chunk

            while '\n' in buffer:
                packet, buffer = buffer.split('\n', 1)
                try:
                    data = json.loads(packet)
                    #print("[Client] Received data:", data)

                    data_type = data.get("type", "unknown")
                    output_file = f"received_{data_type}_data.json"

                    with open(output_file, 'w') as f:
                        json.dump(data["data"], f, indent=4)

                    #print(f"[Client] Saved {data_type} keypoints to {output_file}.")
                    result = Create_hands_coordinates_array("./received_hands_data.json")
                    print(result)

                except json.JSONDecodeError as e:
                    print(f"[Client] JSON decode error: {e}")
                except Exception as e:
                    print(f"[Client] Error processing packet: {e}")

    except Exception as e:
        print(f"[Client] Connection error: {e}")
    finally:
        client.close()
        print("[Client] Socket closed.")

receive_keypoints_data()

#Want help building a unified client that routes packets to different Blender handlers based on type? I can sketch that out next.
