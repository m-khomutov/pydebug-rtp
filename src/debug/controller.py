import argparse
import logging
from pynput import keyboard
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from . import client


def handler():
    logging.info('Starting http ...')
    class Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def do_GET(self): # noqa # pylint: disable=invalid-name
            logging.info("Path: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
            self.send_response(200)
            self.end_headers()

    return Handler


class Controller:
    def __init__(self, url, dumps):
        cl = client.Client(dumps)
        try:
            cl.connect(url)
            cl.run()
            with keyboard.Events() as events:
                if not cl.is_running():
                    if cl.exception:
                        raise cl.exception
                for event in events:
                    if type(event) is keyboard.Events.Release:
                        if event.key == keyboard.KeyCode.from_char('q'):
                            break
                        elif event.key == keyboard.KeyCode.from_char('p'):
                            cl.pause()
                        elif event.key == keyboard.KeyCode.from_char('r'):
                            cl.play()
                        else:
                            pass
        except AttributeError as err:
            print(err)
        except ConnectionRefusedError as err:
            print(err)
        except RuntimeError as err:
            print(err)
        except client.InvalidRtpInterleaved as err:
            print(err)
        except KeyboardInterrupt as err:
            print(err)
        finally:
            cl.stop()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    def __init__(self, *args, **kwargs):
        self._rtsp_client=client.Client((kwargs.get('avc_dump'), kwargs.get('rtp_dump')))
        self._rtsp_client.connect(kwargs.get('rtsp_url'))
        self._rtsp_client.run()
        del kwargs['rtsp_url']
        del kwargs['avc_dump']
        del kwargs['rtp_dump']
        super().__init__(*args, **kwargs)

    def __del__(self):
        self._rtsp_client.stop()

def start():
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='rtp console client')
    parser.add_argument('url', type=str, help='url to rtp source')
    parser.add_argument('-rtpDump', type=str, help='path to file to dump rtp')
    parser.add_argument('-h264Dump', type=str, help='path to file to dump h264')
    args: argparse.Namespace = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    http_server=ThreadedHTTPServer(('', 5445),handler(),rtsp_url=args.url,avc_dump=args.h264Dump,rtp_dump=args.rtpDump)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    http_server.server_close()
    logging.info('Stopped')

    #Controller(args.url, (args.h264Dump, args.rtpDump))

