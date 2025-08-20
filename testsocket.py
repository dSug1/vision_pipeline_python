import socket

HOST = '127.0.0.1'
PORT = 65432

# Assuming 'client_socket' is your connected socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT)) # Connect to the server

# ... (Sending and receiving data) ...

# To close the client connection:
client_socket.close()