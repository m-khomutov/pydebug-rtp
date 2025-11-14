import argparse
import logging
from pynput import keyboard
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from . import client


def handler(rtsp_client):
    logging.info('Starting http ...')
    class Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def do_GET(self): # noqa # pylint: disable=invalid-name
            logging.info("Path: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
            if self.path.startswith('/play'):
                rtsp_client.play(self.path.split('?')[1]) if '?' in self.path else rtsp_client.play()
            elif self.path.startswith('/pause'):
                rtsp_client.pause()
            elif self.path.startswith('/get_parameter'):
                rtsp_client.get_parameter(self.path.split('?')[1])
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
        super().__init__(*args, **kwargs)


def start():
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='rtp console client')
    parser.add_argument('url', type=str, help='url to rtp source')
    parser.add_argument('-rtpDump', type=str, help='path to file to dump rtp')
    parser.add_argument('-h264Dump', type=str, help='path to file to dump h264')
    parser.add_argument('-verbose', action='store_true', help='print debug info')
    args: argparse.Namespace = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    rtsp_client=client.Client((args.h264Dump, args.rtpDump), args.verbose)
    rtsp_client.connect(args.url)
    rtsp_client.run()
    http_server=ThreadedHTTPServer(('', 5445),handler(rtsp_client))
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    http_server.server_close()
    rtsp_client.stop()
    logging.info('Stopped')

    #Controller(args.url, (args.h264Dump, args.rtpDump))

