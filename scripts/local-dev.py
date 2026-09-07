#!/usr/bin/env python3
"""Local macOS development process manager; private state stays in work/."""
import json
import hashlib
import os
import platform
from pathlib import Path
import signal
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'work' / 'run'
NODE = ROOT / 'work' / 'runtime' / 'node' / 'bin' / 'node'
ENV = dict(os.environ, NODE_ENV='development')
ENV['npm_config_cache'] = str(ROOT / 'work' / 'npm-cache')
ENV['npm_config_registry'] = 'https://registry.npmjs.org'
ENV['PATH'] = str(NODE.parent) + os.pathsep + ENV.get('PATH', '')
ENV.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='url.https://.insteadOf',
           GIT_CONFIG_VALUE_0='git://', GIT_CONFIG_KEY_1='url.https://github.com/.insteadOf',
           GIT_CONFIG_VALUE_1='ssh://git@github.com/')
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'compose.local.yml')]
SERVICES = {
    'server': (ROOT, [str(NODE), '--watch', str(ROOT / 'website/server/index.js')], 3000),
    'client': (ROOT / 'website/client', [str(NODE),
               str(ROOT / 'website/client/node_modules/vite/bin/vite.js'),
               '--host', '127.0.0.1', '--port', '5173', '--strictPort'], 5173),
}


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, env=ENV, check=True, **kwargs)


def prepare_local():
    if not NODE.exists():
        system = {'Darwin': 'darwin', 'Linux': 'linux'}.get(platform.system())
        arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64'}.get(platform.machine())
        if not system or not arch:
            raise RuntimeError('请手动安装 Node 20 到 work/runtime/node。')
        version = 'v20.20.2'
        filename = f'node-{version}-{system}-{arch}.tar.gz'
        base = f'https://nodejs.org/dist/{version}/'
        runtime = NODE.parents[2]
        runtime.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(base + 'SHASUMS256.txt') as response:
            checksums = response.read().decode()
        expected = next(line.split()[0] for line in checksums.splitlines() if line.endswith(filename))
        archive = runtime / filename
        urllib.request.urlretrieve(base + filename, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Node 下载校验失败。')
        run(['tar', '-xzf', str(archive), '-C', str(runtime)])
        (runtime / 'node').symlink_to(filename[:-7], target_is_directory=True)
        archive.unlink()
    config_path = ROOT / 'config.json'
    if not config_path.exists():
        config = json.loads((ROOT / 'config.json.example').read_text())
        config.update(HOST='127.0.0.1', WEB_CONCURRENCY=0,
                      BASE_URL='http://127.0.0.1:3000',
                      NODE_DB_URI='mongodb://127.0.0.1:27017/habitica-local?replicaSet=rs&directConnection=true',
                      SESSION_SECRET=secrets.token_hex(32), SESSION_SECRET_KEY=secrets.token_hex(32))
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        config_path.chmod(0o600)


def managed_pid(name):
    path = STATE / (name + '.pid')
    if not path.exists():
        return None
    pid = int(path.read_text())
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                            capture_output=True, text=True)
    entry = next(arg for arg in SERVICES[name][1] if arg.endswith('.js'))
    if result.returncode == 0 and entry in result.stdout:
        return pid
    return None


def port_busy(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def ensure_docker():
    if subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode == 0:
        return
    run(['open', '-a', 'Docker'])
    for _ in range(60):
        if subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError('Docker 未就绪，请打开 Docker Desktop 后重试。')


def stop_processes():
    for name in SERVICES:
        pid = managed_pid(name)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
                for _ in range(50):
                    if not managed_pid(name):
                        break
                    time.sleep(0.1)
                if managed_pid(name):
                    os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        (STATE / (name + '.pid')).unlink(missing_ok=True)


def start():
    if not NODE.exists():
        raise RuntimeError('缺少项目 Node 20：请安装到 work/runtime/node，或在此路径链接 Node 20。')
    for name, (_, _, port) in SERVICES.items():
        if not managed_pid(name) and port_busy(port):
            raise RuntimeError(f'端口 {port} 已被其他程序使用，未启动 {name}。')
    ensure_docker()
    run(COMPOSE + ['up', '-d', '--wait', '--wait-timeout', '150'])
    STATE.mkdir(parents=True, exist_ok=True)
    for name, (cwd, command, _) in SERVICES.items():
        if managed_pid(name):
            continue
        with (STATE / (name + '.log')).open('ab') as log:
            process = subprocess.Popen(command, cwd=cwd, env=ENV,
                                       stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=log, start_new_session=True)
        (STATE / (name + '.pid')).write_text(str(process.pid))
    for _ in range(120):
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/api/v3/status', timeout=2) as res:
                ready = json.load(res).get('success')
            with urllib.request.urlopen('http://127.0.0.1:5173', timeout=2) as res:
                ready = ready and res.status == 200
            if ready:
                print('Habitica 已启动：http://127.0.0.1:5173')
                print('日志：work/run/server.log 和 work/run/client.log')
                return
        except Exception:
            pass
        if not all(managed_pid(name) for name in SERVICES):
            break
        time.sleep(1)
    raise RuntimeError('启动未通过检查，请查看 work/run/ 下的日志。')


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'start':
        start()
    elif action == 'stop':
        stop_processes()
        run(COMPOSE + ['stop'])
        print('已停止，数据库数据保留。')
    elif action == 'restart':
        stop_processes()
        start()
    elif action == 'status':
        for name, (_, _, port) in SERVICES.items():
            print(f'{name}: PID={managed_pid(name)} port={port} listening={port_busy(port)}')
        run(COMPOSE + ['ps'])
    elif action == 'install':
        prepare_local()
        run(['git', 'submodule', 'update', '--init', '--depth=1'])
        run(['npm', 'ci', '--no-audit', '--no-fund'])
        run(['npm', 'run', 'sprites'])
    elif action == 'sprites':
        run(['npm', 'run', 'sprites'])
    elif action == 'logs':
        os.execvp('tail', ['tail', '-n', '40', '-f', str(STATE / 'server.log'), str(STATE / 'client.log')])
    elif action == 'backup':
        destination = ROOT / 'work' / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '.archive.gz')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('wb') as archive:
            run(COMPOSE + ['exec', '-T', 'mongo', 'mongodump', '--db', 'habitica-local',
                           '--archive', '--gzip'], stdout=archive)
        destination.chmod(0o600)
        print(destination)
    else:
        print('用法：./dev start|stop|restart|status|logs|install|sprites|backup')
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
