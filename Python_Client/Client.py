import socket
import json


#from extract_face_keypoints_in_array import extract_face_array as Create_face_coordinates_array
#from extract_hands_landmaks_in_array import extract_landmark_array as Create_hands_coordinates_array


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

                    #result_face_keypoints_Coord_array = Create_face_coordinates_array("./received_face_data.json")
                    #print(result_face_keypoints_Coord_array)

                    #result_handsLandmarksCoord_array = Create_hands_coordinates_array("./received_hands_data.json")
                    #print(result_handsLandmarksCoord_array)

                    # Save to output files
                    # Save to face keypoints coord array output file
                    #face_array_output_file = "face_keypoints_array_output.json"
                    #with open(face_array_output_file, 'w') as f:
                    #    json.dump(result_face_keypoints_Coord_array, f)

                    #print(f"[Client] Saved face keypoints array to {face_array_output_file}")
                    
                    # Save to hands landmarks coord array output file
                    #hands_array_output_file = "hands_landmarks_array_output.json"
                    #with open(hands_array_output_file, 'w') as f:
                    #    json.dump(result_handsLandmarksCoord_array, f)

                    #print(f"[Client] Saved hands landmark array to {hands_array_output_file}")


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
