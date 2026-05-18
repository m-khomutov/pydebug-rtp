"""Network RTSP service"""
import argparse
import socket
import selectors
import types
import multiprocessing
import time
import logging
from .connection import Connection


class Service(multiprocessing.Process):
    """Manages RTSP protocol network activity"""
    def __init__(self, bind_address, **kwargs):
        super().__init__()
        self._root = kwargs.get('root', '.')
        self._verbose = kwargs.get('verbose', False)
        self._running = True
        self._connections = {}
        self._bind_address = bind_address
        self._lock = multiprocessing.Lock()

    def run(self) -> None:
        """Starts managing RTSP protocol network activity"""
        selector = selectors.DefaultSelector()
        accept_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        accept_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while True:
            try:
                accept_sock.bind(self._bind_address)
                break
            except OSError:
                time.sleep(2)
        accept_sock.listen()
        accept_sock.setblocking(False)
        selector.register(accept_sock, selectors.EVENT_READ, data=None)
        logging.basicConfig(level=logging.INFO)
        logging.info('streamer started')
        while self._is_running():
            try:
                for key, mask in selector.select(timeout=.01):
                    if key.data is None:
                        sock, address = key.fileobj.accept()
                        sock.setblocking(False)
                        selector.register(sock,
                                          selectors.EVENT_READ | selectors.EVENT_WRITE,
                                          types.SimpleNamespace(addr=address, inb=b'', outb=b''))
                        self._connections[address] = Connection(address=address, root=self._root, verbose=self._verbose)
                    else:
                        try:
                            self._on_event(key, mask)
                        except Exception as e:  # noqa # pylint: disable=bare-except
                            print(f'Exception: {e}')
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            del self._connections[key.data.addr]
                            print('connection to', key.data.addr, 'closed')
            except KeyboardInterrupt:
                self._stop()
        accept_sock.close()
        selector.close()
        logging.info('streamer finished')

    def join(self, timeout=None) -> None:
        """Implements service thread-safe stop"""
        self._stop()
        if super().is_alive():
            super().join(timeout)

    def _is_running(self):
        """Verifies running process"""
        with self._lock:
            return self._running

    def _stop(self):
        """Stops service in thread-safe manner"""
        with self._lock:
            self._running = False

    def _on_event(self, key, mask):
        """Manages event read/write on socket"""
        connect = self._connections.get(key.data.addr, None)
        if connect:
            if mask & selectors.EVENT_READ:
                connect.on_read_event(key)
            elif mask & selectors.EVENT_WRITE:
                connect.on_write_event(key)


def start():
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='rtp console client')
    parser.add_argument('-root', type=str, default='.', help='path to search rtp dumps. (def. ./)')
    parser.add_argument('-port', type=int, default=4558, help='port to bind service (def. 4558')
    parser.add_argument('-verbose', type=bool, default=False, help='print debug info about stream')
    args: argparse.Namespace = parser.parse_args()

    Service(('', args.port), root=args.root, verbose=args.verbose).run()
