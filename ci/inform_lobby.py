#!/usr/bin/python3

import sys
import argparse
import socket

def sendLobbyCommand(lobbyserver: str, lobbyport: int, command: str, data = None):

    def get_constants(prefix):
        """Create a dictionary mapping socket module constants to their names."""
        return dict( (getattr(socket, n), n)
                     for n in dir(socket)
                     if n.startswith(prefix)
                     )

    # Prefer IPv4 address, if available
    response = socket.getaddrinfo(lobbyserver, lobbyport, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    if not response:
        # Failed to get IPv4 address, try IPv6
        response = socket.getaddrinfo(lobbyserver, lobbyport, socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)

    if not response:
        raise RuntimeError("getaddrinfo failed for: {0}:{1}".format(lobbyserver, lobbyport))

    # Unpack the response tuple
    family, socktype, proto, canonname, sockaddr = response[0]

    families = get_constants('AF_')
    print("family:", families[family])
    print("sockaddr:", sockaddr)

    # create an INET, STREAMing socket
    sock = socket.socket(family, socket.SOCK_STREAM)

    # now connect to the lobby server
    print('Connect to lobby server')
    sock.connect(sockaddr)

    # Send the command to the lobby server
    msg = command.encode('utf-8') + b'\0' + data.encode('utf-8')
    print('Sending command')
    sent = sock.send(msg)
    if sent == 0:
        raise RuntimeError("socket connection broken")

    print('Sent command to lobby server')

    # Server is supposed to send a response
    # (Don't bother processing it, though)
    sock.settimeout(10.0)
    print('Waiting for response')
    result = sock.recv(1)
    if result == b'':
        raise RuntimeError("socket connection broken")

    print('Response received from lobby server')

    sock.close()

    print('Closed socket')

def main(argv):    
    parser = argparse.ArgumentParser(description='Send a command to a lobby server')
    parser.add_argument('lobbyserver', type=str)
    parser.add_argument('lobbyport', type=int)
    parser.add_argument("command", help="the command to send to the lobby server",
                        type=str)
    parser.add_argument('-d', '--data', type=str)
    args = parser.parse_args()

    print ('lobbyserver is:', args.lobbyserver)
    
    sendLobbyCommand(args.lobbyserver, args.lobbyport, args.command, args.data)

if __name__ == "__main__":
   main(sys.argv[1:])
