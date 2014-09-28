from os.path import join, abspath
from subprocess import Popen, call

import json
import sys
import meinheld


CASE_RESULTS = ['OK', 'INFORMATIONAL', 'NON-STRICT', 'UNIMPLEMENTED',
        'UNCLEAN', 'FAILED']


# Environment Setup

def ensure_virtualenv():
    """A python2 instance will be installed to the current virtualenv, in
    order to run the Autobahn test client. So if there is none active, these
    tests should not proceed.
    """

    if not hasattr(sys, 'real_prefix'):
        raise Exception('Not inside a virtualenv')

def ensure_python2():
    """As recommended by Autobahn, the test client should be run with a
    Python 2 interpreter. The interpreter is installed in the current
    virtualenv. The build to be tested by tox is also reinstalled using
    pip2, to make it available to python2 tests."""

    src = '''
import sys
try:
    sys.real_prefix
    sys.exit(0)
except AttributeError:
    sys.exit(1)
'''

    if call(('python2.7', '-c', src)):
        call(('virtualenv', '-p', 'python2.7', sys.prefix))

    zipfile = 'meinheld-{}.zip'.format(meinheld.__version__)
    zipfile = abspath(join(sys.prefix, '..', 'dist', zipfile))
    call(('pip2', 'install', '--pre', '-U', zipfile))

def ensure_wstest():
    """Installs the test client."""

    try:
        call(('wstest', '-a'))
    except FileNotFoundError:
        call(('pip2', 'install', 'autobahntestsuite'))


# Server Setup

def setup_servers():
    """Starts servers within subprocesses."""

    server27 = Popen(('python2', 'autobahn_test_server.py', '8002'))
    server34 = Popen(('python3', 'autobahn_test_server.py', '8003'))
    return server27, server34

def teardown_servers(servers):
    """Stops given servers by killing their subprocesses."""

    for server in servers:
        try:
            server.kill()
            server.wait()
        except AttributeError:
            pass


# Report Parsing

def read_report(client_conf, max_status):
    """Reads the report generated by wstest."""

    with open(client_conf, 'r') as stream:
        report_dir = json.load(stream).get('outdir')

    with open(join(report_dir, 'index.json'), 'r') as stream:
        report = json.load(stream)

    result = (0, 0)
    for server_name, server in sorted(report.items()):
        print('Reading report for "{}"...'.format(server_name))

        result = max(map(status_level, server.values()))
        cases = sorted(filter(lambda e: not acceptable(status_level(e[1]),
                max_status), server.items()), key=case_sorting_key)

        for key, case in cases:
            report_case(key, case)

    return 0 if acceptable(result, max_status) else 1

def status_level(case):
    """Assigns numerical values to case results."""

    try:
        status = CASE_RESULTS.index(case.get('behavior'))
    except ValueError:
        status = len(CASE_RESULTS)

    try:
        close = CASE_RESULTS.index(case.get('behaviorClose'))
    except ValueError:
        close = len(CASE_RESULTS)

    return status, close

def acceptable(status, max_status):
    """Verifies that a test case result is acceptable."""
    return status[0] <= max_status[0] and status[1] <= max_status[1]

def case_sorting_key(e):
    """Sorting key for test case identifier."""
    return tuple(map(lambda n: int(n), e[0].split('.')))

def report_case(case_id, case):
    """Prints information about a test case."""

    status, close = status_level(case)
    if close > 0:
        msg = '{behavior} ({behaviorClose} close)'.format(**case)
    else:
        msg = case.get('behavior')
    print('  Case {} {}'.format(case_id, msg))


# Entry Point

def runtests():
    """Runs the Autobahn Test Suite against Meinheld on both Python 2.7 and
    Python 3.4. The test suite itself should run on Python 2.7, and should
    collect results from all servers from a single run (to report correctly).
    This is why both servers are tested from a single environemnt.
    """

    ensure_virtualenv()
    ensure_python2()
    ensure_wstest()

    servers = []
    try:
        servers = setup_servers()
        call(('wstest', '-m', 'fuzzingclient', '-s', 'fuzzingclient.json'))
    finally:
        teardown_servers(servers)
    sys.exit(read_report('fuzzingclient.json', (3, 4)))

if __name__ == '__main__':
    runtests()

