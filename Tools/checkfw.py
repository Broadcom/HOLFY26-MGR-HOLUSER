# checkfw.py version 1.2 10-April 2024
import socket


def test_tcp_port(server, port):
    """
    attempt a socket connection to the host on the port
    :param server:
    :param port:
    :return: boolean, true it connection is sucessful
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((server, int(port)))
        s.shutdown(2)
        print(f'Successfully connected to {server} on port {port}')
        return True
    except IOError as e:
        print(e)
        with open("checkfw.err", "a") as lf:
            lf.write(f'{e}\n')
            lf.close()
        return False


#status = test_tcp_port('www.opendomainfornowjunk.com', 443)
status = test_tcp_port('www.vmware.com', 443)
if status == False:
    print("Good")
else:
    print("Bad")
