import argparse
import logging
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from . import client


def handler(**handler_args):
    logging.info('Starting http ...')
    class Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self._rtsp_client=handler_args.get('client',None)
            super().__init__(*args, **kwargs)

        def do_GET(self): # noqa # pylint: disable=invalid-name
            logging.info("Path: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
            if self._rtsp_client:
                if str(self.path).startswith('/pause'):
                    self._rtsp_client.pause()
                elif str(self.path).startswith('/play'):
                    self._rtsp_client.play(self.path.split('?'))
                self.send_response(200)
            self.end_headers()

    return Handler


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def start():
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='rtp console client')
    parser.add_argument('url', type=str, help='url to rtp source')
    parser.add_argument('-rtpDump', type=str, help='path to file to dump rtp')
    parser.add_argument('-h264Dump', type=str, help='path to file to dump h264')
    args: argparse.Namespace = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    rtsp_client = client.Client((args.h264Dump,args.rtpDump))
    rtsp_client.connect(args.url)
    rtsp_client.run()
    http_server=ThreadedHTTPServer(('', 5445),handler(client=rtsp_client))
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    http_server.server_close()
    rtsp_client.stop()
    logging.info('Stopped')

    #Controller(args.url, (args.h264Dump, args.rtpDump))

