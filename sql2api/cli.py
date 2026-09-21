"""Command line entry point: ``sql2api serve`` and ``sql2api init``."""
import argparse
import logging
import os

from . import __version__, config, store
from .app import create_app

LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '::1')


def _serve(args):
    app = create_app()
    if args.host not in LOOPBACK_HOSTS and not config.api_key():
        logging.getLogger('sql2api').warning(
            'Listening on %s without SQL2API_API_KEY set: anyone who can reach this port can run SQL '
            'on your active connections.', args.host)
    logging.getLogger('sql2api').info('Using %s (connections: %s)', config.home(), config.connections_file().name)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def _init(args):
    home = config.home()
    home.mkdir(parents=True, exist_ok=True)
    (home / 'saved_sql').mkdir(exist_ok=True)
    target = config.connections_file()
    if target.exists():
        print(f'{target} already exists - left untouched')
    else:
        store.write_json_atomic(str(target), config.EXAMPLE_CONNECTIONS)
        print(f'Created {target}\nEdit it, set "active": true on the connections you want, then run: sql2api serve')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog='sql2api', description='Expose SQL databases as a REST API.')
    parser.add_argument('--version', action='version', version=f'sql2api {__version__}')
    commands = parser.add_subparsers(dest='command')

    serve = commands.add_parser('serve', help='start the HTTP server (default)')
    serve.add_argument('--host', default=os.environ.get('SQL2API_HOST', '127.0.0.1'))
    serve.add_argument('--port', type=int, default=int(os.environ.get('SQL2API_PORT', 5000)))
    serve.add_argument('--debug', action='store_true', default=config.env_flag('SQL2API_DEBUG'),
                       help='Flask debug mode - never use on a reachable host')
    serve.set_defaults(func=_serve)

    init = commands.add_parser('init', help='create db_connections.json and saved_sql/ in the home folder')
    init.set_defaults(func=_init)

    for sub in (serve, init):
        sub.add_argument('--home', help='folder holding db_connections.json and saved_sql/ '
                                        '(default: $SQL2API_HOME or the current directory)')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args = parser.parse_args(['serve', *(argv or [])])
    if getattr(args, 'home', None):
        os.environ['SQL2API_HOME'] = args.home
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    return args.func(args)
