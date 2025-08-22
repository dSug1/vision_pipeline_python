import socket


def receive_hand_data(host='127.0.0.1', port=5050):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

receive_hand_data()
