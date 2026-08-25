import os
import sys
import socket
import json
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="127.0.0.1")
parser.add_argument("--port", type=int, default=5050)
# ⛔ Mirrors the server's guard (`Python_Server_MediaPipe_vision_pipeline/
# Resources/Server.py`), and it is the same compliance control seen from the other
# end: connecting to a REMOTE host means this game is driven by hand data from
# another machine -- an untrusted source for a loop that has no authentication.
parser.add_argument("--allow-remote", action="store_true",
                    help="Permit a non-loopback --host. Read Server.py's header first.")
args = parser.parse_args()

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
if args.host not in _LOOPBACK_HOSTS and not args.allow_remote:
    print(f"[Client] REFUSING to connect to '{args.host}': only loopback is allowed "
          f"({', '.join(sorted(_LOOPBACK_HOSTS))}). Pass --allow-remote to override.")
    sys.exit(2)

# ⚠⚠ THE RECEIVE BUFFER IS CAPPED (audit 2026-08-25). `buffer += chunk` with no
# limit means a peer that never sends the `\n` delimiter grows it until the
# process dies -- and the peer does not have to be malicious for that: a server
# wedged mid-`sendall` produces the same shape. The largest real packet is
# `hands_world` at ~2.5 KB, so 1 MB is ~400x the worst legitimate case and cannot
# be reached by anything that is still speaking the protocol.
_MAX_BUFFER_BYTES = 1 << 20

# Connect to server. The server process needs a few seconds to import MediaPipe
# before it starts listening, so retry instead of failing on the first refusal.
# A failed connect() leaves the socket unusable on Windows, so create a fresh
# socket for each attempt.
_CONNECT_TIMEOUT = 30  # seconds
client = None
for _attempt in range(_CONNECT_TIMEOUT * 2):  # try every 0.5s
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((args.host, args.port))
        break
    except (ConnectionRefusedError, OSError):
        if client is not None:
            client.close()
        client = None
        time.sleep(0.5)

if client is None:
    print(f"[Client] Could not connect to {args.host}:{args.port} within {_CONNECT_TIMEOUT}s. Is the server running?")
    sys.exit(1)

print(f"[Client] Connected to {args.host}:{args.port}")

# Add the application directory (one level above Resources/) to the path so we
# can import the entry module that defines the dispatch callback.
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(app_dir)

# Now import the module
from PythonApp_Main import receive_float_array


def receive_keypoints_data():
    """Read newline-delimited JSON packets and dispatch them.

    ⚠ THE BUFFER IS BYTES, NOT STR, AND THAT IS A FIX (audit 2026-08-25). Decoding
    each 4096-byte chunk on arrival splits any multi-byte UTF-8 sequence that
    happens to straddle a chunk boundary and raises `UnicodeDecodeError`, which the
    outer handler turns into a dropped connection. Today's payload is all-ASCII
    numbers so it never fired -- but the first non-ASCII field ever added to a
    packet would make the pipeline fail roughly once every few hundred frames, at
    random, which is the worst kind of bug to go looking for. Buffering bytes and
    decoding each COMPLETE packet cannot split a character.
    """
    try:
        buffer = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                print("[Client] Connection closed by server.")
                break
            buffer += chunk

            if len(buffer) > _MAX_BUFFER_BYTES:
                print(f"[Client] Protocol error: {len(buffer)} bytes with no packet "
                      f"delimiter. Dropping the connection rather than growing "
                      f"without bound.")
                break

            while b'\n' in buffer:
                packet, buffer = buffer.split(b'\n', 1)
                try:
                    data = json.loads(packet.decode('utf-8'))
                    #print("[Client] Received data:", data)

                    if not isinstance(data, dict):
                        print(f"[Client] Warning: packet is {type(data).__name__}, "
                              f"not an object. Skipping.")
                        continue

                    data_type = data.get("type", "unknown")
                    float_array = data.get("data")

                    # Validate and dispatch directly from memory (no disk round-trip).
                    # ⚠ ELEMENT TYPES ARE CHECKED HERE, not just the container
                    # (audit 2026-08-25). Every consumer downstream does ARITHMETIC
                    # on these -- `_hand_position`, the Horn fit, the depth ratio --
                    # so one string in the array raises deep inside the gesture pass,
                    # AFTER part of the frame has already been applied. Rejecting the
                    # packet whole is the difference between a skipped frame and a
                    # half-updated one.
                    if not isinstance(float_array, list) or not float_array:
                        print(f"[Client] Warning: empty/invalid '{data_type}' array. Skipping dispatch.")
                    elif not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                 for v in float_array):
                        print(f"[Client] Warning: '{data_type}' contains non-numeric "
                              f"values. Skipping dispatch.")
                    else:
                        receive_float_array(data_type, float_array)

                except json.JSONDecodeError as e:
                    print(f"[Client] JSON decode error: {e}")
                except UnicodeDecodeError as e:
                    print(f"[Client] Packet was not valid UTF-8: {e}")
                except Exception as e:
                    print(f"[Client] Error processing packet: {e}")

    except Exception as e:
        print(f"[Client] Connection error: {e}")
    finally:
        client.close()
        print("[Client] Socket closed.")

receive_keypoints_data()

#Want help building a unified client that routes packets to different Blender handlers based on type? I can sketch that out next.
