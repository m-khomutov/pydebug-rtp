import argparse
from pynput import keyboard
from . import client


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


def start():
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='rtp console client')
    parser.add_argument('url', type=str, help='url to rtp source')
    parser.add_argument('-rtpDump', type=str, help='path to file to dump rtp')
    parser.add_argument('-h264Dump', type=str, help='path to file to dump h264')
    args: argparse.Namespace = parser.parse_args()

    Controller(args.url, (args.h264Dump, args.rtpDump))

